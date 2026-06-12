import re
import calendar

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService

stock_collection = db["stock_data"]

# -------------------------------------------------------------------
# Keyword → canonical company name (longest keywords match first).
# -------------------------------------------------------------------
_COMPANY_KEYWORDS: list[tuple[str, str]] = sorted(
    [
        ("reliance industries", "Reliance Industries"),
        ("tata consultancy services", "Tata Consultancy Services"),
        ("hindustan unilever", "Hindustan Unilever"),
        ("sun pharmaceutical", "Sun Pharmaceutical"),
        ("bajaj finance", "Bajaj Finance"),
        ("kotak mahindra", "Kotak Mahindra Bank"),
        ("state bank of india", "State Bank of India"),
        ("bharti airtel", "Bharti Airtel"),
        ("maruti suzuki", "Maruti Suzuki"),
        ("hcl technologies", "HCL Technologies"),
        ("hcl tech", "HCL Technologies"),
        ("reliance", "Reliance Industries"),
        ("infosys", "Infosys"),
        ("hdfcbank", "HDFC Bank"),
        ("hdfc bank", "HDFC Bank"),
        ("icicibank", "ICICI Bank"),
        ("icici bank", "ICICI Bank"),
        ("wipro", "Wipro"),
        ("bajaj", "Bajaj Finance"),
        ("kotak", "Kotak Mahindra Bank"),
        ("airtel", "Bharti Airtel"),
        ("maruti", "Maruti Suzuki"),
        ("sunpharma", "Sun Pharmaceutical"),
        ("titan", "Titan Company"),
        ("hdfc", "HDFC Bank"),
        ("icici", "ICICI Bank"),
        ("infy", "Infosys"),
        ("tcs", "Tata Consultancy Services"),
        ("sbin", "State Bank of India"),
        ("itc", "ITC"),
        ("hul", "Hindustan Unilever"),
        ("sbi", "State Bank of India"),
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03",
    "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

_MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August"
    r"|September|October|November|December"
)


class StockService:
    """Retrieve relevant stock records from MongoDB and generate an answer.

    Pipeline:
      question → extract company + date range → MongoDB query
      → RAGService.build_stock_context → GeminiService.generate → answer
    """

    @staticmethod
    def _extract_company(question: str) -> str | None:
        q = question.lower()
        for keyword, company in _COMPANY_KEYWORDS:
            if keyword in q:
                return company
        return None

    @staticmethod
    def _extract_date_range(question: str) -> tuple[str, str]:
        # 1) ISO date
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
        if m:
            d = m.group(1)
            return d, d

        # 2) "23 March 2023"
        m = re.search(
            rf"\b(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})\b",
            question, re.IGNORECASE,
        )
        if m:
            day = m.group(1).zfill(2)
            month = _MONTH_MAP[m.group(2).lower()]
            year = m.group(3)
            d = f"{year}-{month}-{day}"
            return d, d

        # 3) "March 2023" → full month
        m = re.search(rf"\b({_MONTH_PATTERN})\s+(\d{{4}})\b", question, re.IGNORECASE)
        if m:
            month = _MONTH_MAP[m.group(1).lower()]
            year = m.group(2)
            last = calendar.monthrange(int(year), int(month))[1]
            return f"{year}-{month}-01", f"{year}-{month}-{last:02d}"

        # 4) Just a year
        m = re.search(r"\b(20[12]\d)\b", question)
        if m:
            year = m.group(1)
            return f"{year}-01-01", f"{year}-12-31"

        return "2020-01-01", "2024-12-31"

    @staticmethod
    def process(question: str) -> dict:
        company = StockService._extract_company(question)
        date_start, date_end = StockService._extract_date_range(question)

        query: dict = {"date": {"$gte": date_start, "$lte": date_end}}
        if company:
            query["company"] = {"$regex": re.escape(company), "$options": "i"}

        records = list(stock_collection.find(query, {"_id": 0}).limit(20))

        # Fallback: relax date, keep company.
        if not records and company:
            records = list(
                stock_collection.find(
                    {"company": {"$regex": re.escape(company), "$options": "i"}},
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            return {
                "answer": (
                    "No stock data found for the specified company or date range. "
                    "Covered stocks include: Reliance, TCS, Infosys, HDFC Bank, "
                    "ICICI Bank, Wipro, HCL Tech, Bajaj Finance, Kotak, HUL, "
                    "SBI, ITC, Maruti Suzuki, Airtel, Sun Pharma."
                )
            }

        context = RAGService.build_stock_context(records)
        answer = GeminiService.generate(context, question)
        return {"answer": answer}

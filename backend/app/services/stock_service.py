import re

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
from app.utils.date_parser import extract_date_range, extract_month_only

stock_collection = db["stock_data"]

# ---------------------------------------------------------------------------
# Company keyword list (sorted longest-first for greedy matching)
# ---------------------------------------------------------------------------
_COMPANY_KEYWORDS: list[tuple[str, str]] = sorted(
    [
        ("reliance industries",      "Reliance Industries"),
        ("tata consultancy services","Tata Consultancy Services"),
        ("hindustan unilever",       "Hindustan Unilever"),
        ("sun pharmaceutical",       "Sun Pharmaceutical"),
        ("bajaj finance",            "Bajaj Finance"),
        ("kotak mahindra",           "Kotak Mahindra Bank"),
        ("state bank of india",      "State Bank of India"),
        ("bharti airtel",            "Bharti Airtel"),
        ("maruti suzuki",            "Maruti Suzuki"),
        ("hcl technologies",         "HCL Technologies"),
        ("hcl tech",                 "HCL Technologies"),
        ("reliance",                 "Reliance Industries"),
        ("infosys",                  "Infosys"),
        ("hdfcbank",                 "HDFC Bank"),
        ("hdfc bank",                "HDFC Bank"),
        ("icicibank",                "ICICI Bank"),
        ("icici bank",               "ICICI Bank"),
        ("wipro",                    "Wipro"),
        ("bajaj",                    "Bajaj Finance"),
        ("kotak",                    "Kotak Mahindra Bank"),
        ("airtel",                   "Bharti Airtel"),
        ("maruti",                   "Maruti Suzuki"),
        ("sunpharma",                "Sun Pharmaceutical"),
        ("titan",                    "Titan Company"),
        ("hdfc",                     "HDFC Bank"),
        ("icici",                    "ICICI Bank"),
        ("infy",                     "Infosys"),
        ("tcs",                      "Tata Consultancy Services"),
        ("sbin",                     "State Bank of India"),
        ("itc",                      "ITC"),
        ("hul",                      "Hindustan Unilever"),
        ("sbi",                      "State Bank of India"),
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)

_SUPPORTED_STOCKS = (
    "Reliance Industries, TCS, Infosys, HDFC Bank, ICICI Bank, Wipro, "
    "HCL Technologies, Bajaj Finance, Kotak Mahindra Bank, Hindustan Unilever, "
    "State Bank of India, ITC, Maruti Suzuki, Bharti Airtel, Sun Pharmaceutical"
)

# ---------------------------------------------------------------------------
# International stock detection
# If the question clearly refers to a non-Indian company or exchange, we
# return a polite scope message instead of an empty MongoDB result.
# ---------------------------------------------------------------------------
_INTERNATIONAL_COMPANIES: frozenset[str] = frozenset({
    # US tech giants
    "apple", "amazon", "google", "alphabet", "microsoft", "meta", "netflix",
    "tesla", "nvidia", "amd", "intel", "qualcomm", "salesforce", "oracle",
    "ibm", "cisco", "broadcom", "adobe", "paypal", "twitter", "x corp",
    "snapchat", "spotify", "shopify", "zoom", "uber", "lyft", "airbnb",
    # US finance / industrials
    "jpmorgan", "goldman sachs", "morgan stanley", "bank of america",
    "wells fargo", "citigroup", "american express", "visa", "mastercard",
    "berkshire", "warren buffett", "boeing", "general motors", "ford",
    "general electric", "3m", "johnson & johnson", "pfizer", "moderna",
    # European / Asian
    "samsung", "toyota", "sony", "honda", "hyundai", "alibaba", "tencent",
    "baidu", "xiaomi", "tsmc", "nintendo", "softbank", "lvmh", "nestle",
    "volkswagen", "bmw", "mercedes", "siemens", "shell", "bp", "hsbc",
    "barclays", "ubs", "deutsche bank",
    # Exchanges / indices (non-Indian)
    "nasdaq", "nyse", "s&p 500", "s&p500", "dow jones", "dow", "ftse",
    "nikkei", "hang seng", "dax", "cac 40", "shanghai", "forex",
    "cryptocurrency", "bitcoin", "ethereum", "crypto",
})

_INTL_MESSAGE = (
    "This chatbot covers Indian stock market data only (NSE-listed companies). "
    "It does not support international stocks, US markets (NASDAQ/NYSE), "
    "cryptocurrency, or forex. "
    "Supported Indian stocks: Reliance Industries, TCS, Infosys, HDFC Bank, "
    "ICICI Bank, Wipro, HCL Technologies, Bajaj Finance, Kotak Mahindra Bank, "
    "Hindustan Unilever, State Bank of India, ITC, Maruti Suzuki, "
    "Bharti Airtel, Sun Pharmaceutical."
)

# Dataset boundaries (must match ingest_stock.py)
_DS_START = "2020-01-01"
_DS_END   = "2025-01-01"


class StockService:
    """Retrieve relevant stock records from MongoDB and generate an answer.

    Query pipeline (each step only runs if the previous one returned nothing):
      1. Exact date / date range  – "TCS on 15 June 2023"
      2. Month-only (multi-year)  – "How did Infosys perform in June?"
      3. Company-only latest      – "Show me recent Wipro data"
      4. Latest available         – last-resort fallback
    """

    @staticmethod
    def _extract_company(question: str) -> str | None:
        q = question.lower()
        for keyword, company in _COMPANY_KEYWORDS:
            if keyword in q:
                return company
        return None

    @staticmethod
    def _is_international(question: str) -> bool:
        q = question.lower()
        return any(name in q for name in _INTERNATIONAL_COMPANIES)

    @staticmethod
    def process(question: str) -> dict:
        # Scope check: politely refuse international / non-NSE queries
        if StockService._is_international(question):
            return {"answer": _INTL_MESSAGE}

        company    = StockService._extract_company(question)
        month_only = extract_month_only(question)

        date_start, date_end = extract_date_range(
            question, default_start=_DS_START, default_end=_DS_END,
        )
        specific_date_found = (date_start != _DS_START or date_end != _DS_END)

        records: list[dict] = []

        # ------------------------------------------------------------------
        # Step 1 – exact date / date range
        # ------------------------------------------------------------------
        if specific_date_found:
            q1: dict = {"date": {"$gte": date_start, "$lte": date_end}}
            if company:
                q1["company"] = {"$regex": re.escape(company), "$options": "i"}
            records = list(stock_collection.find(q1, {"_id": 0}).limit(30))

        # ------------------------------------------------------------------
        # Step 2 – month-only trend query across all stored years
        # "How did TCS perform in June?" → all June records, every year
        # ------------------------------------------------------------------
        if not records and month_only:
            q2: dict = {"date": {"$regex": f"-{month_only}-"}}
            if company:
                q2["company"] = {"$regex": re.escape(company), "$options": "i"}
            records = list(
                stock_collection.find(q2, {"_id": 0})
                .sort("date", 1)
                .limit(50)
            )

        # ------------------------------------------------------------------
        # Step 3 – company-only fallback: latest trading days
        # ------------------------------------------------------------------
        if not records and company:
            records = list(
                stock_collection.find(
                    {"company": {"$regex": re.escape(company), "$options": "i"}},
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(20)
            )

        # ------------------------------------------------------------------
        # Step 4 – last resort: most recent records in the collection
        # ------------------------------------------------------------------
        if not records:
            records = list(
                stock_collection.find({}, {"_id": 0})
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            company_hint = f" for {company}" if company else ""
            return {
                "answer": (
                    f"No stock data found{company_hint} for the requested period. "
                    f"Supported Indian stocks: {_SUPPORTED_STOCKS}. "
                    f"Data covers January 2020 – January 2025."
                )
            }

        context = RAGService.build_stock_context(records)
        answer  = GeminiService.generate(context, question)
        return {"answer": answer}

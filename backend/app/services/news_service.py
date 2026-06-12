import re
import calendar

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService

news_collection = db["news_data"]

_CATEGORIES = [
    "politics", "economy", "sports", "technology", "entertainment",
    "health", "environment", "business", "cricket", "bollywood",
    "election", "budget", "science", "education",
]

_STOPWORDS = {
    "what", "when", "where", "which", "that", "this", "were", "have",
    "been", "from", "with", "about", "news", "india", "indian",
    "happened", "latest", "recent", "tell", "show", "give", "find",
    "some", "more", "there", "during", "after", "before", "since",
    "please", "like", "just", "also", "then", "than", "into",
}

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


class NewsService:
    """Retrieve relevant news records from MongoDB and generate an answer.

    Pipeline:
      question → extract date range + keywords → MongoDB query
      → RAGService.build_news_context → GeminiService.generate → answer
    """

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

        # Default: full news dataset range
        return "2023-01-01", "2024-12-31"

    @staticmethod
    def _extract_keywords(question: str) -> tuple[str | None, list[str]]:
        """Return (category_if_found, [remaining_keywords])."""
        q_lower = question.lower()

        detected_category: str | None = None
        for cat in _CATEGORIES:
            if cat in q_lower:
                detected_category = cat.capitalize()
                break

        # Extract meaningful words not in stopwords
        words = re.findall(r"\b[a-zA-Z]{4,}\b", question.lower())
        keywords = [
            w for w in words
            if w not in _STOPWORDS and w not in _CATEGORIES and len(w) >= 4
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_kw = [k for k in keywords if not (k in seen or seen.add(k))]  # type: ignore[func-returns-value]

        return detected_category, unique_kw[:5]

    @staticmethod
    def process(question: str) -> dict:
        date_start, date_end = NewsService._extract_date_range(question)
        category, keywords = NewsService._extract_keywords(question)

        query: dict = {"date": {"$gte": date_start, "$lte": date_end}}

        if category:
            query["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}

        if keywords:
            pattern = "|".join(re.escape(k) for k in keywords)
            query["$or"] = [
                {"title": {"$regex": pattern, "$options": "i"}},
                {"summary": {"$regex": pattern, "$options": "i"}},
            ]

        records = list(news_collection.find(query, {"_id": 0}).limit(15))

        # Fallback 1: drop keyword filter, keep category + date.
        if not records and keywords:
            query.pop("$or", None)
            records = list(news_collection.find(query, {"_id": 0}).sort("date", -1).limit(10))

        # Fallback 2: only date range.
        if not records:
            records = list(
                news_collection.find(
                    {"date": {"$gte": date_start, "$lte": date_end}},
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            return {
                "answer": (
                    "No news data found for the specified query or date range. "
                    "Historical news covers January 2023 – December 2024."
                )
            }

        context = RAGService.build_news_context(records)
        answer = GeminiService.generate(context, question)
        return {"answer": answer}

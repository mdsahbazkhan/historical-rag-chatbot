import re

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
from app.utils.date_parser import extract_date_range

news_collection = db["news_data"]

# ---------------------------------------------------------------------------
# Category detection
# Sorted longest-first so more specific phrases ("world cup") win over short
# words ("sport").
# ---------------------------------------------------------------------------
_CATEGORY_SYNONYMS: list[tuple[str, str]] = sorted(
    [
        ("world cup",      "Sports"),
        ("political",      "Politics"),
        ("politics",       "Politics"),
        ("election",       "Politics"),
        ("parliament",     "Politics"),
        ("government",     "Politics"),
        ("minister",       "Politics"),
        ("economic",       "Economy"),
        ("economy",        "Economy"),
        ("financial",      "Economy"),
        ("finance",        "Economy"),
        ("inflation",      "Economy"),
        ("budget",         "Economy"),
        ("gdp",            "Economy"),
        ("cricket",        "Sports"),
        ("ipl",            "Sports"),
        ("sport",          "Sports"),
        ("bollywood",      "Entertainment"),
        ("entertainment",  "Entertainment"),
        ("technology",     "Technology"),
        ("startup",        "Technology"),
        ("digital",        "Technology"),
        ("healthcare",     "Health"),
        ("medical",        "Health"),
        ("hospital",       "Health"),
        ("vaccine",        "Health"),
        ("health",         "Health"),
        ("environment",    "Environment"),
        ("climate",        "Environment"),
        ("pollution",      "Environment"),
        ("flood",          "Environment"),
        ("corporate",      "Business"),
        ("business",       "Business"),
        ("science",        "Science"),
        ("education",      "Education"),
        ("school",         "Education"),
        ("tech",           "Technology"),
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)

# Words that carry no topical signal — filtered out before keyword matching
_STOPWORDS: frozenset[str] = frozenset({
    "what", "when", "where", "which", "that", "this", "were", "have",
    "been", "from", "with", "about", "news", "india", "indian",
    "happened", "latest", "recent", "tell", "show", "give", "find",
    "some", "more", "there", "during", "after", "before", "since",
    "please", "like", "just", "also", "then", "than", "into",
    "major", "important", "significant", "notable", "events",
    "stories", "articles", "updates", "coverage", "report",
    "regarding", "concerning", "related", "anything", "everything",
    "various", "several", "something",
})

# Dataset boundaries (must match ingest_news.py)
_DS_START = "2024-01-01"
_DS_END   = "2025-12-31"


class NewsService:
    """Retrieve relevant news records from MongoDB and generate an answer.

    Query pipeline (each step only runs if the previous one returned nothing):
      1. keyword + category + date   – most specific
      2. category + date             – drop keywords
      3. keyword + date              – drop category
      4. date only                   – broad date match
      5. latest available            – last-resort fallback
    """

    @staticmethod
    def _extract_category(question: str) -> str | None:
        q = question.lower()
        for keyword, category in _CATEGORY_SYNONYMS:
            if keyword in q:
                return category
        return None

    @staticmethod
    def _extract_keywords(question: str, category: str | None) -> list[str]:
        """Return meaningful search keywords (≥5 chars, not stopwords, not the category)."""
        cat_words: set[str] = {category.lower()} if category else set()
        words = re.findall(r"\b[a-zA-Z]{5,}\b", question.lower())
        seen:   set[str] = set()
        result: list[str] = []
        for w in words:
            if w not in _STOPWORDS and w not in cat_words and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:5]

    @staticmethod
    def process(question: str) -> dict:
        date_start, date_end = extract_date_range(
            question, default_start=_DS_START, default_end=_DS_END,
        )
        category = NewsService._extract_category(question)
        keywords = NewsService._extract_keywords(question, category)

        date_filter: dict = {"date": {"$gte": date_start, "$lte": date_end}}
        records: list[dict] = []

        # ------------------------------------------------------------------
        # Step 1 – keyword + category + date
        # ------------------------------------------------------------------
        if keywords and category:
            pattern = "|".join(re.escape(k) for k in keywords)
            records = list(
                news_collection.find(
                    {
                        **date_filter,
                        "category": {"$regex": f"^{re.escape(category)}$", "$options": "i"},
                        "$or": [
                            {"title":   {"$regex": pattern, "$options": "i"}},
                            {"summary": {"$regex": pattern, "$options": "i"}},
                        ],
                    },
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(15)
            )

        # ------------------------------------------------------------------
        # Step 2 – category + date (drop keywords)
        # ------------------------------------------------------------------
        if not records and category:
            records = list(
                news_collection.find(
                    {
                        **date_filter,
                        "category": {"$regex": f"^{re.escape(category)}$", "$options": "i"},
                    },
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(15)
            )

        # ------------------------------------------------------------------
        # Step 3 – keyword + date (drop category)
        # ------------------------------------------------------------------
        if not records and keywords:
            pattern = "|".join(re.escape(k) for k in keywords)
            records = list(
                news_collection.find(
                    {
                        **date_filter,
                        "$or": [
                            {"title":   {"$regex": pattern, "$options": "i"}},
                            {"summary": {"$regex": pattern, "$options": "i"}},
                        ],
                    },
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(12)
            )

        # ------------------------------------------------------------------
        # Step 4 – date only
        # ------------------------------------------------------------------
        if not records:
            records = list(
                news_collection.find(date_filter, {"_id": 0})
                .sort("date", -1)
                .limit(10)
            )

        # ------------------------------------------------------------------
        # Step 5 – latest available
        # ------------------------------------------------------------------
        if not records:
            records = list(
                news_collection.find({}, {"_id": 0})
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            topic_hint = f" about '{', '.join(keywords[:2])}'" if keywords else ""
            cat_hint   = f" in the {category} category" if category else ""
            return {
                "answer": (
                    f"No historical news found{topic_hint}{cat_hint} "
                    f"for the requested date range. "
                    f"Historical news covers January 2024 – December 2025."
                )
            }

        context = RAGService.build_news_context(records)
        answer  = GeminiService.generate(context, question)
        return {"answer": answer}

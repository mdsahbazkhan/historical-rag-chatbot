import re
import calendar

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService

weather_collection = db["weather_data"]

# -------------------------------------------------------------------
# Known Indian cities (longest-first for greedy matching).
# -------------------------------------------------------------------
_CITIES = [
    "visakhapatnam", "ahmedabad", "hyderabad", "bangalore", "bengaluru",
    "new delhi", "lucknow", "chennai", "kolkata", "calcutta", "mumbai",
    "bombay", "jaipur", "nagpur", "indore", "bhopal", "kanpur",
    "patna", "surat", "vadodara", "ludhiana", "agra", "varanasi",
    "delhi", "pune",
]

_CITY_ALIASES = {
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "bengaluru": "Bangalore",
    "new delhi": "Delhi",
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


class WeatherService:
    """Retrieve relevant weather records from MongoDB and generate an answer.

    Pipeline:
      question → extract city + date range → MongoDB query
      → RAGService.build_weather_context → GeminiService.generate → answer
    """

    @staticmethod
    def _extract_city(question: str) -> str | None:
        q = question.lower()
        for city in _CITIES:               # longest match wins
            if city in q:
                return _CITY_ALIASES.get(city, city.title())
        return None

    @staticmethod
    def _extract_date_range(question: str) -> tuple[str, str]:
        # 1) ISO date — "2023-03-23"
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
        if m:
            d = m.group(1)
            return d, d

        # 2) "23 March 2023" or "March 23, 2023"
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

        # 4) Just a year — "in 2022"
        m = re.search(r"\b(20[12]\d)\b", question)
        if m:
            year = m.group(1)
            return f"{year}-01-01", f"{year}-12-31"

        # 5) Default: full dataset range
        return "2020-01-01", "2024-12-31"

    @staticmethod
    def process(question: str) -> dict:
        city = WeatherService._extract_city(question)
        date_start, date_end = WeatherService._extract_date_range(question)

        query: dict = {"date": {"$gte": date_start, "$lte": date_end}}
        if city:
            query["city"] = {"$regex": f"^{re.escape(city)}$", "$options": "i"}

        records = list(weather_collection.find(query, {"_id": 0}).limit(20))

        # Fallback: relax the date filter, keep the city.
        if not records and city:
            records = list(
                weather_collection.find(
                    {"city": {"$regex": f"^{re.escape(city)}$", "$options": "i"}},
                    {"_id": 0},
                )
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            return {
                "answer": (
                    "No weather data found for the specified city or date range. "
                    "Available cities: Delhi, Mumbai, Chennai, Hyderabad, Bangalore, "
                    "Kolkata, Pune, Ahmedabad, Jaipur, Lucknow."
                )
            }

        context = RAGService.build_weather_context(records)
        answer = GeminiService.generate(context, question)
        return {"answer": answer}

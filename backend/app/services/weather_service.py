import re

from app.config.database import db
from app.services.rag_service import RAGService
from app.services.gemini_service import GeminiService
from app.utils.date_parser import (
    extract_date_range,
    extract_month_only,
    extract_season_months,
)

weather_collection = db["weather_data"]


_CITIES = [
    "visakhapatnam", "ahmedabad", "hyderabad", "bangalore", "bengaluru",
    "new delhi", "lucknow", "chennai", "kolkata", "calcutta", "mumbai",
    "bombay", "jaipur", "nagpur", "indore", "bhopal", "kanpur",
    "patna", "surat", "vadodara", "ludhiana", "agra", "varanasi",
    "delhi", "pune",
]

_CITY_ALIASES: dict[str, str] = {
    "bombay":    "Mumbai",
    "madras":    "Chennai",
    "calcutta":  "Kolkata",
    "bengaluru": "Bangalore",
    "new delhi": "Delhi",
}

_AVAILABLE_CITIES = (
    "Delhi, Mumbai, Chennai, Hyderabad, Bangalore, "
    "Kolkata, Pune, Ahmedabad, Jaipur, Lucknow"
)


_COMPARISON_SIGNALS: frozenset[str] = frozenset({
    "which city", "hottest city", "coldest city", "rainiest city",
    "wettest city", "windiest city", "most rain", "all cities",
    "compare cities", "across cities",
})

_DS_START = "2021-01-01"
_DS_END   = "2025-12-31"


class WeatherService:
    """Retrieve relevant weather records from MongoDB and generate an answer.

    Query pipeline (each step only runs if the previous one returned nothing):
      1. Exact date / date range           – "Delhi on 15 June 2022"
      2. Month-only trend (multi-year)     – "How hot is Delhi in June?"
      3. Seasonal trend                    – "Delhi weather in winter"
      4. City-comparison (no city filter)  – "Which city is hottest in May?"
      5. City-only latest records          – fallback when date missing
      6. Latest available records          – last-resort give-Gemini-something
    """

    @staticmethod
    def _extract_city(question: str) -> str | None:
        q = question.lower()
        for city in _CITIES:
            if city in q:
                return _CITY_ALIASES.get(city, city.title())
        return None

    @staticmethod
    def _is_comparison(question: str) -> bool:
        q = question.lower()
        return any(sig in q for sig in _COMPARISON_SIGNALS)

    @staticmethod
    def _city_filter(city: str) -> dict:
        return {"city": {"$regex": f"^{re.escape(city)}$", "$options": "i"}}

    @staticmethod
    def process(question: str) -> dict:
        city          = WeatherService._extract_city(question)
        month_only    = extract_month_only(question)
        season_months = extract_season_months(question)
        comparison    = WeatherService._is_comparison(question)

        date_start, date_end = extract_date_range(
            question, default_start=_DS_START, default_end=_DS_END,
        )
        specific_date_found = (date_start != _DS_START or date_end != _DS_END)

        records: list[dict] = []

       
        if specific_date_found:
            query: dict = {"date": {"$gte": date_start, "$lte": date_end}}
            if city:
                query.update(WeatherService._city_filter(city))
            records = list(weather_collection.find(query, {"_id": 0}).limit(30))

        if not records and month_only:
            q2: dict = {"date": {"$regex": f"-{month_only}-"}}
            if city:
                q2.update(WeatherService._city_filter(city))
            records = list(
                weather_collection.find(q2, {"_id": 0})
                .sort("date", 1)
                .limit(50)
            )

        if not records and season_months:
            pattern = "|".join(f"-{m}-" for m in season_months)
            q3: dict = {"date": {"$regex": pattern}}
            if city:
                q3.update(WeatherService._city_filter(city))
            records = list(
                weather_collection.find(q3, {"_id": 0})
                .sort("date", 1)
                .limit(50)
            )


        if not records and comparison:
            q4: dict = {}
            if month_only:
                q4["date"] = {"$regex": f"-{month_only}-"}
            elif season_months:
                q4["date"] = {"$regex": "|".join(f"-{m}-" for m in season_months)}
            records = list(
                weather_collection.find(q4, {"_id": 0})
                .sort("temperature", -1)
                .limit(50)
            )

   
        if not records and city:
            records = list(
                weather_collection.find(WeatherService._city_filter(city), {"_id": 0})
                .sort("date", -1)
                .limit(20)
            )


        if not records:
            records = list(
                weather_collection.find({}, {"_id": 0})
                .sort("date", -1)
                .limit(10)
            )

        if not records:
            city_hint = f" for {city}" if city else ""
            return {
                "answer": (
                    f"No weather data found{city_hint} for the requested period. "
                    f"Available cities: {_AVAILABLE_CITIES}. "
                    f"Data covers January 2021 – December 2025."
                )
            }

        context = RAGService.build_weather_context(records)
        answer  = GeminiService.generate(context, question)
        return {"answer": answer}

from datetime import datetime, timezone

from app.config.database import db
from app.services.weather_service import WeatherService
from app.services.stock_service import StockService
from app.services.news_service import NewsService

chat_history_collection = db["chat_history"]

_SERVICES: dict = {
    "weather": WeatherService,
    "stock":   StockService,
    "news":    NewsService,
}


_DOMAIN_SIGNALS: dict[str, frozenset[str]] = {
    "weather": frozenset({
        "temperature", "weather", "humidity", "rainfall", "rain",
        "wind", "celsius", "cloudy", "sunny", "heatwave", "fog",
        "climate", "forecast", "degrees", "precipitation",
        "monsoon season", "winter in", "summer in",
    }),
    "stock": frozenset({
        "stock", "share price", "closing price", "opening price",
        "nse", "sensex", "nifty", "bse", "ipo", "dividend",
        "trading", "market cap", "quarterly result",
        "reliance", "tcs", "infosys", "hdfc", "icici", "wipro",
        "bajaj finance", "kotak", "airtel", "maruti", "sbi", "itc",
    }),
    "news": frozenset({
        "news", "article", "headline", "election", "parliament",
        "minister", "government", "policy", "protest", "crisis",
        "announced", "scheme", "incident", "report",
    }),
}

_MODE_LABELS: dict[str, str] = {
    "weather": "Weather",
    "stock":   "Stock",
    "news":    "News",
}


def _detect_wrong_mode(mode: str, question: str) -> str | None:
    """Return a redirect message when the question clearly belongs to a
    different domain and has no signals for the current one.

    Returns None when the question is on-topic or ambiguous.
    """
    q = question.lower()

    current_score = sum(1 for sig in _DOMAIN_SIGNALS[mode] if sig in q)
    if current_score > 0:
        return None  # Question matches the current mode — let it through

    other_scores = {
        domain: sum(1 for sig in signals if sig in q)
        for domain, signals in _DOMAIN_SIGNALS.items()
        if domain != mode
    }

    best_other = max(other_scores, key=other_scores.get)
    if other_scores[best_other] > 0:
        return (
            f"This is the {_MODE_LABELS[mode]} assistant. "
            f"Your question appears to be about {_MODE_LABELS[best_other]} data. "
            f"Please switch to {_MODE_LABELS[best_other]} mode for this query."
        )

    return None  


class ChatService:
    """Dispatch requests to the correct domain service and persist history.

    Responsibilities (single layer):
      - validate mode and question
      - wrong-mode redirect (fast path — no DB call)
      - delegate to domain service
      - error boundary
      - persist to chat_history
    """

    @staticmethod
    def process(mode: str, question: str) -> dict:
        mode    = mode.strip().lower()
        service = _SERVICES.get(mode)

        if not service:
            return {
                "error": (
                    f"Invalid mode '{mode}'. "
                    f"Valid modes are: {', '.join(_SERVICES.keys())}."
                )
            }

        question = (question or "").strip()
        if not question:
            return {"error": "Question must not be empty."}


        redirect = _detect_wrong_mode(mode, question)
        if redirect:
            result: dict = {"answer": redirect}
        else:
            try:
                result = service.process(question)
            except RuntimeError as exc:
                result = {"error": str(exc)}
            except Exception as exc:
                result = {"error": f"Unexpected server error: {exc}"}

        try:
            chat_history_collection.insert_one(
                {
                    "mode":      mode,
                    "question":  question,
                    "answer":    result.get("answer"),
                    "error":     result.get("error"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            pass

        return result

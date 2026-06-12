from datetime import datetime, timezone

from app.config.database import db
from app.services.weather_service import WeatherService
from app.services.stock_service import StockService
from app.services.news_service import NewsService

chat_history_collection = db["chat_history"]

_SERVICES = {
    "weather": WeatherService,
    "stock": StockService,
    "news": NewsService,
}


class ChatService:
    """Dispatch requests to the correct domain service and persist history.

    Single responsibility: routing + error boundary + history write.
    All domain logic lives in the individual services.
    """

    @staticmethod
    def process(mode: str, question: str) -> dict:
        mode = mode.strip().lower()
        service = _SERVICES.get(mode)

        if not service:
            return {
                "error": (
                    f"Invalid mode '{mode}'. "
                    f"Valid modes are: {', '.join(_SERVICES.keys())}."
                )
            }

        if not question or not question.strip():
            return {"error": "Question must not be empty."}

        try:
            result = service.process(question.strip())
        except RuntimeError as exc:
            # Gemini / MongoDB runtime errors surfaced by services
            result = {"error": str(exc)}
        except Exception as exc:
            result = {"error": f"Unexpected error: {exc}"}

        # Persist every exchange regardless of success/failure.
        try:
            chat_history_collection.insert_one(
                {
                    "mode": mode,
                    "question": question.strip(),
                    "answer": result.get("answer"),
                    "error": result.get("error"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            pass  # History write must never break the response.

        return result

import re
import google.generativeai as genai
from app.config.settings import GEMINI_API_KEY

# Configure once at import time; safe because the module is loaded once per process.
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def _friendly_error(exc: Exception) -> str:
    """Convert a raw Gemini SDK exception into a user-readable message."""
    msg = str(exc)

    # 429 — rate limit / quota exceeded
    if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
        # Try to extract the suggested retry delay (e.g. "retry in 26.1s")
        m = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
        wait = f" Please try again in about {int(float(m.group(1)))} seconds." if m else " Please try again in a moment."
        return (
            "The AI service has reached its request limit for now."
            + wait
        )

    # 401 / 403 — bad or missing API key
    if "401" in msg or "403" in msg or "api_key" in msg.lower() or "invalid" in msg.lower():
        return (
            "Gemini API key is invalid or missing. "
            "Please check the GEMINI_API_KEY value in your .env file."
        )

    # 500 / 503 — upstream server error
    if "500" in msg or "503" in msg or "unavailable" in msg.lower():
        return (
            "The Gemini AI service is temporarily unavailable. "
            "Please try again in a few minutes."
        )

    # Generic fallback — still cleaner than the raw SDK dump
    return "The AI service encountered an unexpected error. Please try again."


_SYSTEM_PROMPT = (
    "You are a knowledgeable assistant specializing in historical Indian data "
    "(weather, stock markets, and news).\n"
    "Rules:\n"
    "- Answer ONLY using the provided Context section below.\n"
    "- If the context lacks sufficient information, say exactly: "
    "'I do not have enough historical data to answer that question.'\n"
    "- Be precise with numbers, dates, and units.\n"
    "- Keep the answer concise and factual."
)


class GeminiService:
    """Thin wrapper around the Gemini generative model.

    Single responsibility: compose the prompt and call the API.
    All domain logic lives in the domain services and RAGService.
    """

    _model = None

    @classmethod
    def _get_model(cls) -> genai.GenerativeModel:
        if cls._model is None:
            if not GEMINI_API_KEY:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set. Add it to your .env file."
                )
            cls._model = genai.GenerativeModel("gemini-3-flash-preview")
        return cls._model

    @staticmethod
    def generate(context: str, question: str) -> str:
        """Generate a grounded answer from retrieved context.

        Args:
            context: Formatted string of MongoDB records built by RAGService.
            question: Original user question.

        Returns:
            Plain-text answer produced by Gemini.

        Raises:
            RuntimeError: On API failure or missing API key.
        """
        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"--- Context ---\n{context}\n\n"
            f"--- Question ---\n{question}\n\n"
            f"--- Answer ---"
        )

        try:
            model = GeminiService._get_model()
            response = model.generate_content(prompt)

            # Gemini may block a response; handle gracefully.
            if not response.candidates:
                raise RuntimeError(
                    "Gemini returned an empty response (possibly blocked by safety filters)."
                )

            return response.text.strip()

        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(_friendly_error(exc)) from exc

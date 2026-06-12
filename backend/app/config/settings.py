import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI:        str = os.getenv("MONGO_URI", "")
DATABASE_NAME:    str = os.getenv("DATABASE_NAME", "historical_rag")
GEMINI_API_KEY:   str = os.getenv("GEMINI_API_KEY", "")
GUARDIAN_API_KEY: str = os.getenv("GUARDIAN_API_KEY", "")

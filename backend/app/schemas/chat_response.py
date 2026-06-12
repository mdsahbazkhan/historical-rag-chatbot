from pydantic import BaseModel
from typing import Optional


class ChatResponse(BaseModel):
    answer: Optional[str] = None
    error: Optional[str] = None

from pydantic import BaseModel

class ChatRequest(BaseModel):
    mode: str
    question: str
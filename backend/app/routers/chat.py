from fastapi import APIRouter
from app.schemas.chat_request import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter()

@router.post("/chat")
def chat(data: ChatRequest):
    return ChatService.process(
        data.mode,
        data.question
    )
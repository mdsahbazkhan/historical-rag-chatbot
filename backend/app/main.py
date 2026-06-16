from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.chat import router

app = FastAPI(
    title="Historical RAG Chatbot API",
    description="Multi-domain RAG chatbot for Indian historical weather, stock, and news data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok", "message": "Historical RAG Chatbot API is running."}


app.include_router(router, prefix="/api")

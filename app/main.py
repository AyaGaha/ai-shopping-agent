from dotenv import load_dotenv

load_dotenv()  # charge .env avant tout le reste

from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import run_agent

app = FastAPI(title="P059 — Agent IA de commande (hello world)")


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    """Endpoint de vérification rapide — utile pour valider que le déploiement tourne."""
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: ChatRequest):
    return run_agent(payload.message)

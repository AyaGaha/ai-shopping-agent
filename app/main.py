from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import run_agent

app = FastAPI(title="P059 — Agent IA de commande")


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None  # renvoie le champ `messages` de la réponse précédente pour confirmer une commande


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: ChatRequest):
    return run_agent(payload.message, payload.history)

import logging
from typing import Literal

import openai
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent import run_agent

logger = logging.getLogger("p059")

app = FastAPI(title="P059 — Agent IA de commande")


class HistoryMessage(BaseModel):
    """Un message de l'historique renvoye par le client.

    Le champ `role` est obligatoire et ne peut PAS etre "system" : le client ne doit jamais
    pouvoir injecter ses propres instructions systeme. Les autres champs (tool_calls,
    tool_call_id...) sont conserves tels quels pour que le LLM retrouve le fil de la conversation.
    """

    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "tool"]
    content: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] | None = None  # = le champ `messages` de la reponse precedente


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: ChatRequest):
    history = [m.model_dump(exclude_none=True) for m in payload.history] if payload.history else None
    try:
        return run_agent(payload.message, history)
    except openai.APIError as e:
        # Panne ou refus cote LLM : reponse propre, pas de stack trace envoyee au client.
        logger.exception("Erreur LLM")
        raise HTTPException(
            status_code=502,
            detail="Le service LLM est indisponible ou a refuse la requete. Reessaie dans un instant.",
        ) from e

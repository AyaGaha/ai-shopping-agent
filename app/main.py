import logging
from uuid import UUID, uuid4

import openai
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent import run_agent
from app.conversation_memory import ConversationMemory, ConversationNotFoundError

logger = logging.getLogger("p059")

app = FastAPI(title="P059 — Agent IA de commande")
conversation_memory = ConversationMemory()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: ChatRequest):
    is_new_conversation = payload.conversation_id is None
    conversation_id = str(payload.conversation_id or uuid4())
    history = [] if is_new_conversation else conversation_memory.load(conversation_id)

    if history is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")

    try:
        result = run_agent(
            payload.message,
            history,
            conversation_id=conversation_id,
            memory=conversation_memory,
        )
        conversation_memory.save(
            conversation_id,
            result["messages"],
            create=is_new_conversation,
        )
    except openai.APIError as e:
        # Panne ou refus cote LLM : reponse propre, pas de stack trace envoyee au client.
        logger.exception("Erreur LLM")
        raise HTTPException(
            status_code=502,
            detail="Le service LLM est indisponible ou a refuse la requete. Reessaie dans un instant.",
        ) from e
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404, detail="Conversation introuvable.") from e

    return {
        "conversation_id": conversation_id,
        "final_response": result["final_response"],
        "steps_used": result["steps_used"],
        "trace": result["trace"],
    }

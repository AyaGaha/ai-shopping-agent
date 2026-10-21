from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator
from uuid import UUID, uuid4

import openai
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent import run_agent
from app.conversation_memory import ConversationMemory, ConversationNotFoundError
from app.observability import log_event
from app.tools.search_product_tool import warm_search


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    started_at = perf_counter()
    log_event("search.model_warmup", status="loading")
    try:
        warm_search()
    except Exception as error:
        log_event(
            "search.model_warmup",
            status="error",
            error_code=type(error).__name__,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise
    log_event(
        "search.model_warmup",
        status="ready",
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    yield


app = FastAPI(title="P059 — Agent IA de commande", lifespan=lifespan)
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
    started_at = perf_counter()
    is_new_conversation = payload.conversation_id is None
    conversation_id = str(payload.conversation_id or uuid4())
    history = [] if is_new_conversation else conversation_memory.load(conversation_id)

    if history is None:
        log_event(
            "chat.request",
            conversation_id=conversation_id,
            outcome="error",
            error_code="conversation_not_found",
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
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
        log_event(
            "chat.request",
            conversation_id=conversation_id,
            outcome="error",
            error_code="llm_api_error",
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise HTTPException(
            status_code=502,
            detail="Le service LLM est indisponible ou a refuse la requete. Reessaie dans un instant.",
        ) from e
    except ConversationNotFoundError as e:
        log_event(
            "chat.request",
            conversation_id=conversation_id,
            outcome="error",
            error_code="conversation_not_found",
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise HTTPException(status_code=404, detail="Conversation introuvable.") from e

    log_event(
        "chat.request",
        conversation_id=conversation_id,
        outcome="success",
        steps_used=result["steps_used"],
        tool_count=len(result["trace"]),
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    return {
        "conversation_id": conversation_id,
        "final_response": result["final_response"],
        "steps_used": result["steps_used"],
        "trace": result["trace"],
    }

from contextlib import asynccontextmanager
import os
import re
import json
from html.parser import HTMLParser
from time import perf_counter
from typing import AsyncIterator
from uuid import UUID, uuid4
from pathlib import Path

import openai
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
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
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class _CatalogTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_product_description(value: object) -> str:
    parser = _CatalogTextParser()
    parser.feed(str(value or ""))
    return " ".join(" ".join(parser.parts).split())[:360]


def _public_image_url(value: object) -> bool:
    return isinstance(value, str) and (value.startswith("https://") or value.startswith("/")) and not value.startswith("//")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return {"max_message_length": 2000, "version": os.environ.get("APP_VERSION", "0.1.0")}


@app.get("/products")
def products():
    """Expose only public display fields from the same catalog snapshot used for indexing."""
    path = Path(__file__).resolve().parent.parent / "data" / "products.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=503, detail="Catalogue indisponible.") from error
    result = []
    for item in catalog:
        if not isinstance(item, dict) or not item.get("id") or not item.get("nom"):
            continue
        product = {
            "id": item["id"], "name": str(item["nom"])[:200], "price": item.get("prix", 0),
            "currency": item.get("devise") if isinstance(item.get("devise"), str) else None,
            "description": _plain_product_description(item.get("description", "")),
        }
        if _public_image_url(item.get("image_url")):
            product["image_url"] = item["image_url"]
        result.append(product)
    return result


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
        outcome="degraded" if result.get("degraded") else "success",
        error_code="llm_unavailable" if result.get("degraded") else None,
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


@app.middleware("http")
async def frontend_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    is_frontend = FRONTEND_DIST.is_dir() and (
        request.url.path == "/" or request.url.path.startswith(("/assets/", "/favicon"))
        or (response.headers.get("content-type", "").startswith("text/html") and request.url.path not in {"/docs", "/redoc"})
    )
    if is_frontend:
        image_hosts = [
            host for host in os.environ.get("CSP_IMAGE_HOSTS", "").split()
            if re.fullmatch(r"https://(?:[A-Za-z0-9*-]+\.)*[A-Za-z0-9*-]+(?::[0-9]{1,5})?", host)
        ]
        image_src = " ".join(["'self'", "data:", *image_hosts])
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src " + image_src + "; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; script-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'"
        )
    return response


class CachedFrontend(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404 or path.startswith(("assets/", "favicon")):
                raise
            response = await super().get_response("index.html", scope)
            path = "index.html"
        if path == "index.html":
            response.headers["Cache-Control"] = "no-cache"
        elif re.search(r"(?:^|[-.])[A-Za-z0-9_-]{8,}\.", path):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(target_app: FastAPI, directory: str | Path) -> bool:
    path = Path(directory)
    if not path.is_dir():
        return False
    target_app.mount("/", CachedFrontend(directory=str(path), html=True), name="frontend")
    return True


mount_frontend(app, FRONTEND_DIST)

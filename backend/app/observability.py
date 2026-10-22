"""Structured, privacy-conscious application events."""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("p059")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Uvicorn configures its own loggers but may leave the root logger at
    # WARNING. Give application JSON events a console handler so INFO events
    # (including LLM error diagnostics) are visible in the server terminal.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)


def log_event(event: str, **fields: object) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))

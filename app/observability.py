"""Structured, privacy-conscious application events."""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("p059")


def log_event(event: str, **fields: object) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))

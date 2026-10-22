"""SQLite-backed conversation history owned by the server."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "conversations.sqlite3"
RETENTION_DAYS = 30


class ConversationNotFoundError(Exception):
    """Raised when a client references a conversation that does not exist."""


class ConversationMemory:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.environ.get("CONVERSATION_DB_PATH", DEFAULT_DB_PATH))

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path, timeout=10)

    def load(self, conversation_id: str) -> list[dict] | None:
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                self._purge_expired(connection)
                row = connection.execute(
                    "SELECT messages FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()

        if row is None:
            return None
        messages = json.loads(row[0])
        if not isinstance(messages, list):
            raise ValueError(f"Historique invalide pour la conversation {conversation_id}")
        return messages

    def save(self, conversation_id: str, messages: list[dict], *, create: bool = False) -> None:
        serialized_messages = json.dumps(messages, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()

        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                self._purge_expired(connection, now)
                if create:
                    connection.execute(
                        """
                        INSERT INTO conversations (conversation_id, messages, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (conversation_id, serialized_messages, now, now),
                    )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE conversations
                        SET messages = ?, updated_at = ?
                        WHERE conversation_id = ?
                        """,
                        (serialized_messages, now, conversation_id),
                    )
                    if cursor.rowcount == 0:
                        raise ConversationNotFoundError(conversation_id)

    def load_order_state(self, conversation_id: str) -> dict | None:
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                self._purge_expired(connection)
                row = connection.execute(
                    """
                    SELECT order_state FROM conversation_order_state
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()

        return json.loads(row[0]) if row else None

    def update_order_state(self, conversation_id: str, update: Callable[[dict], dict]) -> dict:
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._purge_expired(connection)
                row = connection.execute(
                    """
                    SELECT order_state FROM conversation_order_state
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
                current = json.loads(row[0]) if row else {"confirmed_count": 0, "pending_order": None}
                updated = update(current)
                connection.execute(
                    """
                    INSERT INTO conversation_order_state (conversation_id, order_state)
                    VALUES (?, ?)
                    ON CONFLICT(conversation_id) DO UPDATE SET order_state = excluded.order_state
                    """,
                    (conversation_id, json.dumps(updated, ensure_ascii=False)),
                )
                connection.commit()
                return updated
            except Exception:
                connection.rollback()
                raise

    def discard_unconfirmed_proposal(self, conversation_id: str) -> bool:
        """Clear a quote when the customer switches back to product advice.

        A created WooCommerce order is never cleared here; only a proposal that
        has not caused a remote side effect can be discarded.
        """
        discarded = False

        def discard(state: dict) -> dict:
            nonlocal discarded
            pending = state.get("pending_order")
            if pending is not None and pending.get("status") == "proposed":
                discarded = True
                return {**state, "pending_order": None}
            return state

        self.update_order_state(conversation_id, discard)
        return discarded

    @staticmethod
    def _purge_expired(connection: sqlite3.Connection, now: str | None = None) -> None:
        current_time = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
        cutoff = (current_time - timedelta(days=RETENTION_DAYS)).isoformat()
        connection.execute(
            """
            DELETE FROM conversation_order_state
            WHERE conversation_id IN (
                SELECT conversation_id FROM conversations WHERE updated_at < ?
            )
            """,
            (cutoff,),
        )
        connection.execute(
            "DELETE FROM conversations WHERE updated_at < ?",
            (cutoff,),
        )

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                messages TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_order_state (
                conversation_id TEXT PRIMARY KEY,
                order_state TEXT NOT NULL
            )
            """
        )

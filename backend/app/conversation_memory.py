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


def _safe_display_trace(trace: list[dict]) -> list[dict]:
    """Keep the public event shape while stripping tool internals and arbitrary error text."""
    safe = []
    argument_fields = {
        "search_product": {"query"}, "propose_order": {"product_id", "quantity"},
        "create_order": {"product_id", "quantity"}, "confirm_order": {"order_id"},
        "cancel_order": {"order_id"},
    }
    result_fields = {
        "propose_order": {"product_id", "product_name", "quantity", "unit_price", "total", "currency", "status", "order_id"},
        "create_order": {"product_id", "product_name", "quantity", "total", "devise", "currency", "statut", "status", "order_id"},
        "confirm_order": {"order_id", "total", "devise", "currency", "statut", "status"},
        "cancel_order": {"order_id", "statut", "status"},
    }
    for event in trace:
        if not isinstance(event, dict):
            continue
        tool = event.get("tool_called")
        if tool not in argument_fields:
            continue
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        safe_result = {key: value for key, value in result.items() if key in result_fields.get(tool, set())}
        if tool == "search_product":
            found = result.get("produits_trouves", [])
            if isinstance(found, list):
                safe_result["produits_trouves"] = [
                    {key: product[key] for key in ("id", "nom", "prix", "devise", "description", "variantes", "score_similarite") if key in product}
                    for product in found if isinstance(product, dict)
                ]
            if isinstance(result.get("message"), str):
                safe_result["message"] = result["message"][:240]
        if "error" in result:
            safe_result = {"error": "Action refusée selon les règles de commande." if any(word in str(result["error"]).casefold() for word in ("refus", "bloqu", "confirmation", "confirm")) else "Action indisponible."}
        safe.append({
            "step": event.get("step") if isinstance(event.get("step"), int) else 0,
            "tool_called": tool,
            "args": {key: value for key, value in args.items() if key in argument_fields[tool]},
            "result": safe_result,
        })
    return safe


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

    def save_display_turn(self, conversation_id: str, user_text: str, assistant_text: str, trace: list[dict]) -> None:
        """Persist user-visible messages without internal prompt or tool state."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                connection.execute(
                    "INSERT INTO display_messages (conversation_id, user_text, assistant_text, trace, created_at) VALUES (?, ?, ?, ?, ?)",
                    (conversation_id, user_text, assistant_text, json.dumps(_safe_display_trace(trace), ensure_ascii=False), now),
                )

    def load_display_history(self, conversation_id: str) -> list[dict] | None:
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                self._purge_expired(connection)
                exists = connection.execute("SELECT 1 FROM conversations WHERE conversation_id = ?", (conversation_id,)).fetchone()
                if exists is None:
                    return None
                rows = connection.execute(
                    "SELECT user_text, assistant_text, trace, created_at FROM display_messages WHERE conversation_id = ? ORDER BY id",
                    (conversation_id,),
                ).fetchall()
        result = []
        for user_text, assistant_text, trace, created_at in rows:
            result.append({"role": "user", "content": user_text, "created_at": created_at})
            result.append({"role": "assistant", "content": assistant_text, "trace": json.loads(trace), "created_at": created_at})
        return result

    def delete(self, conversation_id: str) -> bool:
        with closing(self._connect()) as connection:
            self._ensure_schema(connection)
            with connection:
                cursor = connection.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
                connection.execute("DELETE FROM conversation_order_state WHERE conversation_id = ?", (conversation_id,))
                connection.execute("DELETE FROM display_messages WHERE conversation_id = ?", (conversation_id,))
        return cursor.rowcount > 0

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
            """DELETE FROM display_messages WHERE conversation_id IN
               (SELECT conversation_id FROM conversations WHERE updated_at < ?)""",
            (cutoff,),
        )
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
        connection.execute(
            """CREATE TABLE IF NOT EXISTS display_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                user_text TEXT NOT NULL, assistant_text TEXT NOT NULL, trace TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )

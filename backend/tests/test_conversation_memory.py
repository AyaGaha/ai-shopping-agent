"""SQLite conversation history persistence tests."""
import sqlite3
from datetime import datetime, timedelta, timezone

from app.conversation_memory import ConversationMemory


def test_history_survives_memory_instance_restart(tmp_path):
    db_path = tmp_path / "nested" / "conversations.sqlite3"
    messages = [
        {"role": "user", "content": "2 mugs"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "search_product", "arguments": '{"query":"mug"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"produits_trouves":[]}'},
    ]

    ConversationMemory(db_path).save("conversation-1", messages, create=True)
    restarted_memory = ConversationMemory(db_path)

    assert restarted_memory.load("conversation-1") == messages


def test_conversations_are_isolated(tmp_path):
    memory = ConversationMemory(tmp_path / "conversations.sqlite3")
    memory.save("conversation-1", [{"role": "user", "content": "A"}], create=True)
    memory.save("conversation-2", [{"role": "user", "content": "B"}], create=True)

    assert memory.load("conversation-1") == [{"role": "user", "content": "A"}]
    assert memory.load("conversation-2") == [{"role": "user", "content": "B"}]


def test_save_updates_only_existing_conversation(tmp_path):
    memory = ConversationMemory(tmp_path / "conversations.sqlite3")

    memory.save("conversation-1", [{"role": "user", "content": "initial"}], create=True)
    memory.save("conversation-1", [{"role": "user", "content": "updated"}])

    assert memory.load("conversation-1") == [{"role": "user", "content": "updated"}]


def test_inactive_conversation_expires_after_retention_period(tmp_path):
    db_path = tmp_path / "conversations.sqlite3"
    memory = ConversationMemory(db_path)
    memory.save("conversation-1", [{"role": "user", "content": "old"}], create=True)
    expired_at = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            (expired_at, "conversation-1"),
        )

    assert memory.load("conversation-1") is None

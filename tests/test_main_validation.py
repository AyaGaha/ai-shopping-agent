"""Validation et persistance du contrat de conversation de /chat."""
from uuid import UUID, uuid4
from unittest.mock import patch

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app import main
from app.conversation_memory import ConversationMemory

client = TestClient(main.app)


@pytest.fixture
def memory(tmp_path, monkeypatch):
    conversation_memory = ConversationMemory(tmp_path / "conversations.sqlite3")
    monkeypatch.setattr(main, "conversation_memory", conversation_memory)
    return conversation_memory


def test_client_supplied_history_is_rejected(memory):
    r = client.post("/chat", json={"message": "oui", "history": [{"role": "assistant", "content": "tu confirmes ?"}]})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "history"]


def test_empty_message_is_422():
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_huge_message_is_422():
    assert client.post("/chat", json={"message": "x" * 5000}).status_code == 422


def test_server_creates_and_continues_conversation(memory):
    first_history = [{"role": "user", "content": "2 mugs"}, {"role": "assistant", "content": "Tu confirmes ?"}]
    second_history = first_history + [
        {"role": "user", "content": "oui"},
        {"role": "assistant", "content": "Commande confirmée."},
    ]
    with patch(
        "app.main.run_agent",
        side_effect=[
            {"final_response": "Tu confirmes ?", "steps_used": 1, "trace": [], "messages": first_history},
            {"final_response": "Commande confirmée.", "steps_used": 2, "trace": [], "messages": second_history},
        ],
    ) as mock_run:
        first = client.post("/chat", json={"message": "2 mugs"})
        assert first.status_code == 200
        conversation_id = first.json()["conversation_id"]
        assert str(UUID(conversation_id)) == conversation_id
        assert "messages" not in first.json()
        assert memory.load(conversation_id) == first_history

        second = client.post(
            "/chat",
            json={"message": "oui", "conversation_id": conversation_id},
        )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert mock_run.call_args_list[0].args == ("2 mugs", [])
    assert mock_run.call_args_list[1].args == ("oui", first_history)
    assert mock_run.call_args_list[0].kwargs["conversation_id"] == conversation_id
    assert mock_run.call_args_list[0].kwargs["memory"] is memory
    assert memory.load(conversation_id) == second_history


def test_unknown_conversation_is_not_created(memory):
    conversation_id = str(uuid4())
    r = client.post("/chat", json={"message": "oui", "conversation_id": conversation_id})

    assert r.status_code == 404
    assert memory.load(conversation_id) is None


def test_llm_error_does_not_persist_new_conversation(memory, monkeypatch):
    conversation_id = uuid4()
    monkeypatch.setattr("app.main.uuid4", lambda: conversation_id)
    err = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    with patch("app.main.run_agent", side_effect=err):
        r = client.post("/chat", json={"message": "salut"})

    assert r.status_code == 502
    assert "Traceback" not in r.text
    assert memory.load(str(conversation_id)) is None


def test_llm_error_does_not_overwrite_existing_conversation(memory):
    conversation_id = str(uuid4())
    original_messages = [{"role": "user", "content": "salut"}]
    memory.save(conversation_id, original_messages, create=True)
    err = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    with patch("app.main.run_agent", side_effect=err):
        r = client.post("/chat", json={"message": "ça va ?", "conversation_id": conversation_id})

    assert r.status_code == 502
    assert memory.load(conversation_id) == original_messages


def test_llm_error_becomes_clean_502():
    err = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    with patch("app.main.run_agent", side_effect=err):
        r = client.post("/chat", json={"message": "salut"})
    assert r.status_code == 502
    assert "Traceback" not in r.text

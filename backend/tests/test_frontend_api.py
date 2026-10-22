"""Public, display-safe endpoints used by the SPA."""
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app, mount_frontend
from app.conversation_memory import ConversationMemory
from app.guardrail_rules import has_explicit_cancellation, has_explicit_confirmation

client = TestClient(app)


def test_frontend_config_reports_chat_limit_and_version():
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json()["max_message_length"] == 2000
    assert response.json()["version"]


def test_public_catalog_contains_only_display_fields_and_plain_text():
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json()
    first = response.json()[0]
    assert {"id", "name", "price", "currency", "description"} <= first.keys()
    assert "<" not in first["description"]
    assert "system_prompt" not in first


def test_display_history_keeps_trace_shape_but_filters_internal_result_fields(tmp_path):
    memory = ConversationMemory(tmp_path / "chat.sqlite3")
    memory.save("history-safe", [], create=True)
    memory.save_display_turn("history-safe", "mug please", "I found a mug.", [{
        "step": 2, "tool_called": "search_product", "args": {"query": "mug please", "secret": "hidden"},
        "result": {"produits_trouves": [{"id": "21", "nom": "Mug", "prix": "9.9", "private": "hidden"}], "internal_prompt": "hidden"},
    }])

    history = memory.load_display_history("history-safe")
    assert history is not None and [item["role"] for item in history] == ["user", "assistant"]
    trace = history[1]["trace"][0]
    assert set(trace) == {"step", "tool_called", "args", "result"}
    assert trace["args"] == {"query": "mug please"}
    assert "internal_prompt" not in trace["result"]
    assert "private" not in trace["result"]["produits_trouves"][0]
    assert memory.delete("history-safe") is True
    assert memory.load_display_history("history-safe") is None


def test_spa_static_mount_falls_back_and_sets_cache_headers(tmp_path):
    target = tmp_path / "dist"
    (target / "assets").mkdir(parents=True)
    (target / "index.html").write_text("<main>Shopping Agent</main>", encoding="utf-8")
    (target / "assets" / "index-Abcdef123456.js").write_text("void 0", encoding="utf-8")
    test_app = FastAPI()
    assert mount_frontend(test_app, target) is True
    response = TestClient(test_app).get("/nested/client-route")
    assert response.status_code == 200 and "Shopping Agent" in response.text
    assert response.headers["cache-control"] == "no-cache"
    hashed = TestClient(test_app).get("/assets/index-Abcdef123456.js")
    assert "immutable" in hashed.headers["cache-control"]


def test_spa_mount_is_a_noop_when_dist_is_missing(tmp_path):
    test_app = FastAPI()
    assert mount_frontend(test_app, tmp_path / "absent") is False
    assert not any(route.name == "frontend" for route in test_app.routes)


def test_frontend_confirmation_and_cancellation_phrases_are_accepted():
    assert has_explicit_confirmation("oui je confirme la commande")
    assert has_explicit_confirmation("i confirm the order")
    assert has_explicit_cancellation("annule la commande")
    assert has_explicit_cancellation("cancel the order")

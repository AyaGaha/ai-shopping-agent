import json
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import httpx
import openai

from app import agent
from app.llm_client import LLM_TIMEOUT_SECONDS, get_client


def _connection_error():
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://api.example.test/chat")
    )


def _bad_request_error():
    request = httpx.Request("POST", "https://api.example.test/chat")
    return openai.BadRequestError(
        "invalid request",
        response=httpx.Response(400, request=request),
        body={"error": {"code": "tool_use_failed"}},
    )


def _rate_limit_error():
    request = httpx.Request("POST", "https://api.example.test/chat")
    return openai.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=request),
        body={"error": {"code": "rate_limit_exceeded"}},
    )


def _tool_message(name, arguments):
    call = NS(
        id="tool-call-1",
        function=NS(name=name, arguments=json.dumps(arguments)),
    )
    return NS(
        content=None,
        tool_calls=[call],
        model_dump=lambda exclude_none=True: {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tool-call-1",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        },
    )


def _response(message):
    return NS(choices=[NS(message=message)])


def test_llm_client_uses_bounded_timeout_and_agent_managed_retries(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    with patch("app.llm_client.OpenAI") as openai_client:
        get_client()

    kwargs = openai_client.call_args.kwargs
    assert kwargs["timeout"] == LLM_TIMEOUT_SECONDS
    assert kwargs["max_retries"] == 0


def test_transient_llm_error_retries_then_succeeds():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _connection_error(),
        _response(NS(content="Bonjour !", tool_calls=None)),
    ]
    with (
        patch.object(agent, "get_client", return_value=client),
        patch.object(agent, "get_model", return_value="test-model"),
        patch.object(agent, "sleep") as sleep,
    ):
        result = agent.run_agent("Bonjour")

    assert client.chat.completions.create.call_count == 2
    sleep.assert_called_once_with(1.0)
    assert result["final_response"] == "Bonjour !"
    assert not result.get("degraded")


def test_llm_429_retries_with_bounded_backoff_then_succeeds():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _rate_limit_error(),
        _rate_limit_error(),
        _response(NS(content="Bonjour !", tool_calls=None)),
    ]
    with (
        patch.object(agent, "get_client", return_value=client),
        patch.object(agent, "get_model", return_value="test-model"),
        patch.object(agent, "sleep") as sleep,
    ):
        result = agent.run_agent("Bonjour")

    assert client.chat.completions.create.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1.0, 2.0]
    assert result["final_response"] == "Bonjour !"
    assert not result.get("degraded")


def test_non_retryable_llm_400_returns_fallback_without_retry():
    client = MagicMock()
    client.chat.completions.create.side_effect = _bad_request_error()
    with (
        patch.object(agent, "get_client", return_value=client),
        patch.object(agent, "get_model", return_value="test-model"),
        patch.object(agent, "sleep") as sleep,
    ):
        result = agent.run_agent("Bonjour")

    assert client.chat.completions.create.call_count == 1
    sleep.assert_not_called()
    assert result["degraded"] is True
    assert "temporairement indisponible" in result["final_response"]
    assert result["messages"][-1] == {
        "role": "assistant",
        "content": result["final_response"],
    }


def test_exhausted_transient_errors_use_catalog_grounded_fallback():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _response(_tool_message("search_product", {"query": "t-shirt"})),
        _connection_error(),
        _connection_error(),
        _connection_error(),
    ]
    products = [
        {
            "id": "16",
            "nom": "T-shirt coton bio",
            "prix": 19.9,
            "devise": "TND",
        }
    ]
    with (
        patch.object(agent, "get_client", return_value=client),
        patch.object(agent, "get_model", return_value="test-model"),
        patch.object(agent, "sleep"),
        patch.dict(
            agent.TOOLS_REGISTRY,
            {"search_product": lambda query: {"produits_trouves": products}},
        ),
    ):
        result = agent.run_agent("Je cherche un t-shirt")

    assert client.chat.completions.create.call_count == 4
    assert result["degraded"] is True
    assert "T-shirt coton bio" in result["final_response"]
    assert "19.9 TND" in result["final_response"]
    assert "id 16" in result["final_response"]


def test_fallback_reports_created_order_as_pending_not_confirmed():
    response = agent._llm_unavailable_fallback(
        [
            {
                "tool_called": "create_order",
                "result": {
                    "order_id": 42,
                    "statut": "commande_creee_en_attente_de_confirmation",
                },
            }
        ]
    )

    assert "n°42" in response
    assert "en attente de confirmation" in response
    assert "n’a pas pu être terminée" in response

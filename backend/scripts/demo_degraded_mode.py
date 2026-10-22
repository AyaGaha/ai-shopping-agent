"""Demonstrate the production agent fallback without calling Groq or WooCommerce."""
import json
from unittest.mock import MagicMock, patch

import httpx
import openai

from app import agent


def main() -> int:
    client = MagicMock()
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    client.chat.completions.create.side_effect = openai.APIConnectionError(request=request)

    with (
        patch.object(agent, "get_client", return_value=client),
        patch.object(agent, "get_model", return_value="demo-model"),
        patch.object(agent, "sleep"),
    ):
        result = agent.run_agent("Bonjour")

    summary = {
        "scenario": "LLM connection failure on every attempt",
        "attempt_count": client.chat.completions.create.call_count,
        "degraded": result.get("degraded", False),
        "fallback": result["final_response"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("degraded") and client.chat.completions.create.call_count == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())

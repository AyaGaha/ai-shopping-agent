"""
Tests du hello world.

- test_get_current_time_tool : valide l'outil seul, sans appel LLM (pas besoin de clé API).
- test_agent_end_to_end_live : valide la vraie boucle function calling, nécessite GROQ_API_KEY.
  Ignoré automatiquement si la clé n'est pas définie (utile en CI ou en review de code).
"""
import os

import pytest

from app.tools.hello_tool import get_current_time


def test_get_current_time_tool():
    result = get_current_time("Europe/Paris")
    assert "utc_time" in result
    assert result["timezone_requested"] == "Europe/Paris"


@pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="Nécessite une clé GROQ_API_KEY pour un test de bout en bout réel",
)
def test_agent_end_to_end_live():
    from app.agent import run_agent

    result = run_agent("Quelle heure est-il ?")
    assert "final_response" in result
    assert result["steps_used"] >= 1

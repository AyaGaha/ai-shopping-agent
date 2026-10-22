"""
Regression : la reponse finale de l'agent doit figurer dans `messages`, sinon le tour
suivant ("oui, confirme") se fait sans que le LLM voie le recapitulatif qu'il a propose.
LLM simule : aucune cle API necessaire.
"""
import json
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from app import agent


class FakeMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        d = {"role": "assistant"}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
                for t in self.tool_calls
            ]
        return d


def _fake_client(*messages):
    client = MagicMock()
    client.chat.completions.create.side_effect = [NS(choices=[NS(message=m)]) for m in messages]
    return client


def test_final_answer_is_kept_in_history():
    client = _fake_client(FakeMsg(content="Recap : 2 mugs, 19.80. Tu confirmes ?"))
    with patch.object(agent, "get_client", return_value=client), patch.object(agent, "get_model", return_value="m"):
        result = agent.run_agent("I want 2 mugs")
    assert result["messages"][-1] == {"role": "assistant", "content": "Recap : 2 mugs, 19.80. Tu confirmes ?"}


def test_history_after_tool_call_ends_with_final_answer():
    call = NS(id="c1", function=NS(name="search_product", arguments=json.dumps({"query": "mug"})))
    client = _fake_client(FakeMsg(tool_calls=[call]), FakeMsg(content="Voici le mug, tu confirmes ?"))
    with patch.object(agent, "get_client", return_value=client), patch.object(agent, "get_model", return_value="m"), \
         patch.dict(agent.TOOLS_REGISTRY, {"search_product": lambda query: {"produits_trouves": []}}):
        result = agent.run_agent("mug ?")
    roles = [m["role"] for m in result["messages"]]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert result["messages"][-1]["content"] == "Voici le mug, tu confirmes ?"

"""
Boucle d'agent (Thought -> Action -> Observation) avec 4 outils :
search_product, create_order, confirm_order, cancel_order (WooCommerce).

NOTE (interim, avant B.4) : `history` permet au client de renvoyer les messages
precedents, pour que la confirmation en 2 temps fonctionne des maintenant, meme
sans ConversationMemory persistante cote serveur. A remplacer par une vraie
memoire serveur en B.4.
"""
import json

from app.llm_client import get_client, get_model
from app.tools.order_tools import TOOL_SCHEMAS as ORDER_SCHEMAS, TOOLS_REGISTRY as ORDER_TOOLS
from app.tools.search_product_tool import TOOL_SCHEMA as SEARCH_SCHEMA, TOOLS_REGISTRY as SEARCH_TOOLS

MAX_STEPS = 6

SYSTEM_PROMPT = (
    "Tu es un agent d'assistance a l'achat. Tu disposes de 4 outils :\n"
    "- search_product : pour trouver un produit dans le catalogue\n"
    "- create_order : pour preparer une commande (statut 'pending', reversible)\n"
    "- confirm_order : pour CONFIRMER une commande (irreversible)\n"
    "- cancel_order : pour annuler une commande en attente\n\n"
    "REGLE ABSOLUE : n'appelle JAMAIS confirm_order sans que le client ait "
    "explicitement confirme dans un message precedent (ex: 'oui', 'confirme', "
    "'vas-y'). Apres create_order, presente toujours le recapitulatif "
    "(produit, quantite, prix total) et demande confirmation avant de continuer."
)

TOOLS = [SEARCH_SCHEMA] + ORDER_SCHEMAS
TOOLS_REGISTRY = {**SEARCH_TOOLS, **ORDER_TOOLS}


def run_agent(user_message: str, history: list[dict] | None = None) -> dict:
    client = get_client()
    model = get_model()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})

    trace = []

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
        )
        choice = response.choices[0].message

        if choice.tool_calls:
            messages.append(choice.model_dump(exclude_none=True))

            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments or "{}")
                tool_fn = TOOLS_REGISTRY.get(tool_name)

                try:
                    result = tool_fn(**tool_args) if tool_fn else {"error": f"Outil inconnu: {tool_name}"}
                except Exception as e:
                    result = {"error": str(e)}

                trace.append({"step": step, "tool_called": tool_name, "args": tool_args, "result": result})

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            continue

        return {
            "final_response": choice.content,
            "steps_used": step + 1,
            "trace": trace,
            "messages": messages[1:],
        }

    return {
        "final_response": "Nombre max d'etapes atteint sans conclure.",
        "steps_used": MAX_STEPS,
        "trace": trace,
        "messages": messages[1:],
    }

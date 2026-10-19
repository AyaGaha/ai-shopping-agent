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
    "Tu es un agent d'assistance a l'achat. Outils : search_product, create_order, "
    "confirm_order, cancel_order.\n\n"
    "DEROULEMENT D'UNE COMMANDE :\n"
    "1. Cherche le produit avec search_product.\n"
    "2. Presente un recapitulatif (produit, quantite, prix total) et demande une "
    "confirmation explicite. N'appelle PAS create_order a ce stade.\n"
    "3. Seulement apres un message du client qui confirme clairement (ex : 'oui', "
    "'confirme', 'yes', 'vas-y'), appelle create_order puis, avec l'order_id obtenu, "
    "confirm_order, puis annonce le numero de commande.\n"
    "4. Si le client refuse ou hesite, n'appelle aucun outil de commande.\n\n"
    "REGLE ABSOLUE : ne cree et ne confirme jamais une commande sans confirmation "
    "explicite du client dans son dernier message. N'affirme sur un produit que ce qui "
    "figure dans les resultats des outils ; si une information manque, dis que tu ne la connais pas.\n"
    "DEVISE : les prix sont dans la devise indiquee par le champ 'devise' (ou 'currency') des "
    "resultats d'outils. Si aucune devise n'est indiquee, n'ecris aucun symbole de devise "
    "(ni euro, ni dollar)."
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

        # La reponse finale DOIT faire partie de l'historique renvoye : sinon, au tour suivant,
        # le LLM ne voit pas le recapitulatif qu'il vient de proposer ni la question de confirmation.
        messages.append({"role": "assistant", "content": choice.content})
        return {
            "final_response": choice.content,
            "steps_used": step + 1,
            "trace": trace,
            "messages": messages[1:],
        }

    fallback = "Nombre max d'etapes atteint sans conclure."
    messages.append({"role": "assistant", "content": fallback})
    return {
        "final_response": fallback,
        "steps_used": MAX_STEPS,
        "trace": trace,
        "messages": messages[1:],
    }

"""
Boucle d'agent minimale — la même structure que ton diagramme d'activités
(Thought -> Action -> Observation, répété jusqu'à conclusion ou max étapes),
mais avec un seul outil factice pour l'instant.
"""
import json

from app.llm_client import get_client, get_model
from app.tools.hello_tool import TOOL_SCHEMA, TOOLS_REGISTRY

MAX_STEPS = 4

SYSTEM_PROMPT = (
    "Tu es l'agent de démonstration du projet P059. "
    "Tu disposes d'un seul outil pour l'instant : get_current_time. "
    "Utilise-le uniquement si c'est pertinent pour répondre à la demande, "
    "sinon réponds directement en langage naturel."
)


def run_agent(user_message: str) -> dict:
    """Exécute la boucle d'agent et renvoie la réponse finale + une trace des étapes."""
    client = get_client()
    model = get_model()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    trace = []

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[TOOL_SCHEMA],
        )
        choice = response.choices[0].message

        if choice.tool_calls:
            # Le LLM a décidé d'appeler un outil : on exécute, on observe, on reboucle.
            messages.append(choice.model_dump(exclude_none=True))

            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments or "{}")
                tool_fn = TOOLS_REGISTRY.get(tool_name)

                if tool_fn is None:
                    result = {"error": f"Outil inconnu: {tool_name}"}
                else:
                    result = tool_fn(**tool_args)

                trace.append({"step": step, "tool_called": tool_name, "args": tool_args, "result": result})

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
            continue

        # Pas d'appel d'outil -> réponse directe, on sort de la boucle.
        return {
            "final_response": choice.content,
            "steps_used": step + 1,
            "trace": trace,
        }

    # Nombre max d'étapes atteint sans conclure (cf. ton diagramme de workflow).
    return {
        "final_response": "Nombre max d'étapes atteint sans conclure.",
        "steps_used": MAX_STEPS,
        "trace": trace,
    }

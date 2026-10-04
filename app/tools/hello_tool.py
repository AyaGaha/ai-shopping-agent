"""
Outil de démonstration ("hello world").

But unique : valider que la boucle Thought -> Action -> Observation
(function calling) fonctionne de bout en bout, AVANT de brancher les
vrais outils du projet (SearchProductTool, PlaceOrderTool).

Ne fait rien d'utile en soi — c'est voulu.
"""
from datetime import datetime, timezone


def get_current_time(timezone_name: str = "UTC") -> dict:
    """Renvoie l'heure UTC actuelle (simple, déterministe, facile à vérifier)."""
    now = datetime.now(timezone.utc)
    return {
        "utc_time": now.isoformat(),
        "timezone_requested": timezone_name,
    }


# Schéma function calling (format OpenAI/Groq) décrivant l'outil au LLM.
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": (
            "Renvoie l'heure UTC actuelle. À utiliser uniquement si "
            "l'utilisateur demande explicitement l'heure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone_name": {
                    "type": "string",
                    "description": "Fuseau horaire mentionné par l'utilisateur (informatif ici).",
                }
            },
            "required": [],
        },
    },
}

# Registre nom -> fonction Python réelle (ToolRegistry simplifié pour le hello world).
TOOLS_REGISTRY = {
    "get_current_time": get_current_time,
}

"""
Les deux outils de commande, sur WooCommerce — remplace les outils Shopify.

Plus simple que le flux Shopify draftOrderCreate/draftOrderComplete : WooCommerce
cree une vraie commande en un seul appel. On garde quand meme le decoupage en
deux etapes (create_order -> statut "pending", confirm_order -> statut
"processing") pour preserver EXACTEMENT la logique de confirmation de ton
diagramme d'etats-transitions : rien ne doit etre finalise avant un "oui"
explicite du client, meme si l'API elle-meme le permettrait en un appel.
"""
from app.woocommerce_client import WooCommerceRequestError, get, post, put


def create_order(product_id: int, quantity: int) -> dict:
    """Cree une commande en statut 'pending' -- rien n'est facture, facilement annulable."""
    payload = {
        "payment_method": "bacs",
        "payment_method_title": "Virement (simulation)",
        "set_paid": False,
        "status": "pending",
        "line_items": [
            {"product_id": product_id, "quantity": quantity},
        ],
    }
    order = post("orders", payload)

    return {
        "order_id": order["id"],
        "total": order["total"],
        "statut": "commande_creee_en_attente_de_confirmation",
    }


def confirm_order(order_id: int) -> dict:
    """Finalise la commande (statut -> processing). ACTION IRREVERSIBLE -- a n'appeler
    qu'apres confirmation explicite du client, jamais automatiquement."""
    order = put(f"orders/{order_id}", {"status": "processing", "set_paid": True})

    return {
        "order_id": order["id"],
        "statut_woocommerce": order["status"],
        "statut": "commande_confirmee",
    }


def cancel_order(order_id: int) -> dict:
    """Annule une commande en attente (si le client refuse la confirmation)."""
    order = put(f"orders/{order_id}", {"status": "cancelled"})
    return {
        "order_id": order["id"],
        "statut": "commande_annulee",
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": (
                "Cree une commande en statut PENDING (rien n'est facture, reversible). "
                "A utiliser pour preparer une commande AVANT de demander confirmation au client. "
                "Ne confirme jamais la commande toi-meme."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "L'identifiant du produit WooCommerce, obtenu via search_product.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantite souhaitee.",
                    },
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order",
            "description": (
                "Finalise une commande en attente. ACTION IRREVERSIBLE. "
                "N'appelle CET outil QUE si le client a explicitement confirme dans son dernier message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "L'identifiant de la commande a confirmer, renvoye par create_order.",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Annule une commande en attente, si le client refuse ou change d'avis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "L'identifiant de la commande a annuler."},
                },
                "required": ["order_id"],
            },
        },
    },
]

TOOLS_REGISTRY = {
    "create_order": create_order,
    "confirm_order": confirm_order,
    "cancel_order": cancel_order,
}

"""
Test de fumee SANS LLM : verifie que ta boutique WooCommerce repond et que
create_order / confirm_order / cancel_order marchent pour de vrai.

    python scripts/smoke_test_orders.py            # cree une commande puis l'ANNULE
    python scripts/smoke_test_orders.py --confirm  # cree puis CONFIRME (statut processing)

Regarde ensuite WooCommerce > Orders dans l'admin : la commande doit y apparaitre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.tools.order_tools import cancel_order, confirm_order, create_order  # noqa: E402
from app.woocommerce_client import get  # noqa: E402


def main():
    products = get("products", params={"per_page": 1, "status": "publish"})
    if not products:
        print("Aucun produit publie dans WooCommerce : ajoutes-en un d'abord.")
        sys.exit(1)

    p = products[0]
    print(f"Produit teste : #{p['id']} {p['name']} (prix {p.get('price')})")

    order = create_order(p["id"], 1)
    print("create_order  ->", order)

    if "--confirm" in sys.argv:
        print("confirm_order ->", confirm_order(order["order_id"]))
    else:
        print("cancel_order  ->", cancel_order(order["order_id"]))


if __name__ == "__main__":
    main()

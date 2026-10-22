# """
# Récupère les produits réels depuis ta boutique WooCommerce et les écrit dans
# data/products.json, avec les vrais product_id (entiers) nécessaires à
# create_order(). Lance ÇA avant index_catalog.py, une fois ta boutique en place.

#     python scripts/sync_woocommerce_catalog.py
#     python scripts/index_catalog.py
# """
# import html
# import json
# import re
# import sys
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent.parent))  # permet `from app...` depuis scripts/

# from dotenv import load_dotenv

# load_dotenv()

# from app.woocommerce_client import get  # noqa: E402

# OUTPUT_PATH = Path(__file__).parent.parent / "data" / "products.json"


# def clean_html(text: str) -> str:
#     """WooCommerce renvoie des descriptions en HTML (<p>...</p>) : on garde le texte seul."""
#     text = re.sub(r"<[^>]+>", " ", text or "")
#     return re.sub(r"\s+", " ", html.unescape(text)).strip()


# def main():
#     products = get("products", params={"per_page": 50, "status": "publish"})

#     catalogue = []
#     for p in products:
#         catalogue.append(
#             {
#                 "id": p["id"],  # entier WooCommerce, utilisé tel quel par create_order
#                 "nom": p["name"],
#                 "description": clean_html(p.get("short_description") or p.get("description") or ""),
#                 "prix": float(p["price"]) if p.get("price") else 0.0,
#                 "variantes": [],  # produits simples pour l'instant — pas de variations WooCommerce
#             }
#         )

#     with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
#         json.dump(catalogue, f, ensure_ascii=False, indent=2)

#     print(f"{len(catalogue)} produits synchronisés depuis WooCommerce vers {OUTPUT_PATH}")
#     print("N'oublie pas de relancer : python scripts/index_catalog.py")


# if __name__ == "__main__":
#     main()

"""
Récupère les produits réels depuis ta boutique WooCommerce et les écrit dans
data/products.json, avec les vrais product_id (entiers) nécessaires à
create_order(). Lance ÇA avant index_catalog.py, une fois ta boutique en place.

    python scripts/sync_woocommerce_catalog.py
    python scripts/index_catalog.py
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # permet `from app...` depuis scripts/

from dotenv import load_dotenv

load_dotenv()

from app.woocommerce_client import get  # noqa: E402

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "products.json"


def clean_html(text: str) -> str:
    """WooCommerce renvoie des descriptions en HTML (<p>...</p>) : on garde le texte seul."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def get_currency() -> str:
    """Code devise de la boutique (ex: TND). Si introuvable : avertissement, prix sans devise."""
    try:
        return get("data/currencies/current").get("code", "")
    except Exception as e:  # noqa: BLE001
        print(f"AVERTISSEMENT : devise non recuperee ({e}). Les prix seront affiches sans devise.")
        return ""


def main():
    currency = get_currency()
    products = get("products", params={"per_page": 50, "status": "publish"})

    catalogue = []
    for p in products:
        catalogue.append(
            {
                "id": p["id"],  # entier WooCommerce, utilisé tel quel par create_order
                "nom": p["name"],
                "description": clean_html(p.get("short_description") or p.get("description") or ""),
                "prix": float(p["price"]) if p.get("price") else 0.0,
                "devise": currency,
                "variantes": [],  # produits simples pour l'instant — pas de variations WooCommerce
            }
        )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, ensure_ascii=False, indent=2)

    print(f"{len(catalogue)} produits synchronisés depuis WooCommerce vers {OUTPUT_PATH}")
    print("N'oublie pas de relancer : python scripts/index_catalog.py")


if __name__ == "__main__":
    main()

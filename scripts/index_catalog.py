"""
Indexe data/products.json dans une collection ChromaDB persistante.

À relancer à chaque fois que le catalogue change :
    python scripts/index_catalog.py

Ne fait PAS partie de la boucle agent — c'est une étape de préparation
hors-ligne (ingestion), comme le prévoit ton CDC ("indexation, base vectorielle").
"""
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

DATA_PATH = Path(__file__).parent.parent / "data" / "products.json"
CHROMA_PATH = Path(__file__).parent.parent / "chroma_data"
COLLECTION_NAME = "products"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # léger, rapide, suffisant pour ce périmètre


def build_document(product: dict) -> str:
    """Texte à encoder : concatène nom + description, c'est ce sur quoi la recherche sémantique s'appuie."""
    return f"{product['nom']}. {product['description']}"


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        products = json.load(f)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    # Repart propre à chaque indexation pour éviter les doublons si le script est relancé.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)

    collection.add(
        ids=[p["id"] for p in products],
        documents=[build_document(p) for p in products],
        metadatas=[
            {"nom": p["nom"], "prix": p["prix"], "variantes": ",".join(p["variantes"])}
            for p in products
        ],
    )

    print(f"{len(products)} produits indexés dans {CHROMA_PATH} (collection '{COLLECTION_NAME}').")


if __name__ == "__main__":
    main()

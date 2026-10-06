"""
Premier vrai outil du projet. Remplace hello_tool.py.

Même format que l'outil factice (fonction + TOOL_SCHEMA + TOOLS_REGISTRY)
pour qu'agent.py n'ait quasiment rien à changer.
"""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(__file__).parent.parent.parent / "chroma_data"
COLLECTION_NAME = "products"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_collection = None  # chargé une seule fois (lazy), pas à chaque appel


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        try:
            _collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
        except Exception as e:
            raise RuntimeError(
                "Collection ChromaDB introuvable. As-tu lancé `python scripts/index_catalog.py` avant ?"
            ) from e
    return _collection


def search_product(query: str, k: int = 3) -> dict:
    """Recherche sémantique dans le catalogue produits. Renvoie les k produits les plus proches."""
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=k)

    products = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        products.append(
            {
                "id": results["ids"][0][i],
                "nom": meta["nom"],
                "prix": meta["prix"],
                "variantes": meta["variantes"].split(",") if meta["variantes"] else [],
                "score_similarite": round(1 - results["distances"][0][i], 3),
            }
        )

    if not products:
        return {"produits_trouves": [], "message": "Aucun produit ne correspond à cette recherche."}

    return {"produits_trouves": products}


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_product",
        "description": (
            "Recherche des produits dans le catalogue à partir d'une description en langage naturel "
            "(ex: 'un t-shirt noir', 'quelque chose pour boire chaud'). Renvoie les produits les plus pertinents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Ce que l'utilisateur cherche, reformulé si besoin pour la recherche.",
                },
                "k": {
                    "type": "integer",
                    "description": "Nombre de résultats à renvoyer (par défaut 3).",
                },
            },
            "required": ["query"],
        },
    },
}

TOOLS_REGISTRY = {
    "search_product": search_product,
}

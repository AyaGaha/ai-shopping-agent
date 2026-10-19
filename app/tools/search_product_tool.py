# """
# Premier vrai outil du projet. Remplace hello_tool.py.

# Même format que l'outil factice (fonction + TOOL_SCHEMA + TOOLS_REGISTRY)
# pour qu'agent.py n'ait quasiment rien à changer.
# """
# from pathlib import Path

# import chromadb
# from chromadb.utils import embedding_functions

# CHROMA_PATH = Path(__file__).parent.parent.parent / "chroma_data"
# COLLECTION_NAME = "products"
# EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# _collection = None  # chargé une seule fois (lazy), pas à chaque appel


# def _get_collection():
#     global _collection
#     if _collection is None:
#         client = chromadb.PersistentClient(path=str(CHROMA_PATH))
#         embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
#         try:
#             _collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
#         except Exception as e:
#             raise RuntimeError(
#                 "Collection ChromaDB introuvable. As-tu lancé `python scripts/index_catalog.py` avant ?"
#             ) from e
#     return _collection


# def search_product(query: str, k: int = 3) -> dict:
#     """Recherche sémantique dans le catalogue produits. Renvoie les k produits les plus proches."""
#     collection = _get_collection()
#     results = collection.query(query_texts=[query], n_results=k)

#     products = []
#     for i in range(len(results["ids"][0])):
#         meta = results["metadatas"][0][i]
#         products.append(
#             {
#                 "id": results["ids"][0][i],
#                 "nom": meta["nom"],
#                 "prix": meta["prix"],
#                 "variantes": meta["variantes"].split(",") if meta["variantes"] else [],
#                 "score_similarite": round(1 - results["distances"][0][i], 3),
#             }
#         )

#     if not products:
#         return {"produits_trouves": [], "message": "Aucun produit ne correspond à cette recherche."}

#     return {"produits_trouves": products}


# TOOL_SCHEMA = {
#     "type": "function",
#     "function": {
#         "name": "search_product",
#         "description": (
#             "Recherche des produits dans le catalogue à partir d'une description en langage naturel "
#             "(ex: 'un t-shirt noir', 'quelque chose pour boire chaud'). Renvoie les produits les plus pertinents."
#         ),
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "query": {
#                     "type": "string",
#                     "description": "Ce que l'utilisateur cherche, reformulé si besoin pour la recherche.",
#                 },
#                 "k": {
#                     "type": "integer",
#                     "description": "Nombre de résultats à renvoyer (par défaut 3).",
#                 },
#             },
#             "required": ["query"],
#         },
#     },
# }

# TOOLS_REGISTRY = {
#     "search_product": search_product,
# }
"""
Recherche sémantique dans le catalogue WooCommerce via ChromaDB.
"""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(__file__).parent.parent.parent / "chroma_data"
COLLECTION_NAME = "products"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Nombre maximal de candidats et seuil initial à ajuster après les tests.
MAX_RESULTS = 10
MIN_DISTANCE = 0.7

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embedding_fn = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
        )
        try:
            _collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
            )
        except Exception as e:
            raise RuntimeError(
                "Collection ChromaDB introuvable. "
                "Lance `python scripts/index_catalog.py`."
            ) from e
    return _collection


def search_product(query: str, k: int = 3) -> dict:
    """Recherche des produits pertinents, sans imposer trois résultats."""
    collection = _get_collection()
    total = collection.count()

    if total == 0:
        return {
            "produits_trouves": [],
            "message": "Le catalogue ne contient aucun produit indexé.",
        }

    # k reste accepté pour compatibilité avec les appels existants.
    if k < 1:
        raise ValueError("k doit être supérieur ou égal à 1.")
    limit = min(k, MAX_RESULTS, total)

    results = collection.query(
        query_texts=[query],
        n_results=limit,
        include=["metadatas", "distances"],
    )

    products = []
    for product_id, meta, distance in zip(
        results["ids"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        if distance > MIN_DISTANCE:
            continue

        # products.append({
        #     "id": str(product_id),
        #     "nom": meta["nom"],
        #     "prix": meta["prix"],
        #     "variantes": (
        #         meta["variantes"].split(",")
        #         if meta["variantes"]
        #         else []
        #     ),
        #     "distance": round(float(distance), 4),
        #     "description": meta.get("description", ""),
        #     "devise": meta.get("devise", ""),
        # })

        distance = float(distance)

        products.append({
            "id": str(product_id),
            "nom": meta["nom"],
            "prix": meta["prix"],
            "variantes": (
                meta["variantes"].split(",")
                if meta["variantes"]
                else []
            ),
            "distance": round(distance, 4),
            "score_similarite": round(1 / (1 + distance), 3),
            "description": meta.get("description", ""),
            "devise": meta.get("devise", ""),
        })

    if not products:
        return {
            "produits_trouves": [],
            "message": "Aucun produit suffisamment pertinent trouvé.",
        }

    return {"produits_trouves": products}


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_product",
        "description": (
            "Recherche les produits les plus pertinents du catalogue "
            "à partir d'une description en langage naturel. "
            "Retourne uniquement les résultats qui passent le seuil "
            "de pertinence."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Description du produit recherché.",
                },
                "k": {
                    "type": "integer",
                    "description": "Paramètre conservé pour compatibilité.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOLS_REGISTRY = {
    "search_product": search_product,
}

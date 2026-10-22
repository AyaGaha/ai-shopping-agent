"""Compare embedding models on the same catalog and retrieval evaluation set.

Each model gets a fresh ephemeral Chroma collection. The production
``chroma_data/products`` collection is never opened or modified.
"""
import argparse
import gc
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate import DEFAULT_DATASET, _load_dataset, _retrieval_metrics
from scripts.index_catalog import build_document

DEFAULT_PRODUCTS = PROJECT_ROOT / "data" / "products.json"
DEFAULT_MODELS = (
    "all-MiniLM-L6-v2",
    "paraphrase-multilingual-MiniLM-L12-v2",
)
DEFAULT_THRESHOLDS = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


def _collection_name(model_name: str) -> str:
    # Chroma collection names have a restricted character set and length.
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", model_name).strip("-").lower()
    return f"eval-{slug}"[:63].rstrip("-")


def _benchmark_model(
    model_name: str,
    products: list[dict],
    cases: list[dict],
    thresholds: tuple[float, ...],
    max_candidates: int,
) -> dict:
    index_started = time.perf_counter()
    import chromadb
    from chromadb.utils import embedding_functions

    # A new in-memory database per model makes it impossible to mix vectors
    # from different embedding spaces or overwrite the production index.
    client = chromadb.EphemeralClient()
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=model_name
    )
    collection = client.create_collection(
        name=_collection_name(model_name),
        embedding_function=embedding_fn,
        configuration={"hnsw": {"space": "cosine"}},
    )

    print(f"[{model_name}] indexation de {len(products)} produits…", file=sys.stderr, flush=True)
    collection.add(
        ids=[str(product["id"]) for product in products],
        documents=[build_document(product) for product in products],
    )
    index_and_model_init_ms = round((time.perf_counter() - index_started) * 1000, 2)

    query_texts = [case["query"] for case in cases]
    print(f"[{model_name}] encodage de {len(query_texts)} requêtes par lot…", file=sys.stderr, flush=True)
    query_started = time.perf_counter()
    query_embeddings = embedding_fn(query_texts)
    query_embedding_ms = round((time.perf_counter() - query_started) * 1000, 2)

    search_started = time.perf_counter()
    response = collection.query(
        query_embeddings=query_embeddings,
        n_results=min(max_candidates, len(products)),
        include=["distances"],
    )
    database_search_ms = round((time.perf_counter() - search_started) * 1000, 2)
    ranked_results = [
        [
            (product_id, float(distance))
            for product_id, distance in zip(ids, distances)
        ]
        for ids, distances in zip(response["ids"], response["distances"])
    ]
    retrieval = {
        "query_count": len(cases),
        "error_count": 0,
        "error_rate": 0.0 if cases else None,
        "thresholds": [
            _retrieval_metrics(cases, ranked_results, threshold)
            for threshold in thresholds
        ],
    }

    result = {
        "embedding_model": model_name,
        "catalog_product_count": len(products),
        "index_and_model_init_ms": index_and_model_init_ms,
        "query_batch_latency_ms": {
            "embedding_all_queries": query_embedding_ms,
            "chroma_search_all_queries": database_search_ms,
            "total_all_queries": round(query_embedding_ms + database_search_ms, 2),
            "amortized_per_query": round(
                (query_embedding_ms + database_search_ms) / len(cases), 2
            ) if cases else None,
        },
        "query_latency_note": (
            f"Les {len(cases)} requêtes sont encodées et cherchées en lots pour réduire "
            "le coût d'inférence sur CPU. index_and_model_init_ms inclut "
            "l'initialisation du modèle et l'indexation du catalogue."
        ),
        "results": retrieval,
    }

    # Release the per-model in-memory index before loading the next model.
    del collection, embedding_fn, client
    gc.collect()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument(
        "--output",
        type=Path,
        help="Écrit également le rapport JSON dans ce fichier.",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help=(
            "Modèle Sentence Transformers à évaluer; répétable. Par défaut : "
            + ", ".join(DEFAULT_MODELS)
        ),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        action="append",
        help="Seuil de distance à mesurer; répétable.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--torch-threads",
        type=int,
        help="Limite les threads CPU PyTorch; par défaut, PyTorch choisit lui-même.",
    )
    parser.add_argument(
        "--limit-queries",
        type=int,
        help="Limite le nombre de requêtes (utile pour vérifier la durée; métriques non représentatives).",
    )
    args = parser.parse_args()
    if args.top_k < 3:
        parser.error("--top-k doit être supérieur ou égal à 3 pour mesurer Hit@3")
    if args.torch_threads is not None and args.torch_threads < 1:
        parser.error("--torch-threads doit être supérieur ou égal à 1")
    if args.limit_queries is not None and args.limit_queries < 1:
        parser.error("--limit-queries doit être supérieur ou égal à 1")

    dataset = _load_dataset(args.dataset)
    with args.products.open(encoding="utf-8") as products_file:
        products = json.load(products_file)
    if not products:
        parser.error("Le catalogue de produits est vide.")
    catalog_ids = {str(product["id"]) for product in products}
    missing_relevant_ids = sorted(
        {
            str(product_id)
            for case in dataset["retrieval"]
            for product_id in case["relevant_ids"]
            if str(product_id) not in catalog_ids
        }
    )
    if missing_relevant_ids:
        parser.error(
            "Le catalogue ne contient pas tous les IDs pertinents du jeu : "
            + ", ".join(missing_relevant_ids)
        )

    models = tuple(args.models) if args.models else DEFAULT_MODELS
    thresholds = tuple(args.threshold) if args.threshold else DEFAULT_THRESHOLDS
    retrieval_cases = dataset["retrieval"]
    if args.limit_queries is not None:
        retrieval_cases = retrieval_cases[:args.limit_queries]

    # Leave PyTorch's hardware-aware default unchanged unless the caller asks
    # to compare a specific thread limit.
    import torch

    if args.torch_threads is not None:
        torch.set_num_threads(args.torch_threads)

    report = {
        "dataset": str(args.dataset),
        "dataset_version": dataset["version"],
        "catalog": str(args.products),
        "distance_metric": "cosine",
        "threshold_semantics": "Retourner les produits dont la distance est <= au seuil.",
        "production_index_modified": False,
        "torch_threads": torch.get_num_threads(),
        "retrieval_query_count": len(retrieval_cases),
        "models": [],
    }

    for model_name in models:
        try:
            print(f"Benchmark du modèle {model_name}…", file=sys.stderr, flush=True)
            report["models"].append(
                _benchmark_model(
                    model_name,
                    products,
                    retrieval_cases,
                    thresholds,
                    args.top_k,
                )
            )
        except Exception as error:
            report["models"].append(
                {
                    "embedding_model": model_name,
                    "error_code": type(error).__name__,
                }
            )
            print(
                f"Échec du benchmark du modèle {model_name}: {type(error).__name__}",
                file=sys.stderr,
            )

    serialized_report = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized_report + "\n", encoding="utf-8")
    print(serialized_report)
    return 1 if any("error_code" in model for model in report["models"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

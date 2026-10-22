"""Offline retrieval and guardrail evaluation; never calls the LLM or WooCommerce."""
import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.guardrail_rules import (
    contains_prompt_injection,
    has_explicit_confirmation,
    is_product_advice_request,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "evaluation_cases.json"
DEFAULT_THRESHOLDS = (0.3, 0.5, 0.7, 0.9, 1.1)
DEFAULT_CANDIDATES = 10


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 2)


def _retrieval_metrics(
    cases: list[dict],
    ranked_results: list[list[tuple[str, float] | None]],
    threshold: float,
    top_k: int = 3,
) -> dict:
    positive_cases = 0
    hits_at_1 = 0
    hits_at_k = 0
    reciprocal_ranks = []
    negative_cases = 0
    false_positives = 0

    for case, ranking in zip(cases, ranked_results):
        visible = [product_id for product_id, distance in ranking if product_id is not None and distance <= threshold]
        relevant_ids = set(case["relevant_ids"])
        if relevant_ids:
            positive_cases += 1
            top_results = visible[:top_k]
            matching_ranks = [
                rank for rank, product_id in enumerate(top_results, start=1)
                if product_id in relevant_ids
            ]
            if matching_ranks:
                rank = min(matching_ranks)
                reciprocal_ranks.append(1 / rank)
                hits_at_k += 1
                if rank == 1:
                    hits_at_1 += 1
            else:
                reciprocal_ranks.append(0.0)
        else:
            negative_cases += 1
            if visible:
                false_positives += 1

    return {
        "threshold": threshold,
        "positive_queries": positive_cases,
        "negative_queries": negative_cases,
        "hit_at_1": round(hits_at_1 / positive_cases, 4) if positive_cases else None,
        f"hit_at_{top_k}": round(hits_at_k / positive_cases, 4) if positive_cases else None,
        "mrr": round(mean(reciprocal_ranks), 4) if reciprocal_ranks else None,
        "false_positive_rate": (
            round(false_positives / negative_cases, 4) if negative_cases else None
        ),
    }


def evaluate_retrieval(
    cases: list[dict],
    query: Callable[[str, int], list[tuple[str, float]]],
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    max_candidates: int = DEFAULT_CANDIDATES,
) -> dict:
    ranked_results: list[list[tuple[str, float] | None]] = []
    durations = []
    errors = 0
    error_codes: Counter[str] = Counter()

    for case in cases:
        started = time.perf_counter()
        try:
            ranked_results.append(query(case["query"], max_candidates))
        except Exception as error:
            ranked_results.append([])
            errors += 1
            error_codes[type(error).__name__] += 1
        durations.append((time.perf_counter() - started) * 1000)

    return {
        "query_count": len(cases),
        "error_count": errors,
        "error_rate": round(errors / len(cases), 4) if cases else None,
        "error_codes": dict(sorted(error_codes.items())),
        "latency_ms": {
            "mean": round(mean(durations), 2) if durations else None,
            "cold_first_query": round(durations[0], 2) if durations else None,
            "warm_mean": round(mean(durations[1:]), 2) if len(durations) > 1 else None,
            "warm_p50": _percentile(durations[1:], 0.50),
            "warm_p95": _percentile(durations[1:], 0.95),
            "warm_max": round(max(durations[1:]), 2) if len(durations) > 1 else None,
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "max": round(max(durations), 2) if durations else None,
        },
        "thresholds": [
            _retrieval_metrics(cases, ranked_results, threshold)
            for threshold in thresholds
        ],
    }


def evaluate_guardrails(
    confirmations: list[dict],
    injections: list[dict],
    product_advice: list[dict] | None = None,
) -> dict:
    confirmation_true_accepts = sum(
        has_explicit_confirmation(case["message"])
        for case in confirmations
        if case["expected"]
    )
    confirmation_false_accepts = sum(
        has_explicit_confirmation(case["message"])
        for case in confirmations
        if not case["expected"]
    )
    expected_confirmations = sum(case["expected"] for case in confirmations)
    expected_rejections = len(confirmations) - expected_confirmations

    blocked_attacks = sum(
        contains_prompt_injection(case["message"])
        for case in injections
        if case["expected_blocked"]
    )
    false_blocks = sum(
        contains_prompt_injection(case["message"])
        for case in injections
        if not case["expected_blocked"]
    )
    expected_attacks = sum(case["expected_blocked"] for case in injections)
    expected_benign = len(injections) - expected_attacks
    product_advice = product_advice or []
    advice_correct = sum(
        is_product_advice_request(case["message"]) == case["expected_search"]
        for case in product_advice
    )

    return {
        "confirmation_cases": len(confirmations),
        "confirmation_accept_rate": (
            round(confirmation_true_accepts / expected_confirmations, 4)
            if expected_confirmations else None
        ),
        "confirmation_false_accept_rate": (
            round(confirmation_false_accepts / expected_rejections, 4)
            if expected_rejections else None
        ),
        "injection_cases": len(injections),
        "attack_block_rate": round(blocked_attacks / expected_attacks, 4) if expected_attacks else None,
        "benign_false_block_rate": round(false_blocks / expected_benign, 4) if expected_benign else None,
        "product_advice_routing_cases": len(product_advice),
        "product_advice_routing_accuracy": (
            round(advice_correct / len(product_advice), 4) if product_advice else None
        ),
    }


def _collection_query(query_text: str, limit: int) -> list[tuple[str, float]]:
    from app.tools.search_product_tool import _get_collection

    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return []
    response = collection.query(
        query_texts=[query_text],
        n_results=min(limit, count),
        include=["distances"],
    )
    return [
        (product_id, float(distance))
        for product_id, distance in zip(response["ids"][0], response["distances"][0])
    ]


def _load_dataset(path: Path) -> dict:
    with path.open(encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)
    required = {"version", "retrieval", "confirmations", "injections", "product_advice"}
    if not isinstance(dataset, dict) or not required.issubset(dataset):
        raise ValueError(f"Jeu d'évaluation invalide : champs requis {sorted(required)}")
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--only", choices=("all", "retrieval", "guardrails"), default="all")
    parser.add_argument("--top-k", type=int, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--threshold",
        type=float,
        action="append",
        help="Distance seuil à mesurer; répétable. Par défaut : 0.3, 0.5, 0.7, 0.9, 1.1.",
    )
    args = parser.parse_args()
    if args.top_k < 3:
        parser.error("--top-k doit être supérieur ou égal à 3 pour mesurer Hit@3")

    dataset = _load_dataset(args.dataset)
    thresholds = tuple(args.threshold) if args.threshold else DEFAULT_THRESHOLDS
    report = {
        "dataset": str(args.dataset.relative_to(PROJECT_ROOT))
        if args.dataset.is_relative_to(PROJECT_ROOT)
        else args.dataset.name,
        "dataset_version": dataset["version"],
        "tool_selection": {
            "status": "not_measured",
            "reason": "Le routage LLM est non déterministe; aucun appel LLM n'est exécuté par cet évaluateur hors ligne.",
        },
    }

    if args.only in ("all", "retrieval"):
        from app.tools.search_product_tool import EMBEDDING_MODEL, MIN_DISTANCE

        report["retrieval"] = {
            "distance_metric": "cosine",
            "embedding_model": EMBEDDING_MODEL,
            "production_threshold": MIN_DISTANCE,
            "results": evaluate_retrieval(
                dataset["retrieval"],
                _collection_query,
                thresholds=thresholds,
                max_candidates=args.top_k,
            ),
        }
    if args.only in ("all", "guardrails"):
        report["guardrails"] = evaluate_guardrails(
            dataset["confirmations"], dataset["injections"], dataset["product_advice"]
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("retrieval", {}).get("results", {}).get("error_count", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())

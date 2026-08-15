"""Validate and decode completed blinded narrative-review scores."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from model_benchmark.narrative_review import RUBRIC, SCHEMA_VERSION, NarrativeReviewError, _atomic_json


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise NarrativeReviewError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise NarrativeReviewError(f"expected an object: {path}")
    return value, hashlib.sha256(raw).hexdigest()


def decode_review_scores(scores_path: Path, key_path: Path) -> dict[str, Any]:
    scores, scores_sha256 = _load(scores_path)
    key, key_sha256 = _load(key_path)
    if scores.get("schema_version") != SCHEMA_VERSION or key.get("schema_version") != SCHEMA_VERSION:
        raise NarrativeReviewError("review schema version mismatch")
    if not key.get("private"):
        raise NarrativeReviewError("decoding key is not marked private")
    if scores.get("source_results_sha256") != key.get("source_results_sha256"):
        raise NarrativeReviewError("score and key source fingerprints differ")
    architectures = key.get("architectures")
    if not isinstance(architectures, list) or len(architectures) != 2 or architectures[0] == architectures[1]:
        raise NarrativeReviewError("decoding key has invalid architectures")

    raw_key_items = key.get("items")
    raw_score_items = scores.get("items")
    if not isinstance(raw_key_items, list) or not isinstance(raw_score_items, list):
        raise NarrativeReviewError("score and key items must be arrays")
    key_items = {item.get("item_id"): item for item in raw_key_items if isinstance(item, dict)}
    score_items = {item.get("item_id"): item for item in raw_score_items if isinstance(item, dict)}
    if (
        not key_items
        or len(key_items) != len(raw_key_items)
        or len(score_items) != len(raw_score_items)
        or key_items.keys() != score_items.keys()
    ):
        raise NarrativeReviewError("completed score item IDs do not exactly match the key")

    decoded_items = []
    preference_counts = {architectures[0]: 0, architectures[1]: 0, "tie": 0}
    dimension_values = {dimension: {architecture: [] for architecture in architectures} for dimension in RUBRIC}
    for item_id in key_items:
        key_item = key_items[item_id]
        score_item = score_items[item_id]
        labels = key_item.get("labels")
        if not isinstance(labels, dict) or set(labels) != {"A", "B"} or set(labels.values()) != set(architectures):
            raise NarrativeReviewError(f"invalid label mapping for {item_id}")
        ratings = score_item.get("ratings")
        if not isinstance(ratings, dict) or set(ratings) != {"A", "B"}:
            raise NarrativeReviewError(f"invalid ratings for {item_id}")
        decoded_ratings: dict[str, dict[str, int]] = {}
        for label in ("A", "B"):
            label_ratings = ratings.get(label)
            if not isinstance(label_ratings, dict) or set(label_ratings) != set(RUBRIC):
                raise NarrativeReviewError(f"invalid rubric dimensions for {item_id}/{label}")
            architecture = labels[label]
            decoded_ratings[architecture] = {}
            for dimension in RUBRIC:
                rating = label_ratings[dimension]
                if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
                    raise NarrativeReviewError(f"rating must be an integer 1..5 for {item_id}/{label}/{dimension}")
                decoded_ratings[architecture][dimension] = rating
                dimension_values[dimension][architecture].append(rating)
        preference = score_item.get("preference")
        if preference not in {"A", "B", "tie"}:
            raise NarrativeReviewError(f"invalid preference for {item_id}")
        decoded_preference = labels[preference] if preference in {"A", "B"} else "tie"
        preference_counts[decoded_preference] += 1
        decoded_items.append({
            "item_id": item_id,
            "model": key_item.get("model", ""),
            "case_id": key_item.get("case_id", ""),
            "repetition": key_item.get("repetition", 0),
            "ratings": decoded_ratings,
            "preference": decoded_preference,
            "notes": str(score_item.get("notes", "")),
        })

    first, second = architectures
    dimension_results = {}
    for dimension in RUBRIC:
        first_mean = fmean(dimension_values[dimension][first])
        second_mean = fmean(dimension_values[dimension][second])
        paired_deltas = [
            left - right
            for left, right in zip(dimension_values[dimension][first], dimension_values[dimension][second], strict=True)
        ]
        dimension_results[dimension] = {
            first: {"mean": first_mean},
            second: {"mean": second_mean},
            f"paired_delta_{first}_minus_{second}": fmean(paired_deltas),
        }
    return {
        "schema_version": "narrative-review-results-v1",
        "private": True,
        "source_results_sha256": key["source_results_sha256"],
        "case_corpus_sha256": key.get("case_corpus_sha256", ""),
        "scores_sha256": scores_sha256,
        "decoding_key_sha256": key_sha256,
        "architectures": architectures,
        "completed_items": len(decoded_items),
        "preference_counts": preference_counts,
        "dimension_results": dimension_results,
        "items": decoded_items,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed_scores", type=Path)
    parser.add_argument("private_key", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        results = decode_review_scores(args.completed_scores, args.private_key)
        _atomic_json(args.output, results, private=True)
    except (NarrativeReviewError, OSError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

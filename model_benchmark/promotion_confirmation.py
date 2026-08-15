"""Analyze a matched multi-seed generation run and its zero-call browser child."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Iterable

from model_benchmark.narrative_review import NarrativeReviewError, _atomic_json


PLAYABLE_CATEGORIES = {
    "browser_load",
    "choice_reachability",
    "choice_effect_execution",
    "runtime_state_transaction",
    "continuity_after_navigation",
}
PRESERVED_FIELDS = {
    "actual_output_raw",
    "finish_reason",
    "input_tokens",
    "model_alias",
    "output_tokens",
    "random_seed",
    "repetition",
    "runtime_seconds",
    "total_tokens",
}
COMPATIBILITY_FIELDS = {
    "benchmark_version",
    "dataset_checksums",
    "generation_params",
    "model_configs",
    "prompt_template",
    "prompt_version",
    "python_version",
    "random_seed",
    "repeated_runs_count",
    "runtime_settings",
    "source_commit_hash",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in (run_dir / "results_internal.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise NarrativeReviewError(f"invalid benchmark run: {run_dir}") from error
    if not isinstance(manifest, dict) or not all(isinstance(record, dict) for record in records):
        raise NarrativeReviewError(f"invalid benchmark artifacts: {run_dir}")
    return manifest, records


def _category_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    categories = record.get("scored_result", {}).get("category_results", [])
    if not isinstance(categories, list):
        raise NarrativeReviewError(f"invalid category results: {record.get('test_id', '')}")
    mapped = {str(category.get("name", "")): category for category in categories if isinstance(category, dict)}
    if len(mapped) != len(categories):
        raise NarrativeReviewError(f"duplicate or invalid category results: {record.get('test_id', '')}")
    return mapped


def _passed(record: dict[str, Any], category: str) -> bool:
    result = _category_map(record).get(category)
    return bool(result and result.get("applicable", True) and result.get("passed"))


def _compiled(record: dict[str, Any]) -> bool:
    return any(
        category.get("applicable", True) and name in PLAYABLE_CATEGORIES
        for name, category in _category_map(record).items()
    )


def _playable(record: dict[str, Any]) -> bool:
    categories = [
        category
        for name, category in _category_map(record).items()
        if category.get("applicable", True) and name in PLAYABLE_CATEGORIES
    ]
    return bool(categories) and all(category.get("passed") for category in categories)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise NarrativeReviewError("cannot calculate a percentile without values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _exact_two_sided_binomial(wins: int, losses: int) -> float:
    non_ties = wins + losses
    if non_ties == 0:
        return 1.0
    lower = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(non_ties, index) for index in range(lower + 1)) / (2**non_ties))


def _pair(
    candidate: dict[tuple[str, int], dict[str, Any]],
    control: dict[tuple[str, int], dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    if set(candidate) != set(control):
        raise NarrativeReviewError("candidate and control request identities do not match")
    wins = sum(predicate(candidate[key]) and not predicate(control[key]) for key in control)
    losses = sum(predicate(control[key]) and not predicate(candidate[key]) for key in control)
    ties = len(control) - wins - losses
    loss_identities = [
        {"input_summary": key[0], "repetition": key[1], "seed": str(control[key].get("random_seed", ""))}
        for key in sorted(control)
        if predicate(control[key]) and not predicate(candidate[key])
    ]
    losses_by_case: dict[str, int] = defaultdict(int)
    for identity in loss_identities:
        losses_by_case[str(identity["input_summary"])] += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "exact_two_sided_p": _exact_two_sided_binomial(wins, losses),
        "loss_identities": loss_identities,
        "losses_by_case": dict(sorted(losses_by_case.items())),
    }


def _architecture_metrics(records: list[dict[str, Any]], expected_seeds: list[str]) -> dict[str, Any]:
    if not records:
        raise NarrativeReviewError("architecture has no records")
    category_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        for name, category in _category_map(record).items():
            if category.get("applicable", True):
                category_counts[name][1] += 1
                category_counts[name][0] += bool(category.get("passed"))
    semantic_observables = [record for record in records if _passed(record, "semantic_observables")]
    semantic_drafts = [record for record in semantic_observables if _passed(record, "draft_assembly")]
    per_seed = []
    for seed in expected_seeds:
        seed_records = [record for record in records if str(record.get("random_seed")) == seed]
        if not seed_records:
            raise NarrativeReviewError(f"architecture has no records for seed {seed}")
        per_seed.append({
            "seed": seed,
            "requests": len(seed_records),
            "request_pass": sum(record.get("status") == "PASS" for record in seed_records),
            "request_playable": sum(_playable(record) for record in seed_records),
        })
    request_count = len(records)
    compiled_count = sum(_compiled(record) for record in records)
    playable_count = sum(_playable(record) for record in records)
    return {
        "original_requests": request_count,
        "request_pass": {
            "passed": sum(record.get("status") == "PASS" for record in records),
            "rate": sum(record.get("status") == "PASS" for record in records) / request_count,
        },
        "request_playable": {"passed": playable_count, "rate": playable_count / request_count},
        "compiled_playable": {
            "passed": playable_count,
            "applicable": compiled_count,
            "rate": playable_count / compiled_count if compiled_count else 0.0,
        },
        "semantic_accepted_compile": {
            "passed": sum(_passed(record, "compile_success") for record in semantic_drafts),
            "applicable": len(semantic_drafts),
            "rate": (
                sum(_passed(record, "compile_success") for record in semantic_drafts) / len(semantic_drafts)
                if semantic_drafts
                else 0.0
            ),
        },
        "semantic_observable_without_draft": len(semantic_observables) - len(semantic_drafts),
        "latency_seconds": {
            "mean": fmean(float(record.get("runtime_seconds", 0)) for record in records),
            "p95": _percentile([float(record.get("runtime_seconds", 0)) for record in records], 0.95),
        },
        "tokens": {
            "mean_total": fmean(float(record.get("total_tokens", 0)) for record in records),
            "total": sum(int(record.get("total_tokens", 0)) for record in records),
        },
        "categories": {
            name: {"passed": counts[0], "applicable": counts[1], "rate": counts[0] / counts[1]}
            for name, counts in sorted(category_counts.items())
        },
        "per_seed": per_seed,
    }


def analyze_confirmation(
    parent_dir: Path,
    child_dir: Path,
    *,
    legacy_architecture: str = "legacy_json",
    required_margin_percentage_points: float = 5.0,
) -> dict[str, Any]:
    parent_manifest, parent_records = _load_run(parent_dir)
    child_manifest, child_records = _load_run(child_dir)
    browser = child_manifest.get("browser_rescore")
    if not isinstance(browser, dict) or browser.get("model_calls") != 0:
        raise NarrativeReviewError("child is not a zero-call browser rescore")
    parent_results_path = parent_dir / "results_internal.jsonl"
    if browser.get("source_results_sha256") != _sha256(parent_results_path):
        raise NarrativeReviewError("child source-results hash does not match the parent")
    for field in COMPATIBILITY_FIELDS:
        if child_manifest.get(field) != parent_manifest.get(field):
            raise NarrativeReviewError(f"child changed compatibility field: {field}")
    parent_by_id = {str(record.get("test_id", "")): record for record in parent_records}
    child_by_id = {str(record.get("test_id", "")): record for record in child_records}
    if not all(parent_by_id) or len(parent_by_id) != len(parent_records):
        raise NarrativeReviewError("parent has blank or duplicate test IDs")
    if not all(child_by_id) or len(child_by_id) != len(child_records):
        raise NarrativeReviewError("child has blank or duplicate test IDs")
    if set(parent_by_id) != set(child_by_id):
        raise NarrativeReviewError("parent and child request identities do not match")
    for test_id, parent in parent_by_id.items():
        child = child_by_id[test_id]
        if child.get("parent_result_id") != test_id:
            raise NarrativeReviewError(f"child does not link to parent result: {test_id}")
        for field in PRESERVED_FIELDS:
            if child.get(field) != parent.get(field):
                raise NarrativeReviewError(f"child changed generation field {field}: {test_id}")

    repeat_count = int(parent_manifest.get("repeated_runs_count", 0))
    base_seed = int(parent_manifest.get("random_seed", 0))
    if repeat_count < 2:
        raise NarrativeReviewError("confirmation requires a repeated multi-seed parent")
    expected_seeds = [str(base_seed + offset) for offset in range(repeat_count)]
    architecture_names = sorted({
        str(record.get("subcategory"))
        for record in child_records
        if str(record.get("category", "")).startswith("harness_structure_")
    })
    if legacy_architecture not in architecture_names:
        raise NarrativeReviewError(f"missing legacy control architecture: {legacy_architecture}")
    architecture_records = {
        architecture: [record for record in child_records if record.get("subcategory") == architecture]
        for architecture in architecture_names
    }
    paired_records: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    for architecture, records in architecture_records.items():
        pairs = {(str(record.get("input_summary")), int(record.get("repetition", 0))): record for record in records}
        if len(pairs) != len(records):
            raise NarrativeReviewError(f"duplicate paired identity for {architecture}")
        counts_by_repetition = defaultdict(int)
        for record in records:
            repetition = int(record.get("repetition", 0))
            if repetition < 1 or repetition > repeat_count:
                raise NarrativeReviewError(f"invalid repetition for {architecture}")
            expected_seed = str(base_seed + repetition - 1)
            if str(record.get("random_seed")) != expected_seed:
                raise NarrativeReviewError(f"seed/repetition mismatch for {architecture}")
            counts_by_repetition[repetition] += 1
        if len(set(counts_by_repetition.values())) != 1 or set(counts_by_repetition) != set(range(1, repeat_count + 1)):
            raise NarrativeReviewError(f"incomplete repetition coverage for {architecture}")
        paired_records[architecture] = pairs
    control_pairs = paired_records[legacy_architecture]
    metrics = {
        architecture: _architecture_metrics(records, expected_seeds)
        for architecture, records in architecture_records.items()
    }
    comparisons: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    control_metrics = metrics[legacy_architecture]
    for architecture in architecture_names:
        if architecture == legacy_architecture:
            continue
        candidate_metrics = metrics[architecture]
        playable_delta = (
            candidate_metrics["request_playable"]["rate"] - control_metrics["request_playable"]["rate"]
        ) * 100
        latency_delta = (
            candidate_metrics["latency_seconds"]["p95"] / control_metrics["latency_seconds"]["p95"] - 1
        ) * 100
        comparisons[architecture] = {
            "versus": legacy_architecture,
            "request_pass": _pair(paired_records[architecture], control_pairs, lambda record: record.get("status") == "PASS"),
            "request_playable": _pair(paired_records[architecture], control_pairs, _playable),
            "request_playable_delta_percentage_points": playable_delta,
            "p95_latency_delta_percent": latency_delta,
        }
        categories = candidate_metrics["categories"]
        gate_values = {
            "semantic_accepted_compile_100_percent": candidate_metrics["semantic_accepted_compile"]["rate"] == 1.0,
            "normalized_handoff_at_least_90_percent": categories["plan_adherence"]["rate"] >= 0.9,
            "state_transaction_at_least_90_percent": categories["state_transaction"]["rate"] >= 0.9,
            "compiled_playability_at_least_95_percent": candidate_metrics["compiled_playable"]["rate"] >= 0.95,
            "request_playable_margin_exceeded": playable_delta > required_margin_percentage_points,
            "p95_latency_within_25_percent": latency_delta <= 25.0,
        }
        gates[architecture] = {**gate_values, "mechanical_and_latency_gates_pass": all(gate_values.values())}

    return {
        "schema_version": "promotion-confirmation-v1",
        "parent_path": str(parent_dir),
        "child_path": str(child_dir),
        "parent_results_sha256": _sha256(parent_results_path),
        "child_results_sha256": _sha256(child_dir / "results_internal.jsonl"),
        "analyzer_source_sha256": _sha256(Path(__file__)),
        "model_calls": browser["model_calls"],
        "record_count": len(child_records),
        "generation_fields_preserved": True,
        "compatibility_fields_verified": True,
        "base_seed": str(base_seed),
        "repeat_count": repeat_count,
        "seeds": expected_seeds,
        "legacy_architecture": legacy_architecture,
        "required_margin_percentage_points": required_margin_percentage_points,
        "architectures": metrics,
        "comparisons": comparisons,
        "automated_promotion_gates": gates,
        "human_narrative_gate": "not_assessed",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_dir", type=Path)
    parser.add_argument("child_dir", type=Path)
    parser.add_argument("--legacy-architecture", default="legacy_json")
    parser.add_argument("--required-margin-percentage-points", type=float, default=5.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = analyze_confirmation(
            args.parent_dir,
            args.child_dir,
            legacy_architecture=args.legacy_architecture,
            required_margin_percentage_points=args.required_margin_percentage_points,
        )
        _atomic_json(args.output, result)
    except (NarrativeReviewError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure same-seed replay ranges across browser-rescored benchmark runs."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from model_benchmark.narrative_review import NarrativeReviewError, _atomic_json


PLAYABLE_CATEGORIES = {
    "browser_load",
    "choice_reachability",
    "choice_effect_execution",
    "runtime_state_transaction",
    "continuity_after_navigation",
}


def _load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        records = [json.loads(line) for line in (run_dir / "results_internal.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise NarrativeReviewError(f"invalid replay run: {run_dir}") from error
    if not isinstance(manifest, dict) or not all(isinstance(record, dict) for record in records):
        raise NarrativeReviewError(f"invalid replay artifacts: {run_dir}")
    browser = manifest.get("browser_rescore")
    if not isinstance(browser, dict) or browser.get("model_calls") != 0:
        raise NarrativeReviewError(f"run is not a zero-call browser rescore: {run_dir}")
    return manifest, records


def _compatibility_key(manifest: dict[str, Any]) -> dict[str, Any]:
    runtime = manifest.get("runtime_settings", {})
    return {
        "random_seed": manifest.get("random_seed"),
        "repeated_runs_count": manifest.get("repeated_runs_count"),
        "model_configs": manifest.get("model_configs"),
        "dataset_checksums": manifest.get("dataset_checksums"),
        "generation_params": manifest.get("generation_params"),
        "python_version": manifest.get("python_version"),
        "source_commit_hash": manifest.get("source_commit_hash"),
        "benchmark_version": manifest.get("benchmark_version"),
        "evaluator_version": manifest.get("evaluator_version"),
        "prompt_template": manifest.get("prompt_template"),
        "prompt_version": manifest.get("prompt_version"),
        "runtime_settings": {
            key: runtime.get(key)
            for key in ("benchmark_profile", "num_predict", "temperature", "timeout", "refactor_architectures", "ollama_version")
        },
        "evaluator_source_sha256": manifest.get("browser_rescore", {}).get("evaluator_source_sha256"),
    }


def _architecture_metrics(records: list[dict[str, Any]], architecture: str) -> dict[str, Any]:
    rows = [record for record in records if record.get("subcategory") == architecture]
    if not rows:
        raise NarrativeReviewError(f"run has no records for {architecture}")
    category_counts: dict[str, list[int]] = {}
    request_playable = 0
    compiled = 0
    for row in rows:
        categories = row.get("scored_result", {}).get("category_results", [])
        applicable_playable = []
        for category in categories:
            if not isinstance(category, dict) or not category.get("applicable", True):
                continue
            name = str(category.get("name", ""))
            category_counts.setdefault(name, [0, 0])[1] += 1
            category_counts[name][0] += bool(category.get("passed"))
            if name in PLAYABLE_CATEGORIES:
                applicable_playable.append(bool(category.get("passed")))
        if applicable_playable:
            compiled += 1
            request_playable += all(applicable_playable)
    total = len(rows)
    return {
        "original_requests": total,
        "request_pass": {"passed": sum(row.get("status") == "PASS" for row in rows), "rate": sum(row.get("status") == "PASS" for row in rows) / total},
        "request_playable": {"passed": request_playable, "rate": request_playable / total},
        "compiled_playable": {"passed": request_playable, "applicable": compiled, "rate": request_playable / compiled if compiled else 0.0},
        "categories": {
            name: {"passed": count[0], "applicable": count[1], "rate": count[0] / count[1]}
            for name, count in sorted(category_counts.items())
        },
    }


def analyze_replay_variance(run_dirs: Iterable[Path]) -> dict[str, Any]:
    paths = list(run_dirs)
    if len(paths) < 2:
        raise NarrativeReviewError("at least two replay runs are required")
    loaded = [_load_run(path) for path in paths]
    expected = _compatibility_key(loaded[0][0])
    if not expected["random_seed"] or expected["repeated_runs_count"] != 1:
        raise NarrativeReviewError("replay runs must use one identical explicit seed")
    for manifest, _ in loaded[1:]:
        if _compatibility_key(manifest) != expected:
            raise NarrativeReviewError("replay manifests are not compatible")
    architectures = sorted({str(record.get("subcategory")) for _, records in loaded for record in records if str(record.get("category", "")).startswith("harness_structure_")})
    expected_ids: dict[str, set[str]] = {}
    for architecture in architectures:
        ids = [str(record.get("test_id", "")) for record in loaded[0][1] if record.get("subcategory") == architecture]
        if not ids or len(ids) != len(set(ids)):
            raise NarrativeReviewError(f"duplicate or missing request identities for {architecture}")
        expected_ids[architecture] = set(ids)
    for _, records in loaded[1:]:
        for architecture in architectures:
            ids = [str(record.get("test_id", "")) for record in records if record.get("subcategory") == architecture]
            if len(ids) != len(set(ids)) or set(ids) != expected_ids[architecture]:
                raise NarrativeReviewError(f"replay request identities differ for {architecture}")
    runs = []
    for path, (manifest, records) in zip(paths, loaded, strict=True):
        runs.append({
            "run_id": manifest.get("run_id", ""),
            "parent_run_id": manifest.get("parent_run_id", ""),
            "path": str(path),
            "architectures": {architecture: _architecture_metrics(records, architecture) for architecture in architectures},
        })
    ranges = {}
    for architecture in architectures:
        architecture_ranges = {}
        for metric in ("request_pass", "request_playable", "compiled_playable"):
            rates = [run["architectures"][architecture][metric]["rate"] for run in runs]
            architecture_ranges[metric] = {"minimum": min(rates), "maximum": max(rates), "range_percentage_points": (max(rates) - min(rates)) * 100}
        ranges[architecture] = architecture_ranges
    playable_noise_floor = max(value["request_playable"]["range_percentage_points"] for value in ranges.values())
    required_margin = max(5, math.floor(playable_noise_floor + 1e-9) + 1)
    return {
        "schema_version": "replay-variance-v1",
        "sampling_seed": expected["random_seed"],
        "run_count": len(runs),
        "compatibility": expected,
        "runs": runs,
        "ranges": ranges,
        "request_playable_noise_floor_percentage_points": playable_noise_floor,
        "required_promotion_margin_percentage_points": required_margin,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = analyze_replay_variance(args.run_dirs)
        _atomic_json(args.output, result)
    except (NarrativeReviewError, OSError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

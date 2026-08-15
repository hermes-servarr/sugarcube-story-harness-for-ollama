"""Derive browser-gated evidence from an immutable refactor benchmark run.

The source run's raw model responses are reparsed with the same architecture
adapters and scorers.  Existing non-browser categories must match exactly
before any derived record is written.  This avoids repeating expensive model
calls merely to run deterministic Tweego/Playwright evaluation.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from model_benchmark.persistence import create_run_dir, write_jsonl, write_manifest
from model_benchmark.refactor_benchmark import (
    _architecture_request,
    _production_pipeline_categories,
    load_refactor_cases,
    make_refactor_browser_evaluator,
    score_refactor_fill,
)


BROWSER_CATEGORY_NAMES = (
    "tweego_compile",
    "browser_load",
    "choice_reachability",
    "choice_effect_execution",
    "runtime_state_transaction",
    "continuity_after_navigation",
)
BROWSER_RESCORE_VERSION = "browser-rescore-v1"


class BrowserRescoreError(ValueError):
    pass


def _canonical_category(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": category["name"],
        "passed": bool(category["passed"]),
        "score": float(category["score"]),
        "details": category["details"],
        "evidence": list(category.get("evidence", [])),
        "applicable": bool(category.get("applicable", True)),
        "gating": bool(category.get("gating", True)),
    }


def _case_id(record: dict[str, Any]) -> str:
    summary = str(record.get("input_summary", ""))
    case_id = summary.split(":", 1)[0]
    if not case_id:
        raise BrowserRescoreError("refactor result lacks a case identity")
    return case_id


def rescore_browser_records(
    records: Iterable[dict[str, Any]],
    browser_evaluator: Callable[[Any, Any, Any], Iterable[Any]],
) -> list[dict[str, Any]]:
    """Return child records with real browser categories and parent linkage."""
    cases = {case.id: case for case in load_refactor_cases()}
    rescored: list[dict[str, Any]] = []
    for source in records:
        record = copy.deepcopy(source)
        if not str(record.get("category", "")).startswith("harness_structure_"):
            record["parent_result_id"] = str(source.get("test_id", ""))
            record["provenance"] = "recovered"
            rescored.append(record)
            continue

        architecture = str(record.get("subcategory", ""))
        case_id = _case_id(record)
        case = cases.get(case_id)
        if case is None:
            raise BrowserRescoreError(f"unknown refactor case in result: {case_id}")
        try:
            parse = _architecture_request(architecture, case)[2]
        except Exception as exc:
            raise BrowserRescoreError(
                f"unsupported architecture in result: {architecture}"
            ) from exc
        raw = str(record.get("actual_output_raw", ""))
        fill = parse(raw)
        categories = [
            *score_refactor_fill(case, raw, fill),
            *_production_pipeline_categories(
                case, fill, browser_evaluator=browser_evaluator
            ),
        ]
        derived = [_canonical_category(dataclasses.asdict(item)) for item in categories]
        original = [
            _canonical_category(item)
            for item in record["scored_result"]["category_results"]
        ]
        old_non_browser = [
            item for item in original if item["name"] not in BROWSER_CATEGORY_NAMES
        ]
        new_non_browser = [
            item for item in derived if item["name"] not in BROWSER_CATEGORY_NAMES
        ]
        if old_non_browser != new_non_browser:
            raise BrowserRescoreError(
                f"source evaluator drift for {record.get('test_id', case_id)}"
            )

        applicable = [
            item for item in derived if item["applicable"] and item["gating"]
        ]
        passed = sum(item["passed"] for item in applicable)
        overall = bool(applicable) and passed == len(applicable)
        record["score"] = float(passed)
        record["max_score"] = float(len(applicable) or 1)
        record["normalized_score"] = record["score"] / record["max_score"]
        record["status"] = "PASS" if overall else "FAIL"
        record["failure_category"] = "none" if overall else "instruction_following"
        record["evaluator_version"] = BROWSER_RESCORE_VERSION
        record["evaluator_reasoning"] = (
            "source response deterministically rescored with Tweego/Playwright"
        )
        record["parent_result_id"] = str(source.get("test_id", ""))
        record["provenance"] = "recovered"
        record["scored_result"]["category_results"] = derived
        record["scored_result"]["overall_pass"] = overall
        rescored.append(record)
    return rescored


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluator_source_hashes() -> dict[str, str]:
    repository = Path(__file__).parents[1]
    relative_paths = (
        "model_benchmark/browser_rescore.py",
        "model_benchmark/refactor_benchmark.py",
        "model_benchmark/refactor_cases.json",
        "model_benchmark/scoring.py",
        "harness/generation/contracts.py",
        "harness/generation/compiler.py",
        "harness/generation/browser_evaluator.py",
        "harness/models.py",
        "harness/parsers.py",
    )
    return {path: _sha256(repository / path) for path in relative_paths}


def _summary(records: list[dict[str, Any]], parent_run_id: str) -> str:
    lines = [
        "# Browser rescore summary",
        "",
        f"Parent run: `{parent_run_id}`",
        f"Derived records: {len(records)}",
        "",
        "| Architecture | Request pass | Browser load | Playable |",
        "|---|---:|---:|---:|",
    ]
    for architecture in ("legacy_json", "typed_fill", "flat_fill"):
        rows = [
            row for row in records
            if row.get("category") == f"harness_structure_{architecture}"
        ]
        category_counts: dict[str, list[int]] = {
            name: [0, 0] for name in BROWSER_CATEGORY_NAMES
        }
        for row in rows:
            for category in row["scored_result"]["category_results"]:
                name = category["name"]
                if name in category_counts and category.get("applicable", True):
                    category_counts[name][1] += 1
                    category_counts[name][0] += bool(category["passed"])
        request_pass = sum(row["status"] == "PASS" for row in rows)
        load = category_counts["browser_load"]
        playable_names = (
            "browser_load", "choice_reachability", "choice_effect_execution",
            "runtime_state_transaction", "continuity_after_navigation",
        )
        playable_total = 0
        playable_pass = 0
        for row in rows:
            applicable = {
                item["name"]: item for item in row["scored_result"]["category_results"]
                if item["name"] in playable_names and item.get("applicable", True)
            }
            if applicable:
                playable_total += 1
                playable_pass += all(item["passed"] for item in applicable.values())
        lines.append(
            f"| {architecture} | {request_pass}/{len(rows)} | "
            f"{load[0]}/{load[1]} | {playable_pass}/{playable_total} |"
        )
    return "\n".join(lines) + "\n"


def rescore_run(
    source_run: Path,
    *,
    tweego_path: Path,
    story_format_path: Path,
    output_dir: Path,
    browser_path: Path | None = None,
) -> Path:
    source_run = source_run.resolve()
    results_path = source_run / "results_internal.jsonl"
    manifest_path = source_run / "run_manifest.json"
    if not results_path.is_file() or not manifest_path.is_file():
        raise BrowserRescoreError("source run lacks results_internal.jsonl or run_manifest.json")
    records = [
        json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parent_run_id = str(manifest.get("run_id", ""))
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    evaluator = make_refactor_browser_evaluator(
        tweego_path, story_format_path, browser_path=browser_path
    )
    rescored = rescore_browser_records(records, evaluator)
    completed = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex[:8]
    child_manifest = dict(manifest)
    child_manifest.update({
        "run_id": run_id,
        "parent_run_id": parent_run_id,
        "benchmark_name": f"{manifest.get('benchmark_name', 'sugarcube-bench')}-browser-rescore",
        "start_timestamp": started.isoformat(),
        "completion_timestamp": completed.isoformat(),
        "duration_seconds": time.monotonic() - clock,
        "evaluator_version": BROWSER_RESCORE_VERSION,
        "cli_args": [],
        "browser_rescore": {
            "source_results_sha256": _sha256(results_path),
            "evaluator_source_sha256": _evaluator_source_hashes(),
            "tweego_path": str(tweego_path.resolve()),
            "tweego_sha256": _sha256(tweego_path),
            "story_format_path": str(story_format_path.resolve()),
            "story_format_sha256": _sha256(story_format_path / "sugarcube-2" / "format.js"),
            "browser_path": str(browser_path.resolve()) if browser_path else "playwright-default",
            "model_calls": 0,
        },
    })
    run_dir = create_run_dir(output_dir, run_id=run_id)
    write_jsonl(run_dir / "results_internal.jsonl", rescored)
    write_manifest(run_dir / "run_manifest.json", child_manifest)
    (run_dir / "summary_internal.md").write_text(
        _summary(rescored, parent_run_id), encoding="utf-8"
    )
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run", type=Path)
    parser.add_argument("--tweego-bin", type=Path, required=True)
    parser.add_argument("--tweego-formats", type=Path, required=True)
    parser.add_argument("--chromium-bin", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_outputs"))
    args = parser.parse_args(argv)
    try:
        run_dir = rescore_run(
            args.source_run,
            tweego_path=args.tweego_bin,
            story_format_path=args.tweego_formats,
            browser_path=args.chromium_bin,
            output_dir=args.output_dir,
        )
    except (BrowserRescoreError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

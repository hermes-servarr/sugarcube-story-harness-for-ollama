#!/usr/bin/env python3
"""Produce a compact, identity-safe summary of anonymized benchmark JSON."""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _group(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get(key, "(missing)"))].append(record)
    result: dict[str, dict[str, Any]] = {}
    for name, rows in sorted(grouped.items()):
        scores = [float(row.get("normalized_score", 0.0)) for row in rows]
        passed = sum(row.get("status") == "PASS" for row in rows)
        result[name] = {
            "cases": len(rows),
            "passed": passed,
            "pass_rate": round(passed / len(rows), 4),
            "mean_score": round(statistics.fmean(scores), 4),
        }
    return result


def _failed_evaluator_categories(
    records: list[dict[str, Any]],
) -> Counter[str]:
    failures: Counter[str] = Counter()
    for row in records:
        scored = row.get("scored_result")
        if not isinstance(scored, dict):
            continue
        categories = scored.get("category_results", [])
        if not isinstance(categories, list):
            continue
        for category in categories:
            if isinstance(category, dict) and not category.get("passed", False):
                failures[str(category.get("name") or "unspecified")] += 1
    return failures


def _thinking_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    thinking = [
        row for row in records if str(row.get("subcategory", "")).lower() == "thinking"
    ]
    scores = [float(row.get("normalized_score", 0.0)) for row in thinking]
    passed = sum(row.get("status") == "PASS" for row in thinking)
    category_failures = _failed_evaluator_categories(thinking)
    total = len(thinking)
    return {
        "cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "mean_score": round(statistics.fmean(scores), 4) if scores else 0.0,
        "failed_evaluator_categories": dict(category_failures.most_common()),
        "thinking_quality_failures": category_failures["thinking_quality"],
        "final_passage_structure_failures": category_failures["passage_structure"],
    }


def _plain_text_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    plain = [
        row for row in records if str(row.get("subcategory", "")).lower() == "plain_text"
    ]
    grouped = _group(plain, "dataset")
    aggregate = (
        next(iter(grouped.values()))
        if grouped else
        {"cases": 0, "passed": 0, "pass_rate": 0.0, "mean_score": 0.0}
    )
    return {
        **aggregate,
        "by_context_profile": _group(plain, "split"),
        "by_tier": _group(plain, "difficulty"),
    }


def _signed_check_summary(
    records: list[dict[str, Any]], marker: str
) -> dict[str, Any]:
    selected = [
        row for row in records
        if marker in str(row.get("test_id", "")).upper()
    ]
    grouped = _group(selected, "dataset")
    aggregate = (
        next(iter(grouped.values()))
        if grouped else
        {"cases": 0, "passed": 0, "pass_rate": 0.0, "mean_score": 0.0}
    )
    failed_checks: Counter[str] = Counter()
    for row in selected:
        scored = row.get("scored_result")
        if not isinstance(scored, dict):
            continue
        for category in scored.get("category_results", []):
            if not isinstance(category, dict):
                continue
            for evidence in category.get("evidence", []):
                if isinstance(evidence, str) and evidence.endswith("=fail"):
                    failed_checks[evidence.removesuffix("=fail")] += 1
    return {
        **aggregate,
        "failed_checks": dict(failed_checks.most_common()),
        "by_variant": _group(selected, "subcategory"),
        "by_context_profile": _group(selected, "split"),
    }


def _conversation_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return _signed_check_summary(records, "CONVERSATION")


def _style_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return _signed_check_summary(records, "STYLE")


def _context_window_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Report transport acceptance separately from full-context retrieval."""
    by_alias: dict[str, Any] = {}
    configured_levels: set[int] = set()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row.get("model_alias", "(missing)"))].append(row)
    for alias, rows in sorted(grouped.items()):
        levels = []
        for row in rows:
            split = str(row.get("split", ""))
            try:
                requested = int(split.removeprefix("num_ctx_"))
            except ValueError:
                continue
            configured_levels.add(requested)
            status = str(row.get("status", "ERROR"))
            levels.append(
                {
                    "requested_num_ctx": requested,
                    "request_accepted": status != "ERROR",
                    "full_retrieval": status == "PASS",
                    "prompt_eval_count": int(row.get("input_tokens", 0) or 0),
                    "runtime_seconds": float(row.get("runtime_seconds", 0.0) or 0.0),
                }
            )
        levels.sort(key=lambda item: item["requested_num_ctx"])
        accepted = [
            item["requested_num_ctx"]
            for item in levels if item["request_accepted"]
        ]
        retained = [
            item["requested_num_ctx"]
            for item in levels if item["full_retrieval"]
        ]
        by_alias[alias] = {
            "max_accepted_num_ctx": max(accepted, default=0),
            "max_full_retrieval_num_ctx": max(retained, default=0),
            "levels": levels,
        }
    highest_level = max(configured_levels, default=0)
    for value in by_alias.values():
        value["accepted_at_least_configured_max"] = (
            highest_level > 0 and value["max_accepted_num_ctx"] == highest_level
        )
        value["retrieved_at_least_configured_max"] = (
            highest_level > 0
            and value["max_full_retrieval_num_ctx"] == highest_level
        )
    return {
        "diagnostic_only": True,
        "cases": len(records),
        "configured_num_ctx_levels": sorted(configured_levels),
        "by_model_alias": by_alias,
    }


def summarize(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("expected a JSON array of result objects")
    records: list[dict[str, Any]] = data
    candidate_records = [
        row for row in records if row.get("dataset") == "capability_candidate"
    ]
    context_window_records = [
        row
        for row in records
        if row.get("dataset") == "capability_context_window"
    ]
    objective_records = [
        row
        for row in records
        if row.get("dataset") not in {
            "capability_candidate",
            "capability_context_window",
        }
    ]
    scores = [
        float(row.get("normalized_score", 0.0)) for row in objective_records
    ]
    passed = sum(row.get("status") == "PASS" for row in objective_records)
    failures = Counter(
        str(row.get("failure_category") or "unspecified")
        for row in objective_records
        if row.get("status") != "PASS"
    )
    samples = []
    for row in sorted(
        (item for item in objective_records if item.get("status") != "PASS"),
        key=lambda item: float(item.get("normalized_score", 0.0)),
    )[:8]:
        category_details = []
        scored = row.get("scored_result")
        if isinstance(scored, dict):
            for category in scored.get("category_results", []):
                if isinstance(category, dict) and not category.get("passed", False):
                    category_details.append(
                        {
                            "name": str(category.get("name", "")),
                            "details": str(category.get("details", ""))[:500],
                        }
                    )
        samples.append(
            {
                "test_id": str(row.get("test_id", "")),
                "model_alias": str(row.get("model_alias", "")),
                "subcategory": str(row.get("subcategory", "")),
                "difficulty": str(row.get("difficulty", "")),
                "score": float(row.get("normalized_score", 0.0)),
                "failure_category": str(row.get("failure_category", "")),
                "evaluator_reasoning": str(row.get("evaluator_reasoning", ""))[:500],
                "failed_categories": category_details[:4],
            }
        )
    total = len(objective_records)
    return {
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "mean_score": round(statistics.fmean(scores), 4) if scores else 0.0,
        "failure_categories": dict(failures.most_common()),
        "by_model_alias": _group(objective_records, "model_alias"),
        "by_variant": _group(objective_records, "subcategory"),
        "by_direction": _group(objective_records, "difficulty"),
        "by_context_profile": _group(objective_records, "split"),
        "thinking_variant": _thinking_summary(objective_records),
        "plain_text": _plain_text_summary(objective_records),
        "conversation_layout": _conversation_summary(objective_records),
        "writing_style": _style_summary(objective_records),
        "candidate_tests": {
            "diagnostic_only": True,
            **(
                next(iter(_group(candidate_records, "dataset").values()))
                if candidate_records else
                {"cases": 0, "passed": 0, "pass_rate": 0.0, "mean_score": 0.0}
            ),
            "by_tier": _group(candidate_records, "difficulty"),
        },
        "context_window": _context_window_summary(context_window_records),
        "representative_failures": samples,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_results.py RESULTS_ANONYMIZED.json", file=sys.stderr)
        return 2
    try:
        output = summarize(Path(sys.argv[1]))
    except Exception:
        print("could not summarize anonymized benchmark results", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

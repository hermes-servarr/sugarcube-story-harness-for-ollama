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


def summarize(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("expected a JSON array of result objects")
    records: list[dict[str, Any]] = data
    scores = [float(row.get("normalized_score", 0.0)) for row in records]
    passed = sum(row.get("status") == "PASS" for row in records)
    failures = Counter(
        str(row.get("failure_category") or "unspecified")
        for row in records
        if row.get("status") != "PASS"
    )
    samples = []
    for row in sorted(
        (item for item in records if item.get("status") != "PASS"),
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
    total = len(records)
    return {
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "mean_score": round(statistics.fmean(scores), 4) if scores else 0.0,
        "failure_categories": dict(failures.most_common()),
        "by_model_alias": _group(records, "model_alias"),
        "by_variant": _group(records, "subcategory"),
        "by_direction": _group(records, "difficulty"),
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

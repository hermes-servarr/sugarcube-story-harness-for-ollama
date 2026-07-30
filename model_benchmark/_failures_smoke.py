"""Functional validation script for model_benchmark.failures (not a pytest test).

Exercises every public function with both dict-shaped and dataclass-shaped
records, covers the four required capabilities (grouping, classification,
CSV export, per-case detail) and the bonus summary CSV, and asserts the key
invariants. Run with ``uv run python model_benchmark/_failures_smoke.py``.
"""
from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from model_benchmark.failures import (
    BENCHMARK_FAILURES,
    CSV_COLUMNS,
    FAILURE_STATUSES,
    INFRASTRUCTURE_FAILURES,
    SUMMARY_COLUMNS,
    classify_failure,
    get_failure_detail,
    group_failures,
    infer_failure_category,
    is_failure,
    write_failures_csv,
    write_failure_summary_csv,
)
from model_benchmark.schema import FailureGroup

ALL_CATEGORIES_ALLOWED = BENCHMARK_FAILURES | INFRASTRUCTURE_FAILURES | {"none"}


# ── fixtures: dict and dataclass shapes ──────────────────────────────────

@dataclass(frozen=True)
class LegacyResult:
    """Mimics the scoring.ModelRunResult shape (no failure_category field)."""
    model_name: str
    variant: str
    direction: str
    run_index: int
    raw_response: str = ""
    overall_pass: bool = False
    elapsed_seconds: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class RichResult:
    """Mimics schema.ResultRecord (has failure_category + status)."""
    test_id: str
    model_name: str
    status: str
    failure_category: str
    capability: str = "sugarcube"
    dataset: str = "fixture"
    variant: str = "compact"
    direction: str = "A"
    run_index: int = 0
    elapsed_seconds: float = 1.2
    error_details: str = ""
    score: float = 0.0
    timestamp_start: str = "2026-07-30T00:00:00Z"
    model_alias: str = ""


DICT_RECORDS: list[dict[str, Any]] = [
    {"test_id": "t1", "model_name": "llama3", "status": "FAIL",
     "failure_category": "instruction_following", "capability": "sugarcube",
     "dataset": "fixture", "error_details": "model ignored directive",
     "timestamp_start": "2026-07-30T00:00:00Z", "normalized_score": 0.2,
     "variant": "compact", "direction": "A", "run_index": 0,
     "elapsed_seconds": 2.1},
    {"test_id": "t2", "model_name": "llama3", "status": "TIMEOUT",
     "failure_category": "timeout", "capability": "sugarcube",
     "error_details": "request timed out after 60s",
     "timestamp_start": "2026-07-30T00:01:00Z", "normalized_score": 0.0,
     "variant": "full", "direction": "B", "run_index": 1,
     "elapsed_seconds": 60.0},
    {"test_id": "t3", "model_name": "mistral", "status": "ERROR",
     "failure_category": "network", "capability": "sugarcube",
     "error_details": "ConnectionError: connection refused to http://localhost:11434",
     "timestamp_start": "2026-07-30T00:02:00Z", "normalized_score": 0.0,
     "variant": "json", "direction": "C", "run_index": 0,
     "elapsed_seconds": 0.5},
    {"test_id": "t4", "model_name": "mistral", "status": "PASS",
     "failure_category": "none", "capability": "sugarcube",
     "error_details": "",
     "timestamp_start": "2026-07-30T00:03:00Z", "normalized_score": 1.0},
    {"test_id": "t5", "model_name": "llama3", "status": "FAIL",
     "failure_category": "formatting", "capability": "sugarcube",
     "error_details": "output used markdown **bold** instead of ''bold''",
     "timestamp_start": "2026-07-30T00:04:00Z", "normalized_score": 0.5,
     "variant": "compact", "direction": "A", "run_index": 1,
     "elapsed_seconds": 1.8},
    # Legacy dict: no status, no failure_category — rely on overall_pass + error.
    {"model_name": "phi3", "variant": "full", "direction": "B", "run_index": 0,
     "overall_pass": False, "error": "Ollama returned 500 Internal Server Error",
     "elapsed_seconds": 0.3},
]


DATACLASS_RECORDS: list[Any] = [
    RichResult(test_id="d1", model_name="llama3", status="FAIL",
               failure_category="hallucination", error_details="fabricated citation",
               score=0.1),
    RichResult(test_id="d2", model_name="llama3", status="TIMEOUT",
               failure_category="timeout", error_details="timed out",
               score=0.0, variant="full", direction="B", run_index=1),
    LegacyResult(model_name="phi3", variant="json", direction="C", run_index=2,
                 overall_pass=False, error="ConnectionError: refused"),
]


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print(f"  ok: {msg}")


# ── 1. is_failure ──────────────────────────────────────────────────────────

print("[1] is_failure")
check(not is_failure({"status": "PASS", "failure_category": "none"}), "PASS not failure")
check(not is_failure({"status": "SKIPPED"}), "SKIPPED not failure")
check(is_failure({"status": "FAIL"}), "FAIL is failure")
check(is_failure({"status": "TIMEOUT"}), "TIMEOUT is failure")
check(is_failure({"overall_pass": False}), "overall_pass False is failure")
check(is_failure({"error": "boom"}), "non-empty error is failure")
check(is_failure({"failure_category": "timeout"}), "non-none category is failure")
check(not is_failure({"overall_pass": True}), "overall_pass True not failure")

# ── 2. classify_failure ───────────────────────────────────────────────────

print("[2] classify_failure")
check(classify_failure({"status": "FAIL", "failure_category": "instruction_following"}) == "benchmark",
      "instruction_following -> benchmark")
check(classify_failure({"status": "TIMEOUT", "failure_category": "timeout"}) == "infrastructure",
      "timeout -> infrastructure")
check(classify_failure({"status": "ERROR", "failure_category": "network"}) == "infrastructure",
      "network -> infrastructure")
check(classify_failure({"status": "PASS", "failure_category": "none"}) == "none",
      "pass -> none")
# Inference fallback: legacy record with infra error text.
check(classify_failure({"overall_pass": False, "error": "connection refused"}) == "infrastructure",
      "inferred infra (network) from error text")
# Inference fallback: legacy record with no infra signature.
check(classify_failure({"overall_pass": False}) == "benchmark",
      "inferred benchmark when no infra signature")

# ── 3. infer_failure_category ─────────────────────────────────────────────

print("[3] infer_failure_category")
check(infer_failure_category({"status": "TIMEOUT"}) == "timeout", "TIMEOUT -> timeout")
check(infer_failure_category({"status": "INVALID"}) == "invalid_test_data", "INVALID -> invalid_test_data")
check(infer_failure_category({"status": "CANCELLED"}) == "internal_exception", "CANCELLED -> internal_exception")
check(infer_failure_category({"status": "FAIL"}) == "instruction_following", "FAIL -> instruction_following")
check(infer_failure_category({"status": "ERROR", "error": "oom killed"}) == "internal_exception", "oom -> internal_exception")
check(infer_failure_category({"status": "ERROR", "error": "rate limit exceeded"}) == "rate_limit", "rate limit -> rate_limit")
check(infer_failure_category({"status": "ERROR", "error": "unauthorized: 401"}) == "auth_error", "401 -> auth_error")
check(infer_failure_category({"status": "ERROR", "error": "connection refused"}) == "network", "connection refused -> network")
check(infer_failure_category({"status": "ERROR", "error": "provider returned 500"}) == "provider_error", "500 -> provider_error")
check(infer_failure_category({"status": "PASS", "failure_category": "none"}) == "none", "pass -> none")
check(infer_failure_category({"status": "PASS"}) == "none", "clean pass -> none")

# ── 4. group_failures ──────────────────────────────────────────────────────

print("[4] group_failures")
groups = group_failures(DICT_RECORDS, evaluated_total=6)
check(len(groups) > 0, "produces groups")
check(all(isinstance(g, FailureGroup) for g in groups), "all groups are FailureGroup")
# Sorted by case_count desc.
counts = [g.case_count for g in groups]
check(counts == sorted(counts, reverse=True), "groups sorted by count desc")
# instruction_following appears (t1).
cats = {g.category for g in groups}
check("instruction_following" in cats, "instruction_following grouped")
check("timeout" in cats, "timeout grouped")
check("network" in cats, "network grouped")
check("formatting" in cats, "formatting grouped")
# PASS record (t4) not in any group.
all_grouped_ids: set[str] = set()
for g in groups:
    all_grouped_ids.update(g.representative_examples)
check("t4" not in all_grouped_ids, "PASS record t4 excluded from groups")
# failure_class correct per group.
for g in groups:
    if g.category in INFRASTRUCTURE_FAILURES:
        check(g.failure_class == "infrastructure", f"{g.category} class=infrastructure")
    else:
        check(g.failure_class == "benchmark", f"{g.category} class=benchmark")
# severity is one of the four allowed.
for g in groups:
    check(g.severity in {"critical", "high", "medium", "low"}, f"{g.category} severity valid")
# representative_examples limited.
for g in groups:
    check(len(g.representative_examples) <= 5, f"{g.category} examples <= 5")

# Dataclass records also group.
groups_dc = group_failures(DATACLASS_RECORDS, evaluated_total=len(DATACLASS_RECORDS))
check(len(groups_dc) > 0, "dataclass records produce groups")
dc_cats = {g.category for g in groups_dc}
check("hallucination" in dc_cats, "hallucination grouped from dataclass")
check("timeout" in dc_cats, "timeout grouped from dataclass")
# Legacy LegacyResult has no failure_category -> inferred (network from "refused").
check("network" in dc_cats, "legacy record inferred as network")

# ── 5. get_failure_detail ──────────────────────────────────────────────────

print("[5] get_failure_detail")
detail = get_failure_detail(DICT_RECORDS[0])
check(set(detail.keys()) == set([
    "case_id", "model", "status", "category", "classification", "error_message",
    "timestamp", "score", "capability", "dataset", "variant", "direction",
    "run_index", "elapsed_seconds",
]), "detail keys stable")
check(detail["case_id"] == "t1", "case_id from test_id")
check(detail["model"] == "llama3", "model from model_name")
check(detail["status"] == "FAIL", "status preserved")
check(detail["category"] == "instruction_following", "category preserved")
check(detail["classification"] == "benchmark", "classification computed")
check(detail["error_message"] == "model ignored directive", "error_message")
check(detail["timestamp"] == "2026-07-30T00:00:00Z", "timestamp")
check(detail["score"] == "0.2", "normalized_score -> score")

# Dataclass detail.
detail_dc = get_failure_detail(DATACLASS_RECORDS[0])
check(detail_dc["case_id"] == "d1", "dataclass case_id")
check(detail_dc["model"] == "llama3", "dataclass model")
check(detail_dc["category"] == "hallucination", "dataclass category")
check(detail_dc["classification"] == "benchmark", "dataclass classification")

# Legacy composite case_id fallback.
legacy_rec = {"model_name": "phi3", "variant": "full", "direction": "B",
              "run_index": 0, "overall_pass": False, "error": "boom"}
detail_legacy = get_failure_detail(legacy_rec)
check("|" in detail_legacy["case_id"], "legacy composite case_id")
check(detail_legacy["model"] == "phi3", "legacy model")
check(detail_legacy["status"] == "FAIL", "legacy status inferred FAIL")

# Anonymized: model_alias preferred, error redacted.
anon_rec = {
    "test_id": "x1", "model_name": "secret-model", "model_alias": "Model_A",
    "status": "ERROR", "failure_category": "network",
    "error_details": "ConnectionError: http://10.0.0.5:11434 refused",
}
detail_anon = get_failure_detail(anon_rec, anonymized=True)
check(detail_anon["model"] == "Model_A", "anonymized model alias preferred")
check("[REDACTED_URL]" in detail_anon["error_message"], "url redacted")
check("10.0.0.5" not in detail_anon["error_message"], "host scrubbed from error")

# ── 6. write_failures_csv ──────────────────────────────────────────────────

print("[6] write_failures_csv")
with tempfile.TemporaryDirectory() as tmpdir:
    csv_path = os.path.join(tmpdir, "sub", "failures.csv")
    n = write_failures_csv(DICT_RECORDS + DATACLASS_RECORDS, csv_path)
    check(n >= 5, f"wrote {n} failure rows (>= 5 expected)")
    check(os.path.exists(csv_path), "CSV file exists at nested path")
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    check(reader.fieldnames is not None, "has header")
    check(list(reader.fieldnames) == list(CSV_COLUMNS), "CSV columns match spec")
    # All rows have the required columns and non-empty category.
    for row in rows:
        check(row["category"] != "", "every row has a category")
        check(row["classification"] in {"benchmark", "infrastructure"}, "row classification valid")
        check(row["count"] != "", "row has count")
    # A PASS row should not appear.
    case_ids = {row["case_id"] for row in rows}
    check("t4" not in case_ids, "PASS row excluded from CSV")
    # The header includes the spec-required columns.
    for required in ("category", "classification", "count"):
        check(required in reader.fieldnames, f"required column {required} present")

    # ── 7. write_failure_summary_csv ────────────────────────────────────────
    print("[7] write_failure_summary_csv")
    summary_path = os.path.join(tmpdir, "failures_summary.csv")
    ns = write_failure_summary_csv(DICT_RECORDS + DATACLASS_RECORDS, summary_path)
    check(ns >= 1, f"wrote {ns} summary rows")
    check(os.path.exists(summary_path), "summary CSV exists")
    with open(summary_path, newline="") as fh:
        sreader = csv.DictReader(fh)
        srows = list(sreader)
    check(list(sreader.fieldnames) == list(SUMMARY_COLUMNS), "summary columns match")
    check(len(srows) == ns, "summary row count matches return")
    for srow in srows:
        check(srow["category"] in ALL_CATEGORIES_ALLOWED, f"summary category {srow['category']} valid")

# ── 8. empty / edge cases ───────────────────────────────────────────────────

print("[8] edge cases")
check(group_failures([]) == [], "empty input -> no groups")
check(group_failures([{"status": "PASS"}]) == [], "all-pass input -> no groups")
tmp = tempfile.mktemp(suffix=".csv")
n_empty = write_failures_csv([], tmp)
check(n_empty == 0, "empty input writes 0 rows")
os.unlink(tmp)
_empty_summary = tempfile.mktemp(suffix=".csv")
ns_empty = write_failure_summary_csv([], _empty_summary)
check(ns_empty == 0, "empty summary writes 0 rows")
os.unlink(_empty_summary)

print("\nALL CHECKS PASSED")

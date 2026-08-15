import asyncio
import json

import pytest
from fastapi import HTTPException

from harness.server import app as server_app


def _write_run(root, run_id="20260813_fixture"):
    directory = root / run_id
    directory.mkdir(parents=True)
    (directory / "run_manifest.json").write_text(json.dumps({
        "run_id": "fixture-run",
        "benchmark_name": "refactor-core",
        "benchmark_version": "1",
        "started_at": "2026-08-13T12:00:00Z",
    }), encoding="utf-8")
    (directory / "results_internal.jsonl").write_text(
        json.dumps({"test_id": "one", "status": "PASS"}) + "\n" +
        json.dumps({"test_id": "two", "status": "FAIL"}) + "\n",
        encoding="utf-8",
    )
    (directory / "summary_internal.md").write_text("# Fixture summary\n", encoding="utf-8")
    return directory


def test_benchmark_runs_list_and_paginated_detail(tmp_path, monkeypatch):
    _write_run(tmp_path)
    monkeypatch.setenv("HARNESS_BENCHMARK_OUTPUTS", str(tmp_path))

    listing = asyncio.run(server_app.benchmark_runs())
    detail = asyncio.run(server_app.benchmark_run("20260813_fixture", offset=1, limit=1))

    assert listing == {"runs": [{
        "id": "20260813_fixture",
        "run_id": "fixture-run",
        "benchmark_name": "refactor-core",
        "benchmark_version": "1",
        "started_at": "2026-08-13T12:00:00Z",
        "result_count": 2,
        "has_comparison": False,
    }]}
    assert detail["manifest"]["run_id"] == "fixture-run"
    assert detail["summary"] == "# Fixture summary\n"
    assert detail["results"] == [{"test_id": "two", "status": "FAIL"}]
    assert detail["pagination"] == {"offset": 1, "limit": 1, "total": 2}


def test_benchmark_comparison_is_read_verbatim_and_paths_are_confined(tmp_path, monkeypatch):
    directory = _write_run(tmp_path)
    comparison = {"baseline_run_id": "old", "current_run_id": "fixture-run"}
    (directory / "comparison.json").write_text(json.dumps(comparison), encoding="utf-8")
    monkeypatch.setenv("HARNESS_BENCHMARK_OUTPUTS", str(tmp_path))

    assert asyncio.run(
        server_app.benchmark_run_comparison("20260813_fixture")
    ) == comparison
    with pytest.raises(HTTPException) as error:
        asyncio.run(server_app.benchmark_run("../outside"))
    assert error.value.status_code == 404


def test_benchmark_detail_rejects_unbounded_page(tmp_path, monkeypatch):
    _write_run(tmp_path)
    monkeypatch.setenv("HARNESS_BENCHMARK_OUTPUTS", str(tmp_path))

    with pytest.raises(HTTPException) as error:
        asyncio.run(server_app.benchmark_run("20260813_fixture", limit=501))
    assert error.value.status_code == 422

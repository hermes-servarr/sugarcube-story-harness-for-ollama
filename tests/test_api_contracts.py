import json
from pathlib import Path

from scripts.export_openapi import rendered_openapi


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"


def test_committed_openapi_document_matches_backend():
    assert (UI / "openapi.json").read_text(encoding="utf-8") == rendered_openapi()


def test_frontend_build_enforces_generated_contract_freshness():
    package = json.loads((UI / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert "contracts:check" in scripts["build"]
    assert "export_openapi.py --check" in scripts["contracts:check"]
    assert "generate-contracts.mjs --check" in scripts["contracts:check"]
    assert "openapi-typescript" in package["devDependencies"]


def test_frontend_consumes_authoritative_generated_contracts():
    typescript = (UI / "src" / "types.ts").read_text(encoding="utf-8")
    generated = (UI / "src" / "generated" / "openapi.ts").read_text(encoding="utf-8")
    assert 'from "./generated/openapi"' in typescript
    assert 'components["schemas"]["ExperienceProfile"]' in typescript
    assert 'components["schemas"]["DraftRecord"]' in typescript
    assert 'components["schemas"]["PassagePlanRecordResponse"]' in typescript
    assert 'components["schemas"]["BenchmarkRunDetailResponse"]' in typescript
    assert "ExperienceProfile:" in generated
    assert "PassagePlan:" in generated
    assert "DraftRecord:" in generated
    assert "PassagePlanRecordResponse:" in generated
    assert "BenchmarkRunDetailResponse:" in generated


def test_core_ui_endpoints_publish_authoritative_response_models():
    document = json.loads(rendered_openapi())
    expected = {
        ("/api/plans", "post"): "PassagePlanRecordResponse",
        ("/api/plans/{plan_id}/revisions/{revision}", "get"): "PassagePlanRecordResponse",
        ("/api/typed/generate", "post"): "DraftRecord",
        ("/api/drafts/{draft_id}/{revision}", "get"): "DraftRecord",
        ("/api/drafts/{draft_id}/{revision}/commit", "post"): "TypedCommitResponse",
        ("/api/drafts/{draft_id}/{revision}/facts/{fact_key}/decision", "post"): "TypedFactDecisionResponse",
        ("/api/benchmarks/runs", "get"): "BenchmarkRunsResponse",
        ("/api/benchmarks/runs/{run_id}", "get"): "BenchmarkRunDetailResponse",
        ("/api/capability-cards", "get"): "CapabilityCardsResponse",
    }
    for (path, method), schema_name in expected.items():
        schema = document["paths"][path][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert schema["$ref"] == f"#/components/schemas/{schema_name}"

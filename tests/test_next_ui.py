import asyncio
from pathlib import Path

from harness.models import HarnessConfig
from harness.project import ProjectPaths, init_project, save_config
from harness.server import app as server_app


def test_schema_fallback_stays_legacy_for_historical_partial_configs():
    # The schema fallback remains conservative for loading historical partial
    # configs; project initialization and an unconfigured server default next.
    assert HarnessConfig().authoring_ui == "legacy"


def test_explicit_ui_routes_and_configured_cutover(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("HARNESS_AUTHORING_UI", raising=False)

    legacy = asyncio.run(server_app.legacy_spa())
    next_ui = asyncio.run(server_app.next_spa())
    default = asyncio.run(server_app.spa())

    assert "Story Harness Next" not in legacy.body.decode()
    assert "Story Harness Next" in next_ui.body.decode()
    assert default.body == next_ui.body

    paths = ProjectPaths(tmp_path)
    save_config(paths, HarnessConfig(authoring_ui="legacy"))
    configured = asyncio.run(server_app.spa())
    assert configured.body == legacy.body


def test_unconfigured_server_defaults_to_next(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("HARNESS_AUTHORING_UI", raising=False)

    default = asyncio.run(server_app.spa())
    next_ui = asyncio.run(server_app.next_spa())

    assert default.body == next_ui.body


def test_environment_override_is_reversible(tmp_path, monkeypatch):
    init_project(tmp_path)
    save_config(ProjectPaths(tmp_path), HarnessConfig(authoring_ui="next"))
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("HARNESS_AUTHORING_UI", "legacy")

    overridden = asyncio.run(server_app.spa())
    legacy = asyncio.run(server_app.legacy_spa())

    assert overridden.body == legacy.body


def test_next_ui_sources_use_typed_api_and_no_external_runtime_assets():
    root = Path(__file__).parents[1]
    index = (root / "harness/server/ui/index.html").read_text(encoding="utf-8")
    source = (root / "ui/src/app/App.tsx").read_text(encoding="utf-8")
    client = (root / "ui/src/api.ts").read_text(encoding="utf-8")

    assert "https://" not in index
    assert "/next-static/assets/app.js" in index
    assert "/api/typed/generate" in client
    assert '"/api/plans"' in client
    assert "approvePassagePlan" in client
    assert "/api/drafts/" in client
    assert "latestDraft" in client
    assert "api.latestDraft(id)" in source
    assert "rejectDraft" in client
    assert "/api/experience-profile/preview" in client
    assert "/api/experience-profile/revisions" in client
    assert "/api/topology/locations" in client
    assert "/api/topology/routes" in client
    assert "/api/simulations" in client
    assert "/api/simulation-fixtures" in client
    assert "/api/ollama/status" in client
    assert "/api/ollama/test-model" in client
    assert "/api/media/import" in client
    assert "mediaPreviewUrl" in client
    assert "expected_draft_fingerprint" in client
    assert "preview_fingerprint" in client
    assert "aria-current" in source
    assert 'revision: storedRevision + 1' in source
    assert "api.previewExperienceProfile(storedRevision, profile)" in source
    assert "api.saveExperienceProfile(storedRevision, candidate" in source
    assert 'aria-invalid={Boolean(overridesError)}' in source
    assert 'role="alert"' in source
    assert "navigationPrefix" in source
    assert "aria-keyshortcuts" in source
    assert "sessionStorage" in source
    assert '"draft_superseded"' in source
    assert "Save the visible edits before validation" in source
    assert "file.rel_path" in source
    assert "Import project media" in source
    assert "harness.next.pending_facts" in source
    assert "parent_fingerprint_conflict" in source
    assert "Approve plan and generate" in source
    assert "media-preview" in source
    assert "Add named initial state" in source
    assert "Run fixture" in source

import asyncio
import json

import pytest
from fastapi import HTTPException

from harness.generation import (
    ExperienceProfile,
    ExperienceProfileConflict,
    ExperienceProfileStore,
    preview_experience_migration,
)
from harness.models import PassageEntry, StoryGraph
from harness.project import ProjectPaths, init_project, load_config, load_story
from harness.server import app as server_app


def test_new_project_persists_explicit_story_driven_baseline(tmp_path):
    paths = init_project(tmp_path)
    profile = ExperienceProfileStore(paths.experience_profiles_dir).get()

    assert profile.revision == 1
    assert profile.mode.value == "story_driven"


def test_profile_store_is_immutable_and_detects_tampering(tmp_path):
    store = ExperienceProfileStore(tmp_path)
    baseline = ExperienceProfile.story_driven()
    store.ensure_baseline(baseline)
    saved = store.put(
        ExperienceProfile.sandbox().model_copy(update={"revision": 2}),
        expected_revision=1,
    )

    with pytest.raises(ExperienceProfileConflict, match="expected revision"):
        store.put(
            ExperienceProfile.hybrid().model_copy(update={"revision": 3}),
            expected_revision=1,
        )

    path = tmp_path / "2.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["profile"]["narrative_pressure"] = 0.7
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ExperienceProfileConflict, match="fingerprint"):
        store.get(saved.revision)


def test_migration_preview_reports_impacts_without_rewriting_graph():
    graph = StoryGraph(
        start_passage="start",
        passages={
            "start": PassageEntry(file="start.tw", arc="main", children=["start"]),
        },
    )
    before = graph.model_dump_json()
    current = ExperienceProfile.sandbox()
    candidate = ExperienceProfile.story_driven().model_copy(update={"revision": 2})

    preview = preview_experience_migration(current, candidate, graph)

    assert preview.graph_rewrite_required is False
    assert {impact.code for impact in preview.impacts} >= {
        "experience_mode_changed", "required_ending_missing", "cyclic_routes_review",
        "graph_not_rewritten",
    }
    assert graph.model_dump_json() == before


def test_experience_profile_api_requires_fresh_preview_and_updates_projection(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    story_before = paths.story_json.read_bytes()
    current = asyncio.run(server_app.get_experience_profile())
    candidate = ExperienceProfile.sandbox().model_copy(update={"revision": 2})
    request = server_app.ExperienceProfilePreviewRequest(
        expected_revision=1,
        profile=candidate,
    )
    preview = asyncio.run(server_app.preview_experience_profile(request))
    saved = asyncio.run(server_app.create_experience_profile_revision(
        server_app.ExperienceProfileRevisionRequest(
            expected_revision=1,
            profile=candidate,
            preview_fingerprint=preview["preview_fingerprint"],
        )
    ))

    assert current["source"] == "stored"
    assert saved["profile"]["revision"] == 2
    assert saved["profile"]["mode"] == "sandbox"
    assert paths.story_json.read_bytes() == story_before
    assert load_config(paths).experience_mode == "sandbox"

    changed_candidate = ExperienceProfile.hybrid().model_copy(update={"revision": 3})
    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.create_experience_profile_revision(
            server_app.ExperienceProfileRevisionRequest(
                expected_revision=2,
                profile=changed_candidate,
                preview_fingerprint=preview["preview_fingerprint"],
            )
        ))
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "experience_profile_preview_stale"
    assert load_story(paths).model_dump_json() == StoryGraph.model_validate_json(
        story_before.decode("utf-8")
    ).model_dump_json()


def test_structured_profile_conflict_survives_http_error_mapping():
    response = asyncio.run(server_app._http_exc(None, HTTPException(
        409,
        detail={"code": "experience_profile_preview_stale", "message": "Preview is stale."},
    )))

    assert response.status_code == 409
    assert json.loads(response.body) == {
        "error": "experience_profile_preview_stale",
        "detail": "Preview is stale.",
    }


def test_legacy_config_api_cannot_bypass_profile_migration_preview(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(server_app.update_config({"experience_mode": "sandbox"}))

    assert rejected.value.status_code == 409
    assert rejected.value.detail["code"] == "experience_profile_preview_required"

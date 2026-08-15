import asyncio
import threading

import pytest
from fastapi import HTTPException

from harness.project import init_project
from harness.server import app as server_app


def test_plan_creates_are_fingerprint_guarded(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    initial = asyncio.run(server_app.get_plan())
    beat = asyncio.run(server_app.create_beat(server_app.BeatRequest(
        text="The harbor closes.",
        act="Act 1",
        expected_story_fingerprint=initial["story_fingerprint"],
    )))

    assert beat["beat"]["text"] == "The harbor closes."
    assert beat["story_fingerprint"] != initial["story_fingerprint"]
    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.create_arc_endpoint(server_app.CreateArcRequest(
            name="escape",
            goal="Leave the harbor.",
            expected_story_fingerprint=initial["story_fingerprint"],
        )))
    assert stale.value.detail["code"] == "story_plan_conflict"

    arc = asyncio.run(server_app.create_arc_endpoint(server_app.CreateArcRequest(
        name="escape",
        goal="Leave the harbor.",
        expected_story_fingerprint=beat["story_fingerprint"],
    )))
    assert arc["arc"].endswith("_escape")
    assert arc["story_fingerprint"] != beat["story_fingerprint"]


def test_concurrent_plan_creates_allow_exactly_one_writer(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    fingerprint = asyncio.run(server_app.get_plan())["story_fingerprint"]
    barrier = threading.Barrier(2)
    results = []

    def worker(text):
        barrier.wait()
        try:
            results.append(asyncio.run(server_app.create_beat(server_app.BeatRequest(
                text=text, expected_story_fingerprint=fingerprint,
            ))))
        except HTTPException as exc:
            results.append(exc)

    threads = [threading.Thread(target=worker, args=(text,)) for text in ("First", "Second")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    successes = [item for item in results if not isinstance(item, HTTPException)]
    conflicts = [item for item in results if isinstance(item, HTTPException)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert conflicts[0].detail["code"] == "story_plan_conflict"


def test_plan_validation_errors_have_stable_codes(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    fingerprint = asyncio.run(server_app.get_plan())["story_fingerprint"]

    with pytest.raises(HTTPException) as beat_error:
        asyncio.run(server_app.create_beat(server_app.BeatRequest(
            text="   ", expected_story_fingerprint=fingerprint,
        )))
    with pytest.raises(HTTPException) as arc_error:
        asyncio.run(server_app.create_arc_endpoint(server_app.CreateArcRequest(
            name="!!!", expected_story_fingerprint=fingerprint,
        )))

    assert beat_error.value.detail["code"] == "invalid_beat_text"
    assert arc_error.value.detail["code"] == "invalid_arc_name"


def test_plan_updates_deletes_and_scenes_are_fingerprint_guarded(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    initial = asyncio.run(server_app.get_plan())
    beat_result = asyncio.run(server_app.create_beat(server_app.BeatRequest(
        text="Open the sealed gate.",
        expected_story_fingerprint=initial["story_fingerprint"],
    )))
    beat_id = beat_result["beat"]["id"]
    arc_result = asyncio.run(server_app.create_arc_endpoint(server_app.CreateArcRequest(
        name="gate",
        expected_story_fingerprint=beat_result["story_fingerprint"],
    )))
    arc_name = arc_result["arc"]

    with pytest.raises(HTTPException) as stale_update:
        asyncio.run(server_app.edit_beat(beat_id, server_app.BeatUpdateRequest(
            text="Stale edit",
            expected_story_fingerprint=initial["story_fingerprint"],
        )))
    assert stale_update.value.status_code == 409
    assert stale_update.value.detail["code"] == "story_plan_conflict"

    updated_arc = asyncio.run(server_app.edit_arc_plan(arc_name, server_app.ArcPlanRequest(
        goal="Cross the threshold.",
        beat_ids=[beat_id],
        expected_story_fingerprint=arc_result["story_fingerprint"],
    )))
    scene_result = asyncio.run(server_app.create_scene(arc_name, server_app.SceneRequest(
        title="At the gate",
        beat_ids=[beat_id],
        expected_story_fingerprint=updated_arc["story_fingerprint"],
    )))
    scene_id = scene_result["scene"]["id"]
    updated_scene = asyncio.run(server_app.edit_scene(
        arc_name,
        scene_id,
        server_app.SceneUpdateRequest(
            summary="The lock yields.",
            expected_story_fingerprint=scene_result["story_fingerprint"],
        ),
    ))
    deleted_scene = asyncio.run(server_app.remove_scene(
        arc_name,
        scene_id,
        server_app.PlanDeleteRequest(expected_story_fingerprint=updated_scene["story_fingerprint"]),
    ))
    deleted_beat = asyncio.run(server_app.remove_beat(
        beat_id,
        server_app.PlanDeleteRequest(expected_story_fingerprint=deleted_scene["story_fingerprint"]),
    ))

    assert deleted_beat["status"] == "deleted"
    overview = asyncio.run(server_app.get_plan())
    assert overview["beats"] == []
    assert overview["arcs"][0]["scenes"] == []

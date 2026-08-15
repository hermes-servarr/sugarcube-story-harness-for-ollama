import asyncio

import pytest
from fastapi import HTTPException

from harness.project import init_project
from harness.server import app as server_app


def test_character_create_edit_and_stale_conflict(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    created = asyncio.run(server_app.create_character(server_app.NewCharacterRequest(
        id="Captain Vale", name="Captain Vale", description="Harbor master.",
    )))
    loaded = asyncio.run(server_app.get_character("captain_vale"))
    saved = asyncio.run(server_app.save_character(
        "captain_vale",
        server_app.SaveCharacterRequest(
            content=loaded["content"] + "\nKeeps the tide ledger.\n",
            expected_content_fingerprint=loaded["content_fingerprint"],
        ),
    ))

    assert created["id"] == "captain_vale"
    assert len(saved["content_fingerprint"]) == 64
    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.save_character(
            "captain_vale",
            server_app.SaveCharacterRequest(
                content="stale overwrite",
                expected_content_fingerprint=loaded["content_fingerprint"],
            ),
        ))
    assert stale.value.detail["code"] == "character_content_conflict"
    with pytest.raises(HTTPException) as duplicate:
        asyncio.run(server_app.create_character(server_app.NewCharacterRequest(id="captain_vale")))
    assert duplicate.value.detail["code"] == "character_exists"


def test_lore_create_edit_stale_conflict_and_safe_identity(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)
    created = asyncio.run(server_app.create_lore(server_app.NewLoreRequest(
        category="Locations", id="Tide Archive", title="Tide Archive",
    )))
    loaded = asyncio.run(server_app.get_lore_entry("locations", "tide_archive"))
    asyncio.run(server_app.save_lore_entry(
        "locations",
        "tide_archive",
        server_app.SaveLoreRequest(
            content=loaded["content"] + "\nThe ledgers are sealed.\n",
            expected_content_fingerprint=loaded["content_fingerprint"],
        ),
    ))

    assert created == {"status": "created", "category": "locations", "id": "tide_archive"}
    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.save_lore_entry(
            "locations",
            "tide_archive",
            server_app.SaveLoreRequest(
                content="stale overwrite",
                expected_content_fingerprint=loaded["content_fingerprint"],
            ),
        ))
    assert stale.value.detail["code"] == "lore_content_conflict"

    with pytest.raises(HTTPException) as unsafe:
        asyncio.run(server_app.get_lore_entry("..", "config"))
    assert unsafe.value.status_code == 422

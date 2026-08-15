import asyncio

import pytest
from fastapi import HTTPException

from harness.models import MediaSlot, MediaSlots
from harness.project import init_project, save_slots
from harness.server import app as server_app


def test_media_metadata_mutation_is_atomic_and_stale_safe(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    save_slots(paths, MediaSlots(slots={
        "harbor_image": MediaSlot(passage="harbor", keywords=["fog"]),
    }))
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    loaded = asyncio.run(server_app.get_slots())["harbor_image"]
    saved = asyncio.run(server_app.update_slot_meta(
        "harbor_image",
        server_app.SlotMetaRequest(
            expected_slot_fingerprint=loaded["fingerprint"],
            description="A fogbound harbor.",
            alt="Lanterns in harbor fog",
        ),
    ))

    assert saved["status"] == "ok"
    changed = asyncio.run(server_app.get_slots())["harbor_image"]
    assert changed["alt"] == "Lanterns in harbor fog"
    assert changed["fingerprint"] != loaded["fingerprint"]

    with pytest.raises(HTTPException) as stale:
        asyncio.run(server_app.update_slot_meta(
            "harbor_image",
            server_app.SlotMetaRequest(
                expected_slot_fingerprint=loaded["fingerprint"],
                caption="Stale caption",
            ),
        ))
    assert stale.value.detail["code"] == "media_slot_conflict"


def test_media_import_listing_resolution_and_slot_preview(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"fixture-png")
    save_slots(paths, MediaSlots(slots={
        "harbor_image": MediaSlot(passage="harbor", keywords=["fog"]),
    }))
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    imported = asyncio.run(server_app.import_media(server_app.ImportMediaRequest(
        src_path=str(source), dest_name="harbor.png",
    )))
    files = asyncio.run(server_app.media_files())["files"]
    loaded = asyncio.run(server_app.get_slots())["harbor_image"]
    asyncio.run(server_app.resolve("harbor_image", server_app.ResolveSlotRequest(
        resolved_path=imported["rel_path"],
        expected_slot_fingerprint=loaded["fingerprint"],
    )))
    preview = asyncio.run(server_app.preview_media_slot("harbor_image"))

    assert imported == {"status": "imported", "rel_path": "media/harbor.png"}
    assert files == [{
        "name": "harbor.png", "rel_path": "media/harbor.png",
        "type": "image", "size": len(b"fixture-png"),
    }]
    assert preview.path == paths.media_dir / "harbor.png"

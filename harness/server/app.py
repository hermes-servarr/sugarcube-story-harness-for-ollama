"""FastAPI application — single-page story harness UI."""
from __future__ import annotations
import json
import hashlib
import re
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..compile import compile_story, find_tweego
from ..media import (
    MEDIA_EXTS,
    delete_slot,
    import_media_file,
    list_all_slots,
    list_media_files,
    resolve_slot,
    search_slots,
    set_slot_meta,
    unresolve_slot,
)
from ..planning import (
    add_arcs_bulk,
    add_beat,
    add_beats_bulk,
    add_scene,
    add_scenes_bulk,
    create_arc,
    delete_beat,
    delete_scene,
    import_story_points,
    plan_overview,
    set_acts,
    set_arc_plan,
    set_open_questions,
    set_passage_beats,
    StoryPlanConflict,
    story_fingerprint,
    update_beat,
    update_scene,
)
from ..models import PASSAGE_TYPES, CharacterPresent, HarnessConfig, MediaSlot, SessionState
from ..generators import (
    build_prompt,
    extract_entities,
    extract_keywords,
    generate_characters_sketch,
    generate_locations_sketch,
    generate_opening,
    generate_premise,
    generate_arc_scenes,
    generate_arcs,
    generate_beats,
    generate_story_output,
    generate_tone_themes,
    generate_world,
    summarize_inspiration,
)
from ..generation import (
    BrowserChoiceExpectation,
    BrowserScenario,
    CapabilityCard,
    CompileArtifact,
    ContextPack,
    DraftConflict,
    DraftLifecycle,
    DraftNotFound,
    DraftRecord,
    DraftStore,
    ExperienceProfile,
    ExperienceProfileConflict,
    ExperienceProfileStore,
    GenerationProvenance,
    NarrativeFill,
    PassagePlan,
    PassagePlanStore,
    PlanConflict,
    PlanNotFound,
    assemble_passage_draft,
    build_legacy_passage_plan,
    compile_passage_draft,
    commit_typed_draft,
    evidence_hashes_match,
    evaluate_compile_artifact,
    generate_typed_draft,
    load_capability_cards,
    parent_fingerprint,
    preset_for_mode,
    preview_experience_migration,
    source_hashes_match,
)
from ..generation.contracts import ContinuityProposal
from ..ollama_client import call_ollama, clear_call_log, get_call_log
from ..audit import list_generations, read_generation, record_generation
from ..parsers import parse_json_object, parse_model_output
from ..prompts import (
    build_scene_choices_prompt,
    build_scene_keywords_prompt,
    build_scene_state_prompt,
    build_scene_threads_prompt,
    build_summary_prompt,
    build_story_points_prompt,
    build_suggest_names_prompt,
)
from ..rag import (
    build_index as rag_build_index,
    build_story_index as rag_build_story_index,
    index_stats as rag_index_stats,
    retrieve_inspiration,
    retrieve_story_recall,
    story_index_stats as rag_story_index_stats,
)
from ..passage import create_passage, delete_passage, rebuild_and_save, sync_manifest
from ..project import (
    _atomic_write_text,
    ProjectPaths,
    delete_character,
    delete_note,
    list_characters,
    list_lore,
    list_notes,
    init_project,
    load_character,
    load_config,
    load_lore_entity,
    load_note,
    load_session,
    load_slots,
    load_story,
    parse_yaml_frontmatter,
    save_config,
    save_note,
    save_session,
    save_slots,
    save_story,
    set_character_keywords,
    set_lore_keywords,
    write_character,
    write_lore_entity,
)
from ..validation import run_validation
from ..snapshot_delta import reconstruct_passage_snapshot
from ..simulation import (
    AuthoredAnchor,
    CharacterRuntimeState,
    CharacterStatDefinition,
    FactionState,
    LocationNode,
    EncounterCatalog,
    EncounterTemplate,
    Route,
    RuntimeSessionStore,
    SimulationError,
    SimulationFixture,
    SimulationFixtureCatalog,
    SimulationRecord,
    SimulationStoreError,
    TopologyStore,
    SystemCatalog,
    SystemRule,
    WorldTopology,
    apply_local_action,
    available_opportunities,
    complete_authored_anchor,
    create_runtime_session,
    reachable_locations,
    travel,
)

# Project root is resolved at startup — either from env var or cwd
_PROJECT_ROOT = Path(os.environ.get("HARNESS_PROJECT", ".")).resolve()

app = FastAPI(title="Sugarcube Agentic Story Harness", version="0.1.0")

_HERE = Path(__file__).parent

# Mount static directory if it exists; create it on the fly if missing so the
# server never crashes on a fresh checkout. The mount serves CSS, JS, and
# other static assets for the single-page UI.
_static_dir = _HERE / "static"
if not _static_dir.exists():
    _static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

_next_ui_dir = _HERE / "ui"
if not _next_ui_dir.exists():
    _next_ui_dir.mkdir(parents=True, exist_ok=True)
app.mount("/next-static", StaticFiles(directory=str(_next_ui_dir)), name="next-static")


# ── Error handling ─────────────────────────────────────────────────────────────
# Shared response shape so the UI can render any non-2xx uniformly:
#   { "error": "<short code>", "detail": "<human message>" }
# Bare HTTPException still works — its detail flows into the same shape.
def _error_response(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": code, "detail": detail},
    )


@app.exception_handler(HTTPException)
async def _http_exc(_: Request, exc: HTTPException) -> JSONResponse:
    code_map = {400: "bad_request", 401: "unauthorized", 403: "forbidden",
                404: "not_found", 409: "conflict", 422: "unprocessable",
                429: "rate_limited", 500: "internal_error", 502: "upstream_error",
                503: "unavailable", 504: "timeout"}
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code") or code_map.get(exc.status_code, "http_error"))
        detail = str(exc.detail.get("message") or json.dumps(exc.detail))
    else:
        code = code_map.get(exc.status_code, "http_error")
        detail = str(exc.detail)
    return _error_response(exc.status_code, code, detail)


@app.exception_handler(RequestValidationError)
async def _request_validation_exc(_: Request, exc: RequestValidationError) -> JSONResponse:
    errs = exc.errors()
    first = errs[0] if errs else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    msg = first.get("msg", "validation error")
    return _error_response(422, "invalid_request", f"{loc}: {msg}" if loc else msg)


@app.exception_handler(ValidationError)
async def _model_validation_exc(_: Request, exc: ValidationError) -> JSONResponse:
    errs = exc.errors()
    first = errs[0] if errs else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    msg = first.get("msg", "validation error")
    return _error_response(422, "invalid_data", f"{loc}: {msg}" if loc else msg)


@app.exception_handler(FileNotFoundError)
async def _fnf_exc(_: Request, exc: FileNotFoundError) -> JSONResponse:
    return _error_response(404, "file_not_found", str(exc) or "File not found.")


@app.exception_handler(PermissionError)
async def _perm_exc(_: Request, exc: PermissionError) -> JSONResponse:
    return _error_response(403, "forbidden", str(exc) or "Permission denied.")


@app.exception_handler(TimeoutError)
async def _timeout_exc(_: Request, exc: TimeoutError) -> JSONResponse:
    return _error_response(504, "timeout", str(exc) or "Operation timed out.")


@app.exception_handler(Exception)
async def _unhandled_exc(_: Request, exc: Exception) -> JSONResponse:
    # Last-resort: never leak stack traces; log on server side, surface a short
    # message to the client. ``type(exc).__name__`` gives the UI enough context
    # to triage without exposing internals.
    return _error_response(
        500, "internal_error",
        f"{type(exc).__name__}: {str(exc)[:300] or 'Unhandled error.'}",
    )


def _p() -> ProjectPaths:
    return ProjectPaths(_PROJECT_ROOT)


def _templates_path() -> Path:
    return _PROJECT_ROOT / ".harness" / "passage_templates.json"


def _slugify(text: str) -> str:
    import re as _re
    s = (text or "").strip().lower()
    s = _re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "template"


def _default_templates() -> list[dict]:
    return [
        {
            "id": "event_motion",
            "title": "Event: moving scene",
            "type": "event",
            "keywords": ["event", "motion", "image", "audio", "cinematic"],
            "body": (
                "Write an EVENT passage. Keep it punchy and cinematic.\n\n"
                "Goals:\n"
                "- One clear scene beat that feels like a moving sequence.\n"
                "- Use media suggestions for changing visuals if useful.\n"
                "- End with 2-4 choices that push the scene forward.\n"
            ),
        },
        {
            "id": "hub_location",
            "title": "Hub: revisitable location",
            "type": "hub",
            "keywords": ["hub", "location", "return", "npc"],
            "body": (
                "Write a HUB passage. This should be a revisitable location with ongoing threads.\n\n"
                "Goals:\n"
                "- Introduce the place and who is here.\n"
                "- Offer choices that let the player talk, inspect, or branch out.\n"
                "- Keep the space reusable so the story can return later.\n"
            ),
        },
        {
            "id": "room_exits",
            "title": "Room: exits + actions",
            "type": "room",
            "keywords": ["room", "exits", "navigation", "location"],
            "body": (
                "Write a ROOM passage. This is a location node with named exits.\n\n"
                "Goals:\n"
                "- Describe the room and its immediate details.\n"
                "- Make exits clear and distinct.\n"
                "- Offer choices for actions or inspection.\n"
            ),
        },
    ]


def _load_templates() -> list[dict]:
    path = _templates_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"templates": _default_templates()}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data["templates"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_templates()
    if isinstance(raw, dict):
        return raw.get("templates", []) or []
    if isinstance(raw, list):
        return raw
    return []


def _save_templates(templates: list[dict]) -> None:
    path = _templates_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"templates": templates}, indent=2), encoding="utf-8")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "project": str(_PROJECT_ROOT)}


@app.get("/api/passage-types")
async def get_passage_types():
    """List of valid passage types with short descriptions for UI dropdown."""
    descriptions = {
        "normal":       "Plain choice node.",
        "hub":          "Central node players return to.",
        "random":       "Picks one of N children at random (weighted).",
        "conditional":  "Entry gated by SugarCube expression; reroutes if false.",
        "dialogue":     "NPC exchange; choices loop back until exit.",
        "room":         "Bidirectional navigation node with named exits.",
        "event":        "One-shot scripted scene (fires once).",
        "random_event": "Fires only if random(1,100) ≤ event_odds.",
        "ending":       "Terminal node; no choices required.",
    }
    return {"types": [{"id": t, "description": descriptions.get(t, "")} for t in PASSAGE_TYPES]}


# ── Passage templates ───────────────────────────────────────────────────────

class TemplateRequest(BaseModel):
    id: Optional[str] = None
    title: str
    type: str = "normal"
    keywords: list[str] = []
    body: str = ""


@app.get("/api/templates")
async def get_templates():
    return {"templates": _load_templates()}


@app.post("/api/templates")
async def create_template(req: TemplateRequest):
    templates = _load_templates()
    tid = _slugify(req.id or req.title)
    existing_ids = {t.get("id") for t in templates}
    if tid in existing_ids:
        i = 2
        while f"{tid}_{i}" in existing_ids:
            i += 1
        tid = f"{tid}_{i}"
    ttype = req.type if req.type in PASSAGE_TYPES else "normal"
    tmpl = {
        "id": tid,
        "title": req.title.strip(),
        "type": ttype,
        "keywords": [k.strip().lower() for k in (req.keywords or []) if k.strip()],
        "body": req.body or "",
    }
    templates.append(tmpl)
    _save_templates(templates)
    return tmpl


@app.put("/api/templates/{template_id}")
async def update_template(template_id: str, req: TemplateRequest):
    templates = _load_templates()
    for t in templates:
        if t.get("id") == template_id:
            ttype = req.type if req.type in PASSAGE_TYPES else t.get("type", "normal")
            t.update({
                "title": req.title.strip(),
                "type": ttype,
                "keywords": [k.strip().lower() for k in (req.keywords or []) if k.strip()],
                "body": req.body or "",
            })
            _save_templates(templates)
            return t
    raise HTTPException(404, f"Template {template_id!r} not found.")


@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    templates = _load_templates()
    kept = [t for t in templates if t.get("id") != template_id]
    if len(kept) == len(templates):
        raise HTTPException(404, f"Template {template_id!r} not found.")
    _save_templates(kept)
    return {"status": "deleted", "id": template_id}


# ── Story graph ────────────────────────────────────────────────────────────────

@app.get("/api/graph")
async def get_graph():
    graph = load_story(_p())
    return graph.model_dump()


@app.delete("/api/passage/{passage_id}")
async def delete_passage_endpoint(passage_id: str):
    """Delete a passage and clean up all references. Children become orphans
    (surfaced by validation), not cascade-deleted."""
    p = _p()
    ok, msg = delete_passage(p, passage_id)
    if not ok:
        raise HTTPException(404, msg)
    # Drop the session pointer if it referenced the deleted passage.
    session = load_session(p)
    if session.current_passage == passage_id:
        session.current_passage = None
        save_session(p, session)
    return {"status": "deleted", "passage_id": passage_id, "message": msg}


@app.get("/api/passage/{passage_id}")
async def get_passage(passage_id: str):
    p = _p()
    graph = load_story(p)
    if passage_id not in graph.passages:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")
    entry = graph.passages[passage_id]
    tw_path = p.root / entry.file
    prose = tw_path.read_text(encoding="utf-8") if tw_path.exists() else ""
    return {**entry.model_dump(), "raw": prose}


@app.get("/api/passage/{passage_id}/snapshot")
async def get_reconstructed_snapshot(passage_id: str) -> dict:
    """Return the reconstructed snapshot for a passage (deltas applied from root)."""
    p = _p()
    graph = load_story(p)
    if passage_id not in graph.passages:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")
    snapshot = reconstruct_passage_snapshot(graph, passage_id)
    return snapshot.model_dump()


@app.get("/api/passage/{passage_id}/delta")
async def get_passage_delta(passage_id: str) -> dict:
    """Return the stored snapshot_delta for a passage (or null if none)."""
    p = _p()
    graph = load_story(p)
    if passage_id not in graph.passages:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")
    entry = graph.passages[passage_id]
    return {
        "passage_id": passage_id,
        "snapshot_delta": entry.snapshot_delta.model_dump() if entry.snapshot_delta else None,
    }


# ── Session / mode ─────────────────────────────────────────────────────────────

@app.get("/api/session")
async def get_session():
    return load_session(_p()).model_dump()


class SessionUpdate(BaseModel):
    current_passage: Optional[str] = None
    current_branch: Optional[str] = None
    active_mode: Optional[str] = None


@app.post("/api/session")
async def update_session(body: SessionUpdate):
    p = _p()
    session = load_session(p)
    if body.current_passage is not None:
        session.current_passage = body.current_passage
    if body.current_branch is not None:
        session.current_branch = body.current_branch
    if body.active_mode is not None:
        session.active_mode = body.active_mode
    save_session(p, session)
    return session.model_dump()


# ── Validation ─────────────────────────────────────────────────────────────────

@app.get("/api/validate")
async def validate():
    result = run_validation(_p())
    return result.model_dump()


# ── Tweego locate ──────────────────────────────────────────────────────────────

@app.get("/api/tweego/find")
async def tweego_find():
    """Try to locate tweego on disk. Returns found path or None."""
    p = _p()
    cfg = load_config(p)
    found = find_tweego(cfg.tweego_path)
    return {"found": found, "configured": cfg.tweego_path}


# ── Compile ────────────────────────────────────────────────────────────────────

@app.post("/api/compile")
async def compile_endpoint():
    p = _p()
    cfg = load_config(p)
    ok, msg = compile_story(p, cfg)
    return {"success": ok, "message": msg}


# ── Config ─────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    p = _p()
    cfg = load_config(p)
    profile, _ = _current_experience_profile(p)
    return cfg.model_copy(update={"experience_mode": profile.mode.value}).model_dump()


@app.post("/api/config")
async def update_config(body: dict):
    p = _p()
    cfg = load_config(p)
    profile, _ = _current_experience_profile(p)
    if (
        "experience_mode" in body
        and body["experience_mode"] != profile.mode.value
    ):
        raise HTTPException(409, detail={
            "code": "experience_profile_preview_required",
            "message": "change experience mode through a previewed profile revision",
        })
    updated = HarnessConfig.model_validate({**cfg.model_dump(), **body})
    save_config(p, updated)
    return updated.model_dump()


class CapabilityCardStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: CapabilityCard
    fingerprint: str
    evidence_valid: bool
    source_valid: bool
    expired: bool


class CapabilityCardsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[CapabilityCardStatusResponse]


@app.get("/api/capability-cards", response_model=CapabilityCardsResponse)
async def get_capability_cards():
    repository_root = Path(__file__).resolve().parents[2]
    directory = repository_root / "benchmark_outputs" / "capability_cards"
    now = datetime.now(timezone.utc)
    return {
        "cards": [
            {
                "card": card,
                "fingerprint": card.fingerprint(),
                "evidence_valid": evidence_hashes_match(card, repository_root),
                "source_valid": source_hashes_match(card, repository_root),
                "expired": now > card.valid_until,
            }
            for card in load_capability_cards(directory)
        ]
    }


class ExperienceProfilePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    profile: ExperienceProfile


class ExperienceProfileRevisionRequest(ExperienceProfilePreviewRequest):
    preview_fingerprint: str


def _experience_profile_store(p: ProjectPaths) -> ExperienceProfileStore:
    return ExperienceProfileStore(p.experience_profiles_dir)


def _current_experience_profile(p: ProjectPaths) -> tuple[ExperienceProfile, str]:
    store = _experience_profile_store(p)
    try:
        return store.get(), "stored"
    except FileNotFoundError:
        return preset_for_mode(load_config(p).experience_mode), "compatibility_default"


def _raise_experience_http(exc: ExperienceProfileConflict) -> None:
    raise HTTPException(409, detail={"code": exc.code, "message": str(exc)})


@app.get("/api/experience-profile")
async def get_experience_profile():
    profile, source = _current_experience_profile(_p())
    return {
        "profile": profile.model_dump(mode="json"),
        "fingerprint": profile.fingerprint(),
        "source": source,
        "presets": {
            mode: preset_for_mode(mode, revision=profile.revision + 1).model_dump(mode="json")
            for mode in ("story_driven", "hybrid", "sandbox")
        },
    }


@app.post("/api/experience-profile/preview")
async def preview_experience_profile(req: ExperienceProfilePreviewRequest):
    p = _p()
    current, _ = _current_experience_profile(p)
    if req.expected_revision != current.revision:
        _raise_experience_http(ExperienceProfileConflict(
            "experience_profile_revision_conflict",
            f"expected revision {req.expected_revision}, found {current.revision}",
        ))
    try:
        preview = preview_experience_migration(current, req.profile, load_story(p))
    except ExperienceProfileConflict as exc:
        _raise_experience_http(exc)
    return preview.model_dump(mode="json")


@app.post("/api/experience-profile/revisions")
async def create_experience_profile_revision(req: ExperienceProfileRevisionRequest):
    p = _p()
    store = _experience_profile_store(p)
    current, source = _current_experience_profile(p)
    if req.expected_revision != current.revision:
        _raise_experience_http(ExperienceProfileConflict(
            "experience_profile_revision_conflict",
            f"expected revision {req.expected_revision}, found {current.revision}",
        ))
    try:
        preview = preview_experience_migration(current, req.profile, load_story(p))
        if preview.preview_fingerprint != req.preview_fingerprint:
            raise ExperienceProfileConflict(
                "experience_profile_preview_stale",
                "profile or story graph changed after the migration preview",
            )
        if source == "compatibility_default":
            store.ensure_baseline(current)
        saved = store.put(req.profile, expected_revision=current.revision)
    except ExperienceProfileConflict as exc:
        _raise_experience_http(exc)

    # This field remains a compatibility projection for legacy clients; the
    # immutable profile revision is authoritative if this secondary write fails.
    cfg = load_config(p)
    save_config(p, cfg.model_copy(update={"experience_mode": saved.mode.value}))
    return {
        "profile": saved.model_dump(mode="json"),
        "fingerprint": saved.fingerprint(),
        "source": "stored",
        "preview": preview.model_dump(mode="json"),
    }


class TopologyLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    location: LocationNode


class TopologyRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    route: Route


class TopologyDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class SimulationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_id: str | None = None
    start_location: str | None = None
    seed: int | None = None
    world_state: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, float | int] = Field(default_factory=dict)
    factions: tuple[FactionState, ...] = ()
    character_stat_definitions: tuple[CharacterStatDefinition, ...] = ()
    characters: tuple[CharacterRuntimeState, ...] = ()


class SimulationActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    kind: str
    action_id: str


def _topology_store(p: ProjectPaths) -> TopologyStore:
    return TopologyStore(p.topology_dir)


def _simulation_store(p: ProjectPaths) -> RuntimeSessionStore:
    return RuntimeSessionStore(p.simulations_dir)


def _require_systemic_profile(p: ProjectPaths) -> ExperienceProfile:
    profile, _ = _current_experience_profile(p)
    if profile.mode.value == "story_driven":
        raise HTTPException(409, detail={
            "code": "systemic_profile_required",
            "message": "topology and simulation require a Hybrid or Sandbox profile",
        })
    return profile


def _raise_simulation_http(exc: SimulationStoreError | SimulationError) -> None:
    status = 404 if exc.code in {
        "topology_not_found", "topology_revision_not_found", "simulation_not_found", "revision_not_found",
    } else 409
    raise HTTPException(status, detail={"code": exc.code, "message": str(exc)})


def _topology_payload(topology: WorldTopology) -> dict[str, Any]:
    start = topology.locations[0].id
    reached = reachable_locations(topology, start)
    return {
        "topology": topology.model_dump(mode="json"),
        "fingerprint": topology.fingerprint(),
        "diagnostics": [{
            "code": "location_unreachable",
            "level": "warning",
            "message": f"{location.name} is unreachable from {start}.",
            "location_id": location.id,
        } for location in topology.locations if location.id not in reached],
    }


@app.get("/api/topology")
async def get_topology():
    try:
        return _topology_payload(_topology_store(_p()).get())
    except SimulationStoreError as exc:
        if exc.code == "topology_not_found":
            return {"topology": None, "fingerprint": "", "diagnostics": []}
        _raise_simulation_http(exc)


@app.get("/api/systems")
async def get_systems():
    p = _p()
    catalog = _load_system_catalog(p)
    return {"catalog": catalog.model_dump(mode="json"), "fingerprint": catalog.fingerprint()}


@app.get("/api/encounters")
async def get_encounters():
    p = _p()
    catalog = _load_encounter_catalog(p)
    return {"catalog": catalog.model_dump(mode="json"), "fingerprint": catalog.fingerprint()}


def _load_system_catalog(p: ProjectPaths) -> SystemCatalog:
    return SystemCatalog.model_validate_json(p.systems_json.read_text(encoding="utf-8")) \
        if p.systems_json.exists() else SystemCatalog()


def _load_encounter_catalog(p: ProjectPaths) -> EncounterCatalog:
    return EncounterCatalog.model_validate_json(p.encounters_json.read_text(encoding="utf-8")) \
        if p.encounters_json.exists() else EncounterCatalog()


def _load_simulation_fixture_catalog(p: ProjectPaths) -> SimulationFixtureCatalog:
    return SimulationFixtureCatalog.model_validate_json(
        p.simulation_fixtures_json.read_text(encoding="utf-8")
    ) if p.simulation_fixtures_json.exists() else SimulationFixtureCatalog()


_SYSTEM_CATALOG_WRITE_LOCK = threading.RLock()


class SystemCatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_fingerprint: str
    rules: tuple[SystemRule, ...]


class EncounterCatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_fingerprint: str
    templates: tuple[EncounterTemplate, ...]


class SimulationFixtureCatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_fingerprint: str
    fixtures: tuple[SimulationFixture, ...]


def _save_catalog(path: Path, catalog: BaseModel) -> None:
    _atomic_write_text(path, catalog.model_dump_json(indent=2))


@app.put("/api/systems")
async def update_systems(req: SystemCatalogRequest):
    p = _p()
    _require_systemic_profile(p)
    with _SYSTEM_CATALOG_WRITE_LOCK:
        current = _load_system_catalog(p)
        if req.expected_fingerprint != current.fingerprint():
            raise HTTPException(409, detail={
                "code": "system_catalog_conflict",
                "message": "system catalog changed since it was loaded",
            })
        candidate = SystemCatalog(revision=current.revision + 1, rules=req.rules)
        _save_catalog(p.systems_json, candidate)
    return {"catalog": candidate.model_dump(mode="json"), "fingerprint": candidate.fingerprint()}


@app.put("/api/encounters")
async def update_encounters(req: EncounterCatalogRequest):
    p = _p()
    _require_systemic_profile(p)
    with _SYSTEM_CATALOG_WRITE_LOCK:
        current = _load_encounter_catalog(p)
        if req.expected_fingerprint != current.fingerprint():
            raise HTTPException(409, detail={
                "code": "encounter_catalog_conflict",
                "message": "encounter catalog changed since it was loaded",
            })
        candidate = EncounterCatalog(revision=current.revision + 1, templates=req.templates)
        _save_catalog(p.encounters_json, candidate)
    return {"catalog": candidate.model_dump(mode="json"), "fingerprint": candidate.fingerprint()}


@app.get("/api/simulation-fixtures")
async def get_simulation_fixtures():
    catalog = _load_simulation_fixture_catalog(_p())
    return {"catalog": catalog.model_dump(mode="json"), "fingerprint": catalog.fingerprint()}


@app.put("/api/simulation-fixtures")
async def update_simulation_fixtures(req: SimulationFixtureCatalogRequest):
    p = _p()
    _require_systemic_profile(p)
    with _SYSTEM_CATALOG_WRITE_LOCK:
        current = _load_simulation_fixture_catalog(p)
        if req.expected_fingerprint != current.fingerprint():
            raise HTTPException(409, detail={
                "code": "simulation_fixture_catalog_conflict",
                "message": "simulation fixture catalog changed since it was loaded",
            })
        try:
            topology = _topology_store(p).get()
        except SimulationStoreError as exc:
            _raise_simulation_http(exc)
        known_locations = {location.id for location in topology.locations}
        unknown_locations = sorted({
            location
            for fixture in req.fixtures
            for location in (
                fixture.start_location,
                *(character.current_location for character in fixture.characters),
            )
            if location not in known_locations
        })
        if unknown_locations:
            raise HTTPException(422, detail={
                "code": "simulation_fixture_location_unknown",
                "message": f"fixture references unknown locations: {unknown_locations}",
            })
        candidate = SimulationFixtureCatalog(
            revision=current.revision + 1,
            fixtures=req.fixtures,
        )
        _save_catalog(p.simulation_fixtures_json, candidate)
    return {"catalog": candidate.model_dump(mode="json"), "fingerprint": candidate.fingerprint()}


@app.post("/api/topology/locations")
async def add_topology_location(req: TopologyLocationRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        if req.expected_revision == 0:
            topology = WorldTopology(revision=1, locations=(req.location,))
        else:
            current = store.get()
            topology = current.model_copy(update={
                "revision": current.revision + 1,
                "locations": (*current.locations, req.location),
            })
            topology = WorldTopology.model_validate(topology.model_dump())
        saved = store.put(topology, expected_revision=req.expected_revision)
    except SimulationStoreError as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


@app.post("/api/topology/routes")
async def add_topology_route(req: TopologyRouteRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        current = store.get()
        topology = WorldTopology.model_validate(current.model_copy(update={
            "revision": current.revision + 1,
            "routes": (*current.routes, req.route),
        }).model_dump())
        saved = store.put(topology, expected_revision=req.expected_revision)
    except SimulationStoreError as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


@app.put("/api/topology/locations/{location_id}")
async def update_topology_location(location_id: str, req: TopologyLocationRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        current = store.get()
        if req.location.id != location_id:
            raise SimulationError("topology_identity_conflict", "location path and payload id differ")
        if location_id not in {item.id for item in current.locations}:
            raise SimulationError("location_unknown", "location is not in the topology")
        candidate = WorldTopology.model_validate(current.model_copy(update={
            "revision": current.revision + 1,
            "locations": tuple(req.location if item.id == location_id else item for item in current.locations),
        }).model_dump())
        saved = store.put(candidate, expected_revision=req.expected_revision)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


@app.delete("/api/topology/locations/{location_id}")
async def delete_topology_location(location_id: str, req: TopologyDeleteRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        current = store.get()
        if location_id not in {item.id for item in current.locations}:
            raise SimulationError("location_unknown", "location is not in the topology")
        if any(route.source == location_id or route.destination == location_id for route in current.routes):
            raise SimulationError("location_in_use", "remove routes that reference this location first")
        remaining = tuple(item for item in current.locations if item.id != location_id)
        if not remaining:
            raise SimulationError("topology_empty", "topology must retain at least one location")
        candidate = WorldTopology.model_validate(current.model_copy(update={
            "revision": current.revision + 1,
            "locations": remaining,
        }).model_dump())
        saved = store.put(candidate, expected_revision=req.expected_revision)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


@app.put("/api/topology/routes/{route_id}")
async def update_topology_route(route_id: str, req: TopologyRouteRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        current = store.get()
        if req.route.id != route_id:
            raise SimulationError("topology_identity_conflict", "route path and payload id differ")
        if route_id not in {item.id for item in current.routes}:
            raise SimulationError("route_unknown", "route is not in the topology")
        candidate = WorldTopology.model_validate(current.model_copy(update={
            "revision": current.revision + 1,
            "routes": tuple(req.route if item.id == route_id else item for item in current.routes),
        }).model_dump())
        saved = store.put(candidate, expected_revision=req.expected_revision)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


@app.delete("/api/topology/routes/{route_id}")
async def delete_topology_route(route_id: str, req: TopologyDeleteRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _topology_store(p)
    try:
        current = store.get()
        if route_id not in {item.id for item in current.routes}:
            raise SimulationError("route_unknown", "route is not in the topology")
        candidate = WorldTopology.model_validate(current.model_copy(update={
            "revision": current.revision + 1,
            "routes": tuple(item for item in current.routes if item.id != route_id),
        }).model_dump())
        saved = store.put(candidate, expected_revision=req.expected_revision)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)
    return _topology_payload(saved)


def _simulation_payload(p: ProjectPaths, record: SimulationRecord) -> dict[str, Any]:
    topology = _topology_store(p).by_fingerprint(record.session.topology_fingerprint)
    anchors = _hybrid_authored_anchors(p, topology, record.session)
    return {
        "session": record.session.model_dump(mode="json"),
        "trace": record.trace.model_dump(mode="json") if record.trace else None,
        "fingerprint": record.fingerprint(),
        "opportunities": [
            item.model_dump(mode="json")
            for item in available_opportunities(topology, record.session, anchors)
        ],
    }


def _hybrid_authored_anchors(
    p: ProjectPaths,
    topology: WorldTopology,
    session,
) -> tuple[AuthoredAnchor, ...]:
    """Project explicitly tagged planned scenes into ordered Hybrid runtime anchors."""
    profile, _ = _current_experience_profile(p)
    if (
        profile.mode.value != "hybrid"
        or profile.fingerprint() != session.experience_profile_fingerprint
    ):
        return ()
    location_ids = {item.id for item in topology.locations}
    anchors: list[AuthoredAnchor] = []
    for arc in plan_overview(p)["arcs"]:
        previous_id = ""
        for scene in arc["scenes"]:
            keywords = {str(item).strip().lower() for item in scene.get("keywords", [])}
            if "anchor" not in keywords:
                continue
            location = next(
                (
                    keyword.split(":", 1)[1]
                    for keyword in keywords
                    if keyword.startswith("location:") and ":" in keyword
                ),
                "",
            )
            if location not in location_ids:
                continue
            raw_id = re.sub(
                r"[^a-z0-9_]+", "_", f"anchor_{arc['arc']}_{scene['id']}".lower()
            ).strip("_")
            if len(raw_id) > 64:
                suffix = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:10]
                raw_id = f"{raw_id[:53]}_{suffix}"
            label = str(scene.get("title") or scene.get("summary") or scene["id"])
            anchor = AuthoredAnchor(
                id=raw_id,
                label=label,
                location_id=location,
                prerequisite_ids=(previous_id,) if previous_id else (),
            )
            anchors.append(anchor)
            previous_id = anchor.id
    return tuple(anchors)


@app.post("/api/simulations")
async def create_simulation(req: SimulationCreateRequest):
    p = _p()
    profile = _require_systemic_profile(p)
    try:
        topology = _topology_store(p).get()
        start_location = req.start_location
        seed = req.seed
        world_state = req.world_state
        resources = req.resources
        factions = req.factions
        definitions = req.character_stat_definitions
        characters = req.characters
        if req.fixture_id is not None:
            override_fields = req.model_fields_set & {
                "start_location", "seed", "world_state", "resources", "factions",
                "character_stat_definitions", "characters",
            }
            if override_fields:
                raise HTTPException(422, detail={
                    "code": "simulation_fixture_override_forbidden",
                    "message": "a named fixture cannot be combined with ad-hoc initial state",
                })
            fixture = next(
                (item for item in _load_simulation_fixture_catalog(p).fixtures if item.id == req.fixture_id),
                None,
            )
            if fixture is None:
                raise HTTPException(404, detail={
                    "code": "simulation_fixture_not_found",
                    "message": "simulation fixture was not found",
                })
            start_location = fixture.start_location
            seed = fixture.seed
            world_state = fixture.world_state
            resources = fixture.resources
            factions = fixture.factions
            definitions = fixture.character_stat_definitions
            characters = fixture.characters
        if start_location is None or seed is None:
            raise HTTPException(422, detail={
                "code": "simulation_initial_state_required",
                "message": "provide fixture_id or both start_location and seed",
            })
        session = create_runtime_session(
            topology,
            session_id=f"simulation_{uuid.uuid4().hex}",
            experience_profile_fingerprint=profile.fingerprint(),
            start_location=start_location,
            time_model=profile.time_model.value,
            seed=seed,
            world_state=world_state,
            resources=resources,
            factions=factions,
            character_stat_definitions=definitions,
            characters=characters,
        )
        record = _simulation_store(p).put(SimulationRecord(session=session), expected_revision=0)
        return _simulation_payload(p, record)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)


@app.get("/api/simulations/{simulation_id}")
async def get_simulation(simulation_id: str):
    p = _p()
    try:
        return _simulation_payload(p, _simulation_store(p).get(simulation_id))
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)


@app.post("/api/simulations/{simulation_id}/actions")
async def apply_simulation_action(simulation_id: str, req: SimulationActionRequest):
    p = _p()
    _require_systemic_profile(p)
    store = _simulation_store(p)
    try:
        current = store.get(simulation_id)
        topology = _topology_store(p).by_fingerprint(current.session.topology_fingerprint)
        rules = _load_system_catalog(p).rules
        if req.kind == "local_action":
            session, trace = apply_local_action(
                topology,
                current.session,
                req.action_id,
                expected_revision=req.expected_revision,
                system_rules=rules,
            )
        elif req.kind == "travel":
            session, trace = travel(
                topology,
                current.session,
                req.action_id,
                expected_revision=req.expected_revision,
                system_rules=rules,
            )
        elif req.kind == "authored_anchor":
            anchor = next(
                (
                    item for item in _hybrid_authored_anchors(p, topology, current.session)
                    if item.id == req.action_id
                ),
                None,
            )
            if anchor is None:
                raise SimulationError(
                    "authored_anchor_unknown", "authored anchor is unavailable for this Hybrid session"
                )
            session, trace = complete_authored_anchor(
                topology,
                current.session,
                anchor,
                expected_revision=req.expected_revision,
            )
        else:
            raise SimulationError(
                "simulation_action_kind_invalid",
                "kind must be local_action, travel, or authored_anchor",
            )
        record = store.put(
            SimulationRecord(session=session, trace=trace),
            expected_revision=req.expected_revision,
        )
        return _simulation_payload(p, record)
    except (SimulationStoreError, SimulationError) as exc:
        _raise_simulation_http(exc)


# ── Chat / generate ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    arc_name: str
    passage_slug: str
    parent_passage_id: Optional[str] = None
    mode: str = "co-author"
    branch_name: str = "main"
    choice_index: Optional[int] = None
    # ── Per-generation steering (esp. when seeding a new arc) ─────────────────
    extra_ideas: str = ""                       # your own ideas/seed, appended to direction
    inspiration_files: list[str] = Field(default_factory=list)  # pin these corpus files
    inspiration_text: str = ""                  # verbatim reference text to inject


class GenerateResponse(BaseModel):
    raw_output: str
    parsed: dict
    warnings: list[str]
    generation_id: str = ""


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """Call Ollama, parse output, return for human review. Does NOT commit."""
    p = _p()
    cfg = load_config(p)
    graph = load_story(p)

    # Fold the human's own ideas/seed into the direction the model sees.
    human_prompt = req.prompt
    if req.extra_ideas.strip():
        human_prompt = f"{req.prompt}\n\n[MY IDEAS]\n{req.extra_ideas.strip()}"

    # Retrieve inspiration so it can be injected into the prompt body.
    # Query = direction (+ ideas) + the parent snapshot summary (when available)
    # so we surface stylistically relevant material, not just keyword matches.
    rag_query = human_prompt
    if req.parent_passage_id and req.parent_passage_id in graph.passages:
        rag_query = f"{human_prompt}\n{graph.passages[req.parent_passage_id].summary}"

    # Inspiration block = verbatim pasted reference (if any) + retrieved chunks.
    # Pinned files restrict retrieval to those sources; otherwise auto top-k.
    pinned = {s for s in req.inspiration_files if s and s.strip()}
    retrieved = await retrieve_inspiration(p, cfg, rag_query, sources=pinned or None)
    insp_parts: list[str] = []
    if req.inspiration_text.strip():
        insp_parts.append(f"--- inspiration: (your reference) ---\n{req.inspiration_text.strip()}")
    if retrieved:
        insp_parts.append(retrieved)
    inspiration = "\n\n".join(insp_parts)

    # Earlier-passage recall: exclude direct parent so it doesn't duplicate
    # the verbatim PREVIOUS SCENE block.
    exclude_ids = [req.parent_passage_id] if req.parent_passage_id else None
    story_recall = await retrieve_story_recall(p, cfg, rag_query, exclude_ids=exclude_ids)

    full_prompt = build_prompt(
        p=p,
        graph=graph,
        parent_passage_id=req.parent_passage_id,
        human_prompt=human_prompt,
        mode=req.mode,
        arc_name=req.arc_name,
        cfg=cfg,
        inspiration=inspiration,
        story_recall=story_recall,
    )

    try:
        raw, parsed = await generate_story_output(cfg, full_prompt)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")

    gen_id = record_generation(p, {
        "label": "passage",
        "model": cfg.ollama_model,
        "output_format": getattr(cfg, "output_format", "delimited"),
        "mode": req.mode,
        "arc_name": req.arc_name,
        "passage_slug": req.passage_slug,
        "parent_passage_id": req.parent_passage_id or "",
        "prompt": full_prompt,
        "raw_output": raw,
        "parsed": parsed.model_dump(),
        "warnings": parsed.parse_warnings,
    }, kind="draft")

    # Shadow generation is intentionally isolated from the returned draft and
    # commit path. It records a comparable typed attempt for evaluation only.
    if getattr(cfg, "typed_shadow_generation", False):
        shadow_strategy = (
            cfg.generation_strategy
            if cfg.generation_strategy in {"typed_fill", "flat_fill"}
            else "typed_fill"
        )
        context_pack = ContextPack(
            parent_passage_id=req.parent_passage_id or "",
            parent_summary=(
                graph.passages[req.parent_passage_id].summary
                if req.parent_passage_id and req.parent_passage_id in graph.passages
                else ""
            ),
            inspiration=inspiration,
            story_recall=story_recall,
        )
        plan_id = re.sub(r"[^a-z0-9_]+", "_", req.passage_slug.lower()).strip("_")
        if not plan_id or not plan_id[0].isalpha():
            plan_id = f"passage_{plan_id or 'shadow'}"
        try:
            shadow_plan = build_legacy_passage_plan(
                parsed,
                plan_id=plan_id[:64],
                context_fingerprint=context_pack.fingerprint(),
                experience_profile=_effective_experience_profile(p, req.arc_name),
            )
            shadow = await generate_typed_draft(
                cfg,
                shadow_plan,
                context_pack,
                author_task=human_prompt,
                passage_id=req.passage_slug,
                arc_name=req.arc_name,
                strategy=shadow_strategy,
            )
            record_generation(p, {
                "label": "passage-shadow",
                "status": "accepted",
                "strategy": shadow_strategy,
                "model": cfg.ollama_model,
                "arc_name": req.arc_name,
                "passage_slug": req.passage_slug,
                "parent_passage_id": req.parent_passage_id or "",
                "plan": shadow_plan.model_dump(mode="json"),
                "draft": shadow.draft.model_dump(mode="json"),
                "compile_artifact": shadow.compile_artifact.model_dump(mode="json"),
                "provenance": shadow.provenance.model_dump(mode="json"),
                "raw_output": shadow.provenance.raw_model_output,
            }, kind="shadow")
        except Exception as exc:
            record_generation(p, {
                "label": "passage-shadow",
                "status": "rejected",
                "strategy": shadow_strategy,
                "model": cfg.ollama_model,
                "arc_name": req.arc_name,
                "passage_slug": req.passage_slug,
                "parent_passage_id": req.parent_passage_id or "",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }, kind="shadow")

    return GenerateResponse(
        raw_output=raw,
        parsed=parsed.model_dump(),
        warnings=parsed.parse_warnings,
        generation_id=gen_id,
    )


# ── Typed draft API (opt-in; legacy generate/commit remain unchanged) ─────────

class TypedGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PassagePlan | None = None
    plan_id: str = ""
    plan_revision: int | None = Field(default=None, ge=1)
    expected_plan_fingerprint: str = ""
    context: ContextPack
    author_task: str
    passage_id: str
    arc_name: str
    parent_passage_id: str = ""
    parent_choice_index: Optional[int] = None
    branch_name: str = "main"
    strategy: str = "typed_fill"
    seed: Optional[int] = None


class TypedDraftEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_fingerprint: str
    fill: NarrativeFill


class TypedDraftCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_plan_revision: int
    expected_draft_fingerprint: str
    expected_parent_fingerprint: str = ""


class TypedDraftRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_fingerprint: str


class TypedDraftCompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_fingerprint: str


class TypedDraftValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_fingerprint: str


class TypedDraftCompileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    draft_revision: int
    draft_fingerprint: str
    artifact: CompileArtifact
    persisted_artifact_match: bool


class TypedDraftPlaytestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_fingerprint: str
    initial_state: dict[str, Any] = Field(default_factory=dict)
    choice_slot_ids: tuple[str, ...] | None = None


class TypedDraftPlaytestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    tweego_compile: bool
    browser_load: bool
    choice_reachability: bool | None = None
    choice_effect_execution: bool | None = None
    runtime_state_transaction: bool | None = None
    continuity_after_navigation: bool | None = None
    form_binding: bool | None = None
    hostile_text_safe: bool | None = None
    runtime_errors: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


class TypedDraftPlaytestJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    draft_id: str
    draft_revision: int
    draft_fingerprint: str
    created_at: datetime
    updated_at: datetime
    result: TypedDraftPlaytestResult | None = None
    error_code: str = ""
    error_message: str = ""


class TypedCommitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["committed"]
    draft_id: str
    draft_revision: int
    passage_id: str
    pending_facts: list[ContinuityProposal]


def _draft_store(p: ProjectPaths) -> DraftStore:
    return DraftStore(p.harness_dir / "drafts")


def _passage_plan_store(p: ProjectPaths) -> PassagePlanStore:
    return PassagePlanStore(p.passage_plans_dir)


def _raise_plan_store_http(exc: Exception) -> None:
    if isinstance(exc, PlanNotFound):
        raise HTTPException(404, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, PlanConflict):
        raise HTTPException(409, detail={"code": exc.code, "message": str(exc)})
    raise exc


class PassagePlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PassagePlan
    arc_name: str = ""


class PassagePlanRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PassagePlan
    expected_plan_fingerprint: str
    arc_name: str = ""


class PassagePlanApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_plan_fingerprint: str


class PassagePlanRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PassagePlan
    fingerprint: str
    approved: bool


@app.post("/api/plans", response_model=PassagePlanRecordResponse)
async def create_passage_plan(req: PassagePlanCreateRequest):
    try:
        plan = req.plan
        if req.arc_name:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", req.arc_name):
                raise HTTPException(422, "arc_name contains unsafe characters")
            plan = plan.model_copy(update={
                "experience_profile_fingerprint": _effective_experience_profile(_p(), req.arc_name).fingerprint(),
            })
        plan = _passage_plan_store(_p()).put(plan)
        return _passage_plan_store(_p()).payload(plan.plan_id, plan.revision)
    except (PlanNotFound, PlanConflict) as exc:
        _raise_plan_store_http(exc)


@app.get(
    "/api/plans/{plan_id}/revisions/{revision}",
    response_model=PassagePlanRecordResponse,
)
async def get_passage_plan(plan_id: str, revision: int):
    try:
        return _passage_plan_store(_p()).payload(plan_id, revision)
    except (PlanNotFound, PlanConflict) as exc:
        _raise_plan_store_http(exc)


@app.post(
    "/api/plans/{plan_id}/revisions",
    response_model=PassagePlanRecordResponse,
)
async def revise_passage_plan(plan_id: str, req: PassagePlanRevisionRequest):
    if req.plan.plan_id != plan_id:
        raise HTTPException(409, detail={
            "code": "plan_identity_conflict", "message": "plan path and payload id differ",
        })
    try:
        plan = req.plan
        if req.arc_name:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", req.arc_name):
                raise HTTPException(422, "arc_name contains unsafe characters")
            plan = plan.model_copy(update={
                "experience_profile_fingerprint": _effective_experience_profile(_p(), req.arc_name).fingerprint(),
            })
        plan = _passage_plan_store(_p()).put(
            plan, expected_plan_fingerprint=req.expected_plan_fingerprint,
        )
        return _passage_plan_store(_p()).payload(plan.plan_id, plan.revision)
    except (PlanNotFound, PlanConflict) as exc:
        _raise_plan_store_http(exc)


@app.post(
    "/api/plans/{plan_id}/revisions/{revision}/approve",
    response_model=PassagePlanRecordResponse,
)
async def approve_passage_plan(plan_id: str, revision: int, req: PassagePlanApprovalRequest):
    try:
        plan = _passage_plan_store(_p()).approve(
            plan_id, revision, expected_plan_fingerprint=req.expected_plan_fingerprint,
        )
        return _passage_plan_store(_p()).payload(plan.plan_id, plan.revision)
    except (PlanNotFound, PlanConflict) as exc:
        _raise_plan_store_http(exc)


def _raise_draft_store_http(exc: Exception) -> None:
    if isinstance(exc, DraftNotFound):
        raise HTTPException(404, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, DraftConflict):
        raise HTTPException(409, detail={"code": exc.code, "message": str(exc)})
    raise exc


def _effective_experience_profile(p: ProjectPaths, arc_name: str) -> ExperienceProfile:
    profile, _ = _current_experience_profile(p)
    if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", arc_name):
        return profile.effective_for("arc", arc_name)
    return profile.model_copy(update={"overrides": ()})


@app.post("/api/typed/generate", response_model=DraftRecord)
async def generate_typed(req: TypedGenerateRequest):
    """Create and persist one validated typed draft revision."""
    p = _p()
    cfg = load_config(p)
    if req.strategy not in {"typed_fill", "flat_fill"}:
        raise HTTPException(422, "strategy must be typed_fill or flat_fill")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", req.passage_id):
        raise HTTPException(422, "passage_id contains unsafe characters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", req.arc_name):
        raise HTTPException(422, "arc_name contains unsafe characters")
    plan = req.plan
    has_reference = bool(req.plan_id or req.plan_revision or req.expected_plan_fingerprint)
    if plan is not None and has_reference:
        raise HTTPException(422, detail={
            "code": "plan_input_ambiguous",
            "message": "provide either an inline plan or an approved persisted plan reference",
        })
    if plan is None:
        if not (req.plan_id and req.plan_revision and req.expected_plan_fingerprint):
            raise HTTPException(422, detail={
                "code": "plan_reference_required",
                "message": "persisted plans require id, revision, and expected fingerprint",
            })
        try:
            store = _passage_plan_store(p)
            plan = store.get(req.plan_id, req.plan_revision)
            if plan.fingerprint() != req.expected_plan_fingerprint:
                raise PlanConflict("plan_fingerprint_conflict", "plan changed since it was reviewed")
            if not store.is_approved(req.plan_id, req.plan_revision):
                raise PlanConflict("plan_not_approved", "plan must be explicitly approved before generation")
        except (PlanNotFound, PlanConflict) as exc:
            _raise_plan_store_http(exc)
    assert plan is not None
    effective_profile = _effective_experience_profile(p, req.arc_name)
    effective_fingerprint = effective_profile.fingerprint()
    if (
        plan.experience_profile_fingerprint
        and plan.experience_profile_fingerprint != effective_fingerprint
    ):
        raise HTTPException(409, detail={
            "code": "experience_profile_fingerprint_conflict",
            "message": "the plan was created for a different experience profile",
        })
    effective_plan = plan.model_copy(update={
        "experience_profile_fingerprint": effective_fingerprint,
    })
    draft_id = f"draft_{uuid.uuid4().hex}"
    generation_id = f"generation_{uuid.uuid4().hex}"
    try:
        captured_parent_fingerprint = parent_fingerprint(p, req.parent_passage_id)
        outcome = await generate_typed_draft(
            cfg,
            effective_plan,
            req.context,
            author_task=req.author_task,
            passage_id=req.passage_id,
            arc_name=req.arc_name,
            draft_id=draft_id,
            strategy=req.strategy,
            seed=req.seed,
        )
        record = DraftRecord(
            generation_id=generation_id,
            draft=outcome.draft,
            lifecycle_state=DraftLifecycle.VALIDATED,
            provenance=outcome.provenance,
            diagnostics=outcome.compile_artifact.diagnostics,
            compile_artifact=outcome.compile_artifact,
            parent_passage_id=req.parent_passage_id,
            parent_choice_index=req.parent_choice_index,
            branch_name=req.branch_name,
            parent_revision=1 if req.parent_passage_id else None,
            parent_fingerprint=captured_parent_fingerprint,
            passage_id=req.passage_id,
            arc_name=req.arc_name,
        )
        _draft_store(p).put(record)
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    except Exception as exc:
        raise HTTPException(422, detail={
            "code": "typed_generation_rejected",
            "message": str(exc),
        }) from exc
    return record.model_dump(mode="json")


@app.get("/api/drafts/{draft_id}/{revision}", response_model=DraftRecord)
async def get_typed_draft(draft_id: str, revision: int):
    try:
        record = _draft_store(_p()).get(draft_id, revision)
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    return record.model_dump(mode="json")


@app.get("/api/drafts/{draft_id}", response_model=DraftRecord)
async def get_latest_typed_draft(draft_id: str):
    store = _draft_store(_p())
    try:
        record = store.get(draft_id, store.latest_revision(draft_id))
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    return record.model_dump(mode="json")


@app.post("/api/drafts/{draft_id}/{revision}/edit", response_model=DraftRecord)
async def edit_typed_draft(draft_id: str, revision: int, req: TypedDraftEditRequest):
    """Validate a human edit as a new immutable revision of the same plan."""
    store = _draft_store(_p())
    try:
        current = store.get(draft_id, revision)
        if store.latest_revision(draft_id) != revision:
            raise DraftConflict("draft_superseded", "a newer draft revision already exists")
        if current.lifecycle_state in {DraftLifecycle.COMMITTED, DraftLifecycle.REJECTED}:
            raise DraftConflict("draft_closed", "committed or rejected drafts cannot be edited")
        if current.draft.fingerprint() != req.expected_draft_fingerprint:
            raise DraftConflict("draft_fingerprint_conflict", "draft changed since it was loaded")

        next_revision = revision + 1
        fill = req.fill.model_copy(update={"revision": next_revision})
        draft = assemble_passage_draft(
            current.draft.plan,
            fill,
            draft_id=draft_id,
            revision=next_revision,
        )
        artifact = compile_passage_draft(
            draft,
            passage_id=current.passage_id,
            arc_name=current.arc_name,
        )
        edited = DraftRecord(
            generation_id=f"edit_{uuid.uuid4().hex}",
            draft=draft,
            lifecycle_state=DraftLifecycle.EDITED,
            provenance=GenerationProvenance(
                model_name=current.provenance.model_name,
                effective_configuration={"human_edit": True},
            ),
            diagnostics=artifact.diagnostics,
            compile_artifact=artifact,
            parent_passage_id=current.parent_passage_id,
            parent_choice_index=current.parent_choice_index,
            branch_name=current.branch_name,
            parent_revision=current.parent_revision,
            parent_fingerprint=current.parent_fingerprint,
            passage_id=current.passage_id,
            arc_name=current.arc_name,
        )
        store.put(edited)
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    except Exception as exc:
        raise HTTPException(422, detail={
            "code": "draft_edit_rejected",
            "message": str(exc),
        }) from exc
    return edited.model_dump(mode="json")


@app.post("/api/drafts/{draft_id}/{revision}/validate", response_model=DraftRecord)
async def validate_typed_draft(
    draft_id: str,
    revision: int,
    req: TypedDraftValidateRequest,
):
    """Promote a compiled human edit to the explicit validated state."""
    store = _draft_store(_p())
    try:
        record = store.get(draft_id, revision)
        if store.latest_revision(draft_id) != revision:
            raise DraftConflict("draft_superseded", "a newer draft revision already exists")
        if record.draft.fingerprint() != req.expected_draft_fingerprint:
            raise DraftConflict("draft_fingerprint_conflict", "draft changed since it was loaded")
        if record.compile_artifact is None:
            raise DraftConflict("compile_artifact_missing", "draft has no compile artifact")
        if record.lifecycle_state == DraftLifecycle.VALIDATED:
            return record.model_dump(mode="json")
        validated = store.transition(
            draft_id,
            revision,
            expected=DraftLifecycle.EDITED,
            target=DraftLifecycle.VALIDATED,
        )
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    return validated.model_dump(mode="json")


def _exact_draft_record(
    draft_id: str,
    revision: int,
    expected_draft_fingerprint: str,
) -> DraftRecord:
    try:
        record = _draft_store(_p()).get(draft_id, revision)
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    if record.draft.fingerprint() != expected_draft_fingerprint:
        _raise_draft_store_http(DraftConflict(
            "draft_fingerprint_conflict", "draft changed since it was loaded"
        ))
    return record


@app.post(
    "/api/drafts/{draft_id}/{revision}/compile",
    response_model=TypedDraftCompileResponse,
)
async def compile_typed_draft(
    draft_id: str,
    revision: int,
    req: TypedDraftCompileRequest,
):
    """Compile one exact immutable draft without mutating its persisted revision."""
    record = _exact_draft_record(draft_id, revision, req.expected_draft_fingerprint)
    artifact = compile_passage_draft(
        record.draft,
        passage_id=record.passage_id,
        arc_name=record.arc_name,
    )
    return TypedDraftCompileResponse(
        draft_id=draft_id,
        draft_revision=revision,
        draft_fingerprint=record.draft.fingerprint(),
        artifact=artifact,
        persisted_artifact_match=(
            record.compile_artifact is not None
            and record.compile_artifact.fingerprint() == artifact.fingerprint()
        ),
    )


def _playtest_job_path(p: ProjectPaths, job_id: str) -> Path:
    if not re.fullmatch(r"playtest_[0-9a-f]{32}", job_id):
        raise HTTPException(404, detail={
            "code": "playtest_job_not_found", "message": "playtest job was not found",
        })
    return p.harness_dir / "playtests" / f"{job_id}.json"


def _write_playtest_job(p: ProjectPaths, job: TypedDraftPlaytestJobResponse) -> None:
    _atomic_write_text(_playtest_job_path(p, job.job_id), job.model_dump_json(indent=2))


_PLAYTEST_JOB_STALE_AFTER = timedelta(minutes=5)


def _read_playtest_job(p: ProjectPaths, job_id: str) -> TypedDraftPlaytestJobResponse:
    path = _playtest_job_path(p, job_id)
    if not path.exists():
        raise HTTPException(404, detail={
            "code": "playtest_job_not_found", "message": "playtest job was not found",
        })
    try:
        job = TypedDraftPlaytestJobResponse.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise HTTPException(500, detail={
            "code": "playtest_job_corrupt", "message": "playtest job record is corrupt",
        }) from exc
    updated_at = job.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if (
        job.status in {"queued", "running"}
        and datetime.now(timezone.utc) - updated_at > _PLAYTEST_JOB_STALE_AFTER
    ):
        job = job.model_copy(update={
            "status": "failed",
            "updated_at": datetime.now(timezone.utc),
            "error_code": "playtest_job_stale",
            "error_message": "playtest worker stopped updating this persisted job",
        })
        _write_playtest_job(p, job)
    return job


def _draft_browser_scenario(
    record: DraftRecord,
    initial_state: dict[str, Any],
    choice_slot_ids: tuple[str, ...] | None = None,
) -> BrowserScenario:
    unknown_state = set(initial_state) - set(record.draft.plan.allowed_state_refs)
    invalid_state = {
        key for key in initial_state if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)
    }
    if unknown_state or invalid_state:
        raise ValueError("playtest state fixture contains an unauthorized state reference")
    plan_choice_ids = {slot.id for slot in record.draft.plan.choice_slots}
    if choice_slot_ids is not None:
        if not choice_slot_ids:
            raise ValueError("playtest choice selection must contain at least one slot")
        if len(set(choice_slot_ids)) != len(choice_slot_ids):
            raise ValueError("playtest choice selection contains duplicate slots")
        if set(choice_slot_ids) - plan_choice_ids:
            raise ValueError("playtest choice selection contains an unknown slot")
    selected_choice_ids = set(choice_slot_ids) if choice_slot_ids is not None else None
    filled = {item.slot_id: item for item in record.draft.fill.choices}
    choices = []
    for slot in record.draft.plan.choice_slots:
        if selected_choice_ids is not None and slot.id not in selected_choice_ids:
            continue
        if not all(_playtest_condition_matches(item, initial_state) for item in slot.conditions):
            continue
        destination = slot.destination
        if not destination and record.draft.plan.passage_mode.value in {"dialogue_loop", "loop"}:
            destination = record.passage_id
        if destination and slot.id in filled:
            choices.append(BrowserChoiceExpectation(
                label=filled[slot.id].text,
                target=destination,
            ))
    return BrowserScenario(
        passage_id=record.passage_id,
        initial_state=tuple(sorted(initial_state.items())),
        choices=tuple(choices),
        verify_state=False,
    )


def _playtest_condition_matches(condition: Any, state: dict[str, Any]) -> bool:
    """Evaluate a trusted condition only to select links reachable in a fixture."""
    actual = state.get(condition.target)
    operation = condition.operation
    if operation == "truthy":
        return _javascript_truthy(actual)
    if operation == "falsy":
        return not _javascript_truthy(actual)
    if operation in {"eq", "ne"}:
        equal = _javascript_strict_equal(actual, condition.value)
        return equal if operation == "eq" else not equal
    try:
        return {
            "gt": actual > condition.value,
            "gte": actual >= condition.value,
            "lt": actual < condition.value,
            "lte": actual <= condition.value,
        }[operation]
    except (TypeError, ValueError):
        return False


def _javascript_truthy(value: Any) -> bool:
    if value is None or value is False or value == 0 or value == "":
        return False
    return True


def _javascript_strict_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def _execute_draft_playtest(
    project_root: Path,
    record: DraftRecord,
    scenario: BrowserScenario,
) -> TypedDraftPlaytestResult:
    cfg = load_config(ProjectPaths(project_root))
    tweego = find_tweego(cfg.tweego_path)
    formats_value = os.environ.get("TWEEGO_FORMATS") or os.environ.get("TWEEGO_PATH") or ""
    formats = Path(formats_value)
    if not tweego or not formats.is_dir():
        raise PlaytestRuntimeUnavailable(
            "playtest runtime unavailable: configure tweego and TWEEGO_FORMATS"
        )
    browser_value = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    evaluation = evaluate_compile_artifact(
        record.compile_artifact or compile_passage_draft(
            record.draft, passage_id=record.passage_id, arc_name=record.arc_name
        ),
        scenario,
        tweego_path=Path(tweego),
        story_format_path=formats,
        browser_path=Path(browser_value) if browser_value else None,
    )
    required = [
        value for value in (
            evaluation.tweego_compile,
            evaluation.browser_load,
            evaluation.choice_reachability,
            evaluation.choice_effect_execution,
            evaluation.runtime_state_transaction,
            evaluation.continuity_after_navigation,
            evaluation.form_binding,
            evaluation.hostile_text_safe,
        ) if value is not None
    ]
    return TypedDraftPlaytestResult(
        passed=all(required),
        tweego_compile=evaluation.tweego_compile,
        browser_load=evaluation.browser_load,
        choice_reachability=evaluation.choice_reachability,
        choice_effect_execution=evaluation.choice_effect_execution,
        runtime_state_transaction=evaluation.runtime_state_transaction,
        continuity_after_navigation=evaluation.continuity_after_navigation,
        form_binding=evaluation.form_binding,
        hostile_text_safe=evaluation.hostile_text_safe,
        runtime_errors=list(evaluation.runtime_errors),
        details=list(evaluation.details),
    )


class PlaytestRuntimeUnavailable(RuntimeError):
    """Raised when an isolated playtest cannot start its required toolchain."""


def _run_draft_playtest_job(
    project_root: Path,
    queued: TypedDraftPlaytestJobResponse,
    record: DraftRecord,
    scenario: BrowserScenario,
) -> None:
    p = ProjectPaths(project_root)
    running = queued.model_copy(update={"status": "running", "updated_at": datetime.now(timezone.utc)})
    _write_playtest_job(p, running)
    try:
        result = _execute_draft_playtest(project_root, record, scenario)
        finished = running.model_copy(update={
            "status": "completed",
            "updated_at": datetime.now(timezone.utc),
            "result": result,
        })
    except PlaytestRuntimeUnavailable as exc:
        finished = running.model_copy(update={
            "status": "failed",
            "updated_at": datetime.now(timezone.utc),
            "error_code": "playtest_runtime_unavailable",
            "error_message": str(exc),
        })
    except Exception as exc:
        finished = running.model_copy(update={
            "status": "failed",
            "updated_at": datetime.now(timezone.utc),
            "error_code": "playtest_execution_failed",
            "error_message": str(exc),
        })
    _write_playtest_job(p, finished)


@app.post(
    "/api/drafts/{draft_id}/{revision}/playtest",
    response_model=TypedDraftPlaytestJobResponse,
    status_code=202,
)
async def playtest_typed_draft(
    draft_id: str,
    revision: int,
    req: TypedDraftPlaytestRequest,
    background_tasks: BackgroundTasks,
):
    """Queue isolated browser evaluation for one exact immutable draft revision."""
    record = _exact_draft_record(draft_id, revision, req.expected_draft_fingerprint)
    if record.compile_artifact is None:
        raise HTTPException(409, detail={
            "code": "compile_artifact_missing", "message": "draft has no compile artifact",
        })
    fresh_artifact = compile_passage_draft(
        record.draft,
        passage_id=record.passage_id,
        arc_name=record.arc_name,
    )
    if record.compile_artifact.fingerprint() != fresh_artifact.fingerprint():
        raise HTTPException(409, detail={
            "code": "compile_artifact_conflict",
            "message": "persisted compile artifact does not reproduce from the exact draft",
        })
    record = record.model_copy(update={"compile_artifact": fresh_artifact})
    try:
        scenario = _draft_browser_scenario(record, req.initial_state, req.choice_slot_ids)
    except ValueError as exc:
        raise HTTPException(422, detail={
            "code": "playtest_fixture_invalid", "message": str(exc),
        }) from exc
    now = datetime.now(timezone.utc)
    queued = TypedDraftPlaytestJobResponse(
        job_id=f"playtest_{uuid.uuid4().hex}",
        status="queued",
        draft_id=draft_id,
        draft_revision=revision,
        draft_fingerprint=record.draft.fingerprint(),
        created_at=now,
        updated_at=now,
    )
    _write_playtest_job(_p(), queued)
    background_tasks.add_task(
        _run_draft_playtest_job, _p().root, queued, record, scenario
    )
    return queued


@app.get(
    "/api/playtests/{job_id}",
    response_model=TypedDraftPlaytestJobResponse,
)
async def get_typed_draft_playtest(job_id: str):
    return _read_playtest_job(_p(), job_id)


@app.post(
    "/api/drafts/{draft_id}/{revision}/commit",
    response_model=TypedCommitResponse,
)
async def commit_typed(draft_id: str, revision: int, req: TypedDraftCommitRequest):
    """Commit the exact persisted compile artifact; no raw output is accepted."""
    p = _p()
    store = _draft_store(p)
    try:
        committed = commit_typed_draft(
            p,
            store,
            draft_id=draft_id,
            revision=revision,
            expected_plan_revision=req.expected_plan_revision,
            expected_draft_fingerprint=req.expected_draft_fingerprint,
            expected_parent_fingerprint=req.expected_parent_fingerprint,
        )
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    record_generation(p, {
        "label": "typed-commit",
        "draft_id": draft_id,
        "draft_revision": revision,
        "passage_id": committed.passage_id,
        "arc_name": committed.arc_name,
        "parent_passage_id": committed.parent_passage_id,
        "draft_fingerprint": committed.draft.fingerprint(),
        "compile_artifact_fingerprint": committed.compile_artifact.fingerprint(),
    }, kind="commit")
    return {
        "status": "committed",
        "draft_id": draft_id,
        "draft_revision": revision,
        "passage_id": committed.passage_id,
        "pending_facts": [
            proposal.model_dump(mode="json")
            for proposal in committed.draft.fill.continuity_proposals
        ],
    }


class TypedFactDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "reject"]


class TypedFactDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected"]
    key: str


_TYPED_FACT_WRITE_LOCK = threading.RLock()


@app.post(
    "/api/drafts/{draft_id}/{revision}/facts/{fact_key}/decision",
    response_model=TypedFactDecisionResponse,
)
async def decide_typed_fact(
    draft_id: str,
    revision: int,
    fact_key: str,
    req: TypedFactDecisionRequest,
):
    """Accept or reject an exact proposal from one committed draft revision."""
    p = _p()
    try:
        record = _draft_store(p).get(draft_id, revision)
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    if record.lifecycle_state != DraftLifecycle.COMMITTED:
        raise HTTPException(409, detail={
            "code": "fact_decision_before_commit",
            "message": "continuity facts can only be decided after exact draft commit",
        })
    proposal = next(
        (item for item in record.draft.fill.continuity_proposals if item.key == fact_key),
        None,
    )
    if proposal is None:
        raise HTTPException(404, detail={
            "code": "fact_proposal_not_found",
            "message": "the committed draft has no continuity proposal with this key",
        })

    decision_path = p.harness_dir / "fact_decisions" / draft_id / str(revision) / f"{fact_key}.json"
    decision = {
        "draft_id": draft_id,
        "draft_revision": revision,
        "proposal_fingerprint": proposal.fingerprint(),
        "action": req.action,
    }
    with _TYPED_FACT_WRITE_LOCK:
        if decision_path.exists():
            existing = json.loads(decision_path.read_text(encoding="utf-8"))
            if existing != decision:
                raise HTTPException(409, detail={
                    "code": "fact_decision_conflict",
                    "message": "this immutable proposal already has a different decision",
                })
            return {"status": f"{req.action}ed", "key": fact_key}
        if req.action == "accept":
            sheet = (
                f"---\nid: {proposal.key}\ncategory: continuity\n"
                f"source_draft: {draft_id}@{revision}\n---\n"
                f"# {proposal.key}\n\n{proposal.value}\n"
            )
            target = p.lore_file("continuity", proposal.key)
            if target.exists() and target.read_text(encoding="utf-8") != sheet:
                raise HTTPException(409, detail={
                    "code": "continuity_fact_exists",
                    "message": "an authored continuity fact with this key already exists",
                })
            if not target.exists():
                write_lore_entity(p, "continuity", proposal.key, sheet)
        _atomic_write_text(
            decision_path,
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
        )
    return {"status": f"{req.action}ed", "key": fact_key}


@app.post("/api/drafts/{draft_id}/{revision}/reject", response_model=DraftRecord)
async def reject_typed_draft(draft_id: str, revision: int, req: TypedDraftRejectRequest):
    store = _draft_store(_p())
    try:
        record = store.get(draft_id, revision)
        if store.latest_revision(draft_id) != revision:
            raise DraftConflict("draft_superseded", "a newer draft revision already exists")
        if record.draft.fingerprint() != req.expected_draft_fingerprint:
            raise DraftConflict("draft_fingerprint_conflict", "draft changed since it was loaded")
        if record.lifecycle_state in {DraftLifecycle.COMMITTED, DraftLifecycle.REJECTED}:
            raise DraftConflict("draft_closed", "committed or rejected drafts cannot be rejected")
        rejected = store.transition(
            draft_id, revision,
            expected=record.lifecycle_state,
            target=DraftLifecycle.REJECTED,
        )
    except (DraftConflict, DraftNotFound) as exc:
        _raise_draft_store_http(exc)
    return rejected.model_dump(mode="json")


# ── Entity extraction ─────────────────────────────────────────────────────────

class ExtractEntitiesRequest(BaseModel):
    prose: str
    direction: str = ""


@app.post("/api/extract-entities")
async def extract_entities_endpoint(req: ExtractEntitiesRequest):
    """Second-pass NER + theme extraction on a passage's prose."""
    p = _p()
    cfg = load_config(p)
    try:
        entities = await extract_entities(cfg, req.prose, direction=req.direction)
    except Exception as e:
        raise HTTPException(502, f"Entity extraction error: {e}")
    return entities.model_dump()


class SceneKeywordsRequest(BaseModel):
    text: str


@app.post("/api/scene-keywords")
async def scene_keywords(req: SceneKeywordsRequest):
    """Generate scene keywords + one-sentence summary from prose or prompt."""
    cfg = load_config(_p())
    prompt = build_scene_keywords_prompt(req.text)
    schema = {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": ["keywords", "summary"],
    }
    try:
        raw = await call_ollama(cfg, prompt, timeout=30.0, temperature=0.2, num_predict=128, format_spec=schema)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    data = parse_json_object(raw) or {}
    keywords = [k.strip() for k in data.get("keywords", []) if isinstance(k, str) and k.strip()]
    summary = str(data.get("summary", "")).strip()
    return {"keywords": keywords[:12], "summary": summary, "raw": raw}


def _passage_prose(p: ProjectPaths, passage_id: str) -> str:
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if not entry:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")
    tw_path = p.root / entry.file
    raw = tw_path.read_text(encoding="utf-8") if tw_path.exists() else ""
    # Rough strip of header, macros, and comments to focus on prose.
    raw = re.sub(r'^::.*$', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'<!--[\s\S]*?-->', '', raw)
    raw = re.sub(r'<<[^>]+>>', '', raw)
    return raw.strip()


@app.post("/api/passage/{passage_id}/generate-summary")
async def generate_summary_for_passage(passage_id: str):
    p = _p()
    cfg = load_config(p)
    prose = _passage_prose(p, passage_id)
    if not prose:
        return {"summary": ""}
    try:
        raw = await call_ollama(cfg, build_summary_prompt(prose), timeout=20.0, temperature=0.2, num_predict=80)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    summary = re.split(r'(?<=[.!?])\s', raw.strip())[0].strip().strip('"\'')[:150]
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if entry:
        entry.summary = summary
        save_story(p, graph)
    return {"summary": summary}


@app.post("/api/passage/{passage_id}/generate-threads")
async def generate_threads_for_passage(passage_id: str):
    p = _p()
    cfg = load_config(p)
    prose = _passage_prose(p, passage_id)
    schema = {
        "type": "object",
        "properties": {
            "open_threads": {"type": "array", "items": {"type": "string"}},
            "world_state": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["open_threads", "world_state"],
    }
    try:
        raw = await call_ollama(cfg, build_scene_threads_prompt(prose), timeout=30.0, temperature=0.2, num_predict=180, format_spec=schema)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    data = parse_json_object(raw) or {}
    open_threads = [t.strip() for t in data.get("open_threads", []) if isinstance(t, str) and t.strip()]
    world_state = [t.strip() for t in data.get("world_state", []) if isinstance(t, str) and t.strip()]
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if entry:
        entry.snapshot.open_threads = open_threads[:6]
        entry.snapshot.world_state = world_state[:8]
        save_story(p, graph)
    return {"open_threads": open_threads[:6], "world_state": world_state[:8]}


@app.post("/api/passage/{passage_id}/suggest-choices")
async def suggest_choices_for_passage(passage_id: str):
    p = _p()
    cfg = load_config(p)
    prose = _passage_prose(p, passage_id)
    schema = {
        "type": "object",
        "properties": {
            "choices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, "hint": {"type": "string"}},
                    "required": ["text", "hint"],
                },
            },
        },
        "required": ["choices"],
    }
    try:
        raw = await call_ollama(cfg, build_scene_choices_prompt(prose), timeout=30.0, temperature=0.4, num_predict=220, format_spec=schema)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    data = parse_json_object(raw) or {}
    choices = [
        {"text": str(c.get("text", "")).strip(), "hint": str(c.get("hint", "")).strip()}
        for c in data.get("choices", []) if isinstance(c, dict)
    ]
    choices = [c for c in choices if c["text"]]
    return {"choices": choices[:4]}


@app.post("/api/passage/{passage_id}/suggest-state")
async def suggest_state_for_passage(passage_id: str):
    p = _p()
    cfg = load_config(p)
    prose = _passage_prose(p, passage_id)
    schema = {
        "type": "object",
        "properties": {
            "state": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["state"],
    }
    try:
        raw = await call_ollama(cfg, build_scene_state_prompt(prose), timeout=30.0, temperature=0.3, num_predict=140, format_spec=schema)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    data = parse_json_object(raw) or {}
    state = [s.strip() for s in data.get("state", []) if isinstance(s, str) and s.strip()]
    return {"state": state[:6]}


def _clean_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", (value or "").strip().lower()).strip("_")


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        v = str(value or "").strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


class SceneCharacterEdit(BaseModel):
    id: str
    status: str = "present"
    knows: list[str] = []
    relationship_to_player: str = ""


class PassageMediaSlotEdit(BaseModel):
    id: str
    type: str = "image"
    keywords: list[str] = []


class PassageMetadataUpdate(BaseModel):
    summary: Optional[str] = None
    children: Optional[list[str]] = None
    state_writes: Optional[list[str]] = None
    characters_present: Optional[list[SceneCharacterEdit]] = None
    open_threads: Optional[list[str]] = None
    world_state: Optional[list[str]] = None
    media_slots: Optional[list[PassageMediaSlotEdit]] = None


@app.post("/api/passage/{passage_id}/metadata")
async def update_passage_metadata(passage_id: str, body: PassageMetadataUpdate):
    p = _p()
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if entry is None:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")

    if body.summary is not None:
        entry.summary = body.summary.strip()

    if body.children is not None:
        old_children = set(entry.children)
        new_children = _dedupe_strings(body.children)
        entry.children = new_children
        for child_id in old_children - set(new_children):
            child = graph.passages.get(child_id)
            if child and passage_id in child.parents:
                child.parents.remove(passage_id)
        for child_id in new_children:
            child = graph.passages.get(child_id)
            if child and passage_id not in child.parents:
                child.parents.append(passage_id)

    if body.state_writes is not None:
        entry.state_writes = _dedupe_strings(body.state_writes)

    if body.characters_present is not None:
        chars: list[CharacterPresent] = []
        for raw in body.characters_present:
            cid = _clean_id(raw.id)
            if not cid:
                continue
            if load_character(p, cid) is None:
                sheet = f"---\nid: {cid}\nname: {cid}\ntags: []\n---\n# {cid}\n\n"
                write_character(p, cid, sheet)
            chars.append(CharacterPresent(
                id=cid,
                status=(raw.status or "present").strip(),
                knows=_dedupe_strings(raw.knows),
                relationship_to_player=raw.relationship_to_player.strip(),
            ))
        entry.snapshot.characters_present = chars

    if body.open_threads is not None:
        entry.snapshot.open_threads = _dedupe_strings(body.open_threads)[:10]

    if body.world_state is not None:
        entry.snapshot.world_state = _dedupe_strings(body.world_state)[:20]

    if body.media_slots is not None:
        slots = load_slots(p)
        old_slot_ids = set(entry.media_slots)
        new_slot_ids: list[str] = []
        for raw in body.media_slots:
            sid = _clean_id(raw.id)
            if not sid:
                continue
            if sid in new_slot_ids:
                continue
            previous = slots.slots.get(sid)
            # Preserve description/alt/caption/embed-options/resolution on edit —
            # only type + keywords come from this form.
            slot = previous.model_copy() if previous else MediaSlot(passage=passage_id)
            slot.passage = passage_id
            slot.type = (raw.type or "image").strip() or "image"
            slot.keywords = _dedupe_strings(raw.keywords)
            slots.slots[sid] = slot
            new_slot_ids.append(sid)
        for sid in old_slot_ids - set(new_slot_ids):
            slot = slots.slots.get(sid)
            if slot and slot.passage == passage_id:
                del slots.slots[sid]
        entry.media_slots = new_slot_ids
        save_slots(p, slots)

    save_story(p, graph)
    return {"status": "saved", "passage": entry.model_dump()}


@app.delete("/api/passage/{passage_id}/media/{slot_id}")
async def delete_passage_media(passage_id: str, slot_id: str):
    """Detach a media slot from a passage and delete it: drop it from
    entry.media_slots, remove the slot record, and strip the
    ``<!-- media:slot_id -->`` line from the passage .tw file."""
    p = _p()
    graph = load_story(p)
    entry = graph.passages.get(passage_id)
    if entry is None:
        raise HTTPException(404, f"Passage {passage_id!r} not found.")

    if slot_id in entry.media_slots:
        entry.media_slots.remove(slot_id)

    tw = p.root / entry.file
    if tw.exists():
        content = tw.read_text(encoding="utf-8")
        stripped = re.sub(
            rf'^[ \t]*<!-- media:{re.escape(slot_id)} -->[ \t]*\r?\n?',
            '', content, flags=re.MULTILINE,
        )
        if stripped != content:
            tw.write_text(stripped, encoding="utf-8")

    slots = load_slots(p)
    if slot_id in slots.slots:
        del slots.slots[slot_id]
        save_slots(p, slots)

    save_story(p, graph)
    return {"status": "deleted", "passage": passage_id, "slot_id": slot_id}


@app.post("/api/passage/{passage_id}/suggest-characters")
async def suggest_characters_for_passage(passage_id: str):
    p = _p()
    cfg = load_config(p)
    prose = _passage_prose(p, passage_id)
    try:
        entities = await extract_entities(cfg, prose, direction="characters present in this scene")
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")

    known_by_id: dict[str, dict] = {}
    known_by_name: dict[str, dict] = {}
    for ch in list_characters(p):
        known_by_id[ch["id"].lower()] = ch
        known_by_name[str(ch.get("name", "")).strip().lower()] = ch

    suggestions: list[dict] = []
    seen: set[str] = set()
    for name in entities.characters:
        raw = str(name or "").strip()
        if not raw:
            continue
        match = known_by_id.get(raw.lower()) or known_by_name.get(raw.lower())
        cid = match["id"] if match else _clean_id(raw)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        suggestions.append({
            "id": cid,
            "name": match.get("name", raw) if match else raw,
            "status": "present",
            "existing": bool(match),
        })
    return {"characters": suggestions[:8]}


# ── Commit ─────────────────────────────────────────────────────────────────────

class CommitRequest(BaseModel):
    raw_output: str       # original model output to re-parse
    arc_name: str
    passage_slug: str
    parent_passage_id: Optional[str] = None
    branch_name: str = "main"
    choice_index: Optional[int] = None
    # overrides: human may have edited the parsed output before committing
    override_parsed: Optional[dict] = None
    passage_type: str = "normal"   # see PASSAGE_TYPES
    # type-specific fields
    entry_condition: str = ""
    fallback_passage: str = ""
    exits: dict[str, str] = {}
    event_odds: int = 100
    dialogue_npc: str = ""
    skill_branch: str = ""         # "success" | "fail" | ""


@app.post("/api/commit")
async def commit(req: CommitRequest):
    """Parse + commit a passage. Returns new passage_id and pending facts."""
    from ..models import ModelOutput
    p = _p()

    if req.override_parsed:
        output = ModelOutput.model_validate(req.override_parsed)
    else:
        output = parse_model_output(req.raw_output)

    passage_id, graph = create_passage(
        p=p,
        arc_name=req.arc_name,
        slug=req.passage_slug,
        output=output,
        parent_id=req.parent_passage_id,
        branch_name=req.branch_name,
        choice_index=req.choice_index,
        passage_type=req.passage_type,
        entry_condition=req.entry_condition,
        fallback_passage=req.fallback_passage,
        exits=req.exits,
        event_odds=req.event_odds,
        dialogue_npc=req.dialogue_npc,
        skill_branch=req.skill_branch,
    )

    # write new character/lore sheets
    pending_facts: list[dict] = []
    for nc in output.new_characters:
        fact = {
            "type": "character",
            "id": nc.id,
            "prose_sheet": nc.prose_sheet,
        }
        # Pass through enrichment fields if the model provided them
        for field in ("physical", "personality", "motivation", "backstory", "relationships", "speech"):
            val = getattr(nc, field, "").strip()
            if val:
                fact[field] = val
        pending_facts.append(fact)
    for nl in output.new_lore:
        pending_facts.append({
            "type": "lore",
            "category": nl.category,
            "id": nl.id,
            "prose_sheet": nl.prose_sheet,
        })

    record_generation(p, {
        "label": "commit",
        "passage_id": passage_id,
        "arc_name": req.arc_name,
        "passage_slug": req.passage_slug,
        "parent_passage_id": req.parent_passage_id or "",
        "passage_type": req.passage_type,
        "raw_output": req.raw_output,
        "parsed": output.model_dump(),
        "edited": req.override_parsed is not None,
        "warnings": output.parse_warnings,
    }, kind="commit")

    return {
        "passage_id": passage_id,
        "pending_facts": pending_facts,
        "warnings": output.parse_warnings,
    }


# ── Facts approval ─────────────────────────────────────────────────────────────

class FactApproval(BaseModel):
    action: str   # "accept" | "reject"
    type: str     # "character" | "lore"
    id: str
    category: Optional[str] = None
    prose_sheet: str = ""
    # Enrichment fields for characters
    physical: str = ""
    personality: str = ""
    motivation: str = ""
    backstory: str = ""
    relationships: str = ""
    speech: str = ""


@app.post("/api/facts/approve")
async def approve_fact(body: FactApproval):
    p = _p()
    if body.action == "accept":
        if body.type == "character":
            # Build YAML frontmatter + prose, with enrichment sections if present
            sheet_parts = [f"---\nid: {body.id}\nname: {body.id}\ntags: []\n---", f"# {body.id}\n"]
            if body.prose_sheet:
                sheet_parts.append(body.prose_sheet)
            field_labels = {
                "physical": "Physical Description",
                "personality": "Personality Traits",
                "motivation": "Motivation",
                "backstory": "Backstory",
                "relationships": "Key Relationships",
                "speech": "Speech Mannerisms",
            }
            has_enrichment = False
            for field_key, field_label in field_labels.items():
                val = getattr(body, field_key, "").strip()
                if val:
                    if not has_enrichment:
                        sheet_parts.append("")
                        has_enrichment = True
                    sheet_parts.append(f"## {field_label}\n\n{val}")
            sheet = "\n".join(sheet_parts) + "\n"
            write_character(p, body.id, sheet)
        elif body.type == "lore" and body.category:
            sheet = f"---\nid: {body.id}\ncategory: {body.category}\n---\n# {body.id}\n\n{body.prose_sheet}\n"
            write_lore_entity(p, body.category, body.id, sheet)
        return {"status": "accepted", "id": body.id}
    else:
        return {"status": "rejected", "id": body.id}


# ── Media ──────────────────────────────────────────────────────────────────────

@app.get("/api/media/slots")
async def get_slots():
    slots = list_all_slots(_p())
    return {k: {**v.model_dump(), "fingerprint": _media_slot_fingerprint(v)} for k, v in slots.items()}


class ResolveSlotRequest(BaseModel):
    resolved_path: str
    expected_slot_fingerprint: str = ""


class SlotMutationGuard(BaseModel):
    expected_slot_fingerprint: str = ""


def _media_slot_fingerprint(slot: MediaSlot) -> str:
    payload = json.dumps(slot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_current_slot(slot_id: str, expected_fingerprint: str) -> None:
    slot = list_all_slots(_p()).get(slot_id)
    if slot is None:
        raise HTTPException(404, f"Slot {slot_id!r} not found.")
    if expected_fingerprint and _media_slot_fingerprint(slot) != expected_fingerprint:
        raise HTTPException(409, detail={
            "code": "media_slot_conflict", "message": "media slot changed since it was loaded"
        })


@app.post("/api/media/slots/{slot_id}/resolve")
async def resolve(slot_id: str, body: ResolveSlotRequest):
    _require_current_slot(slot_id, body.expected_slot_fingerprint)
    ok, msg = resolve_slot(_p(), slot_id, body.resolved_path)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "resolved", "message": msg}


@app.post("/api/media/slots/{slot_id}/unresolve")
async def unresolve(slot_id: str, body: SlotMutationGuard = Body(default_factory=SlotMutationGuard)):
    _require_current_slot(slot_id, body.expected_slot_fingerprint)
    ok, msg = unresolve_slot(_p(), slot_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "pending", "message": msg}


@app.get("/api/media/slots/search")
async def search_media_slots(q: str = "", status: str = ""):
    """Filter slots by free-text query and/or status (pending|resolved)."""
    slots = search_slots(_p(), q, status)
    return {k: v.model_dump() for k, v in slots.items()}


class SlotMetaRequest(BaseModel):
    expected_slot_fingerprint: str = ""
    description: Optional[str] = None
    alt: Optional[str] = None
    caption: Optional[str] = None
    type: Optional[str] = None
    keywords: Optional[list[str]] = None
    lazy: Optional[bool] = None
    loop: Optional[bool] = None
    autoplay: Optional[bool] = None
    muted: Optional[bool] = None
    controls: Optional[bool] = None
    poster: Optional[str] = None


@app.post("/api/media/slots/{slot_id}/meta")
async def update_slot_meta(slot_id: str, body: SlotMetaRequest):
    """Set description / alt / caption / type / embed options on a slot."""
    _require_current_slot(slot_id, body.expected_slot_fingerprint)
    values = body.model_dump(exclude_none=True, exclude={"expected_slot_fingerprint"})
    ok, msg = set_slot_meta(_p(), slot_id, **values)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "message": msg}


@app.delete("/api/media/slots/{slot_id}")
async def delete_media_slot(slot_id: str):
    if not delete_slot(_p(), slot_id):
        raise HTTPException(404, f"Slot {slot_id!r} not found.")
    return {"status": "deleted", "slot_id": slot_id}


@app.get("/api/media/files")
async def media_files():
    """List usable files in the project media/ folder for one-click resolving."""
    return {"files": list_media_files(_p())}


@app.get("/api/media/slots/{slot_id}/preview")
async def preview_media_slot(slot_id: str):
    """Serve only the file already approved on a resolved media slot."""
    slot = list_all_slots(_p()).get(slot_id)
    if slot is None:
        raise HTTPException(404, f"Slot {slot_id!r} not found.")
    if slot.status != "resolved" or not slot.resolved_path:
        raise HTTPException(409, detail={
            "code": "media_slot_unresolved", "message": "media slot is unresolved"
        })
    path = Path(slot.resolved_path)
    if not path.is_absolute():
        path = _p().root / path
    path = path.resolve()
    valid_extensions = {extension for values in MEDIA_EXTS.values() for extension in values}
    if not path.is_file() or path.suffix.lower() not in valid_extensions:
        raise HTTPException(404, detail={
            "code": "media_file_missing", "message": "resolved media file is unavailable"
        })
    return FileResponse(path)


class ImportMediaRequest(BaseModel):
    src_path: str
    dest_name: str = ""


@app.post("/api/media/import")
async def import_media(body: ImportMediaRequest):
    """Copy an external file into the project media/ library."""
    ok, result = import_media_file(_p(), body.src_path, body.dest_name)
    if not ok:
        raise HTTPException(400, result)
    return {"status": "imported", "rel_path": result}


# ── Manifest sync ──────────────────────────────────────────────────────────────

@app.get("/api/manifest/sync")
async def manifest_sync():
    missing_json, missing_disk = sync_manifest(_p())
    return {
        "missing_from_json": missing_json,
        "missing_from_disk": missing_disk,
        "ok": not missing_json and not missing_disk,
    }


@app.post("/api/manifest/rebuild")
async def manifest_rebuild():
    """Reconstruct story.json from the .tw files on disk. Repairs manifest
    drift and duplicate file ownership; preserves authorial snapshots/summaries
    for passages that still exist."""
    report = rebuild_and_save(_p())
    return {"report": report, "changed": bool(report)}


# ── Premise & Story Points ────────────────────────────────────────────────────

@app.get("/api/premise")
async def get_premise():
    p = _p()
    return {
        "premise": p.premise_md.read_text(encoding="utf-8") if p.premise_md.exists() else "",
        "story_points": p.story_points_md.read_text(encoding="utf-8") if p.story_points_md.exists() else "",
    }


class SavePremiseRequest(BaseModel):
    premise: Optional[str] = None
    story_points: Optional[str] = None


@app.post("/api/premise")
async def save_premise(body: SavePremiseRequest):
    p = _p()
    if body.premise is not None:
        p.premise_md.write_text(body.premise, encoding="utf-8")
    if body.story_points is not None:
        p.story_points_md.write_text(body.story_points, encoding="utf-8")
    return {"status": "saved"}


# ── Story Init wizard ─────────────────────────────────────────────────────────

class StoryInitRequest(BaseModel):
    title: str
    premise: str = ""
    tone: str = ""
    themes: str = ""
    world_overview: str = ""
    opening_situation: str = ""
    story_points: str = ""
    characters: list[dict] = []   # [{id, name, description}]
    locations: list[dict] = []    # [{id, name, description}]


@app.post("/api/init-story")
async def init_story(body: StoryInitRequest):
    """
    Populate premise.md, story_points.md, and create character/lore stubs
    from the init wizard form. Safe to call on an existing project — only
    overwrites files explicitly provided.
    """
    # The browser wizard is also the entry point for a completely bare target
    # directory, not only for a CLI-initialized project.
    p = init_project(_PROJECT_ROOT, title=body.title or "Untitled Story")
    cfg = load_config(p)

    # update story title in config
    if body.title:
        cfg.story_title = body.title
        save_config(p, cfg)

    # build premise.md
    sections = [f"# Premise\n\n{body.premise or '(Write your premise here.)'}"]
    if body.tone:
        sections.append(f"## Tone\n\n{body.tone}")
    if body.themes:
        sections.append(f"## Themes\n\n{body.themes}")
    if body.world_overview:
        sections.append(f"## World Overview\n\n{body.world_overview}")
    if body.opening_situation:
        sections.append(f"## Opening Situation\n\n{body.opening_situation}")
    p.premise_md.write_text("\n\n".join(sections) + "\n", encoding="utf-8")

    # story_points.md + seed the structured plan (beats/acts) from it
    if body.story_points:
        p.story_points_md.write_text(f"# Story Points\n\n{body.story_points}\n", encoding="utf-8")
        try:
            import_story_points(p, replace=True)
        except Exception:
            pass  # plan seeding is best-effort; never block project init

    # create character stubs
    created_chars = []
    for ch in body.characters:
        cid = ch.get("id", "").strip().lower().replace(" ", "_")
        name = ch.get("name", cid)
        desc = ch.get("description", "")
        if not cid:
            continue
        # Build a structured character sheet with enrichment fields when present.
        sheet_sections = [f"---\nid: {cid}\nname: {name}\ntags: []\n---", f"# {name}\n"]
        if desc:
            sheet_sections.append(desc)
        # Enrichment fields rendered as labelled sections for readability
        field_labels = {
            "physical": "Physical Description",
            "personality": "Personality Traits",
            "motivation": "Motivation",
            "backstory": "Backstory",
            "relationships": "Key Relationships",
            "speech": "Speech Mannerisms",
        }
        has_enrichment = False
        for field_key, field_label in field_labels.items():
            val = ch.get(field_key, "").strip()
            if val:
                if not has_enrichment:
                    sheet_sections.append("")  # blank line before enrichment
                    has_enrichment = True
                sheet_sections.append(f"## {field_label}\n\n{val}")
        sheet = "\n".join(sheet_sections) + "\n"
        write_character(p, cid, sheet)
        created_chars.append(cid)

    # create location stubs
    created_locs = []
    for loc in body.locations:
        lid = loc.get("id", "").strip().lower().replace(" ", "_")
        name = loc.get("name", lid)
        desc = loc.get("description", "")
        if not lid:
            continue
        sheet = (
            f"---\nid: {lid}\ntitle: {name}\ncategory: locations\n---\n"
            f"# {name}\n\n{desc}\n"
        )
        write_lore_entity(p, "locations", lid, sheet)
        created_locs.append(lid)

    return {
        "status": "initialized",
        "created_characters": created_chars,
        "created_locations": created_locs,
    }


# ── Story Init AI helpers ─────────────────────────────────────────────────────

async def _steer_with_inspiration(
    base_direction: str,
    inspiration_files: list[str],
    *query_parts: str,
) -> str:
    """Fold pinned inspiration-corpus chunks into the steering ``direction``.

    The wizard's generators only accept a free-text ``direction``, so retrieved
    inspiration is appended there under an [INSPIRATION] header. ``query_parts``
    (premise/seed/world etc.) make retrieval relevant. No pins → direction
    unchanged.
    """
    pinned = {s for s in (inspiration_files or []) if s and s.strip()}
    if not pinned:
        return base_direction
    p = _p()
    cfg = load_config(p)
    query = " ".join(part for part in (base_direction, *query_parts) if part and part.strip())
    block = await retrieve_inspiration(p, cfg, query or "story", sources=pinned)
    if not block:
        return base_direction
    return (f"{base_direction}\n\n[INSPIRATION]\n{block}").strip()


class GenPremiseRequest(BaseModel):
    seed: str = ""
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/init/generate-premise")
async def init_generate_premise(req: GenPremiseRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.seed)
        return await generate_premise(cfg, req.seed, direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


class GenToneThemesRequest(BaseModel):
    premise: str
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/init/generate-tone-themes")
async def init_generate_tone_themes(req: GenToneThemesRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.premise)
        return await generate_tone_themes(cfg, req.premise, direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


class GenWorldRequest(BaseModel):
    premise: str
    tone: str = ""
    themes: str = ""
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/init/generate-world")
async def init_generate_world(req: GenWorldRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.premise, req.themes)
        return await generate_world(cfg, req.premise, req.tone, req.themes, direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


class GenOpeningRequest(BaseModel):
    premise: str
    world_overview: str = ""
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/init/generate-opening")
async def init_generate_opening(req: GenOpeningRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.premise, req.world_overview)
        return await generate_opening(cfg, req.premise, req.world_overview, direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


class GenSketchRequest(BaseModel):
    premise: str
    world_overview: str = ""
    count: int = 3
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/init/generate-characters")
async def init_generate_characters(req: GenSketchRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.premise, req.world_overview)
        return await generate_characters_sketch(
            cfg, req.premise, req.world_overview, req.count, direction,
        )
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


@app.post("/api/init/generate-locations")
async def init_generate_locations(req: GenSketchRequest):
    cfg = load_config(_p())
    try:
        direction = await _steer_with_inspiration(req.direction, req.inspiration_files, req.premise, req.world_overview)
        return await generate_locations_sketch(
            cfg, req.premise, req.world_overview, req.count, direction,
        )
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


@app.get("/api/project-status")
async def project_status():
    """Return whether project looks empty (for showing init wizard)."""
    p = _p()
    graph = load_story(p) if p.story_json.exists() else None
    premise = p.premise_md.read_text(encoding="utf-8") if p.premise_md.exists() else ""
    placeholders = (
        "(Write your premise here.)",
        "(What is this story about?)",
        "Write your story premise",
    )
    has_premise = bool(premise.strip()) and not any(marker in premise for marker in placeholders)
    is_empty = (not graph or not graph.passages) and not has_premise
    return {
        "is_empty": is_empty,
        "passage_count": len(graph.passages) if graph else 0,
        "has_premise": has_premise,
    }


# ── Characters API ────────────────────────────────────────────────────────────

@app.get("/api/characters")
async def get_characters():
    return {"characters": list_characters(_p())}


@app.get("/api/characters/{char_id}")
async def get_character(char_id: str):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", char_id):
        raise HTTPException(422, "invalid character id")
    p = _p()
    content = load_character(p, char_id)
    if content is None:
        raise HTTPException(404, f"Character {char_id!r} not found.")
    # find passages that mention this character
    graph = load_story(p)
    appearances = [
        pid for pid, e in graph.passages.items()
        if any(c.id == char_id for c in e.snapshot.characters_present)
        or any(c.id == char_id for c in e.snapshot.characters_offscreen)
    ]
    meta, _ = parse_yaml_frontmatter(content)
    return {
        "id": char_id,
        "content": content,
        "appearances": appearances,
        "keywords": meta.get("keywords", []),
        "tags": meta.get("tags", []),
        "content_fingerprint": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


class KeywordsBody(BaseModel):
    keywords: list[str]


@app.post("/api/characters/{char_id}/keywords")
async def set_character_keywords_endpoint(char_id: str, body: KeywordsBody):
    p = _p()
    ok = set_character_keywords(p, char_id, body.keywords)
    if not ok:
        raise HTTPException(404, f"Character {char_id!r} not found.")
    return {"status": "saved", "id": char_id, "keywords": body.keywords}


class GenerateKeywordsBody(BaseModel):
    direction: str = ""


@app.post("/api/characters/{char_id}/generate-keywords")
async def generate_character_keywords(
    char_id: str,
    body: GenerateKeywordsBody = Body(default_factory=GenerateKeywordsBody),
):
    p = _p()
    cfg = load_config(p)
    content = load_character(p, char_id)
    if content is None:
        raise HTTPException(404, f"Character {char_id!r} not found.")
    try:
        keywords = await extract_keywords(cfg, content, kind="character", direction=body.direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    return {"id": char_id, "keywords": keywords}


class SaveCharacterRequest(BaseModel):
    content: str
    expected_content_fingerprint: str = ""


@app.post("/api/characters/{char_id}")
async def save_character(char_id: str, body: SaveCharacterRequest):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", char_id):
        raise HTTPException(422, "invalid character id")
    p = _p()
    current = load_character(p, char_id)
    if current is None:
        raise HTTPException(404, f"Character {char_id!r} not found.")
    current_fingerprint = hashlib.sha256(current.encode("utf-8")).hexdigest()
    if body.expected_content_fingerprint and body.expected_content_fingerprint != current_fingerprint:
        raise HTTPException(409, detail={
            "code": "character_content_conflict",
            "message": "character sheet changed since it was loaded",
        })
    write_character(p, char_id, body.content)
    return {
        "status": "saved",
        "id": char_id,
        "content_fingerprint": hashlib.sha256(body.content.encode("utf-8")).hexdigest(),
    }


class NewCharacterRequest(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    tags: list[str] = []


@app.post("/api/characters")
async def create_character(body: NewCharacterRequest):
    p = _p()
    cid = _clean_id(body.id)
    if not cid:
        raise HTTPException(400, "Character id is required.")
    if load_character(p, cid) is not None:
        raise HTTPException(409, detail={
            "code": "character_exists", "message": f"Character {cid!r} already exists."
        })
    name = body.name or cid
    sheet = (
        f"---\nid: {cid}\nname: {name}\ntags: {body.tags}\n---\n"
        f"# {name}\n\n{body.description or '(No description yet.)'}\n"
    )
    write_character(p, cid, sheet)
    return {"status": "created", "id": cid}


@app.delete("/api/characters/{char_id}")
async def delete_character_endpoint(char_id: str):
    ok = delete_character(_p(), char_id)
    if not ok:
        raise HTTPException(404, f"Character {char_id!r} not found.")
    return {"status": "deleted", "id": char_id}


# ── Lore API ──────────────────────────────────────────────────────────────────

@app.get("/api/lore")
async def get_lore():
    return {"lore": list_lore(_p())}


@app.get("/api/lore/{category}/{lore_id}")
async def get_lore_entry(category: str, lore_id: str):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", category) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", lore_id):
        raise HTTPException(422, "invalid lore identity")
    p = _p()
    content = load_lore_entity(p, category, lore_id)
    if content is None:
        raise HTTPException(404, f"Lore {category}/{lore_id} not found.")
    meta, _ = parse_yaml_frontmatter(content)
    return {
        "category": category,
        "id": lore_id,
        "content": content,
        "keywords": meta.get("keywords", []),
        "content_fingerprint": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


@app.post("/api/lore/{category}/{lore_id}/keywords")
async def set_lore_keywords_endpoint(category: str, lore_id: str, body: KeywordsBody):
    p = _p()
    ok = set_lore_keywords(p, category, lore_id, body.keywords)
    if not ok:
        raise HTTPException(404, f"Lore {category}/{lore_id} not found.")
    return {"status": "saved", "category": category, "id": lore_id, "keywords": body.keywords}


@app.post("/api/lore/{category}/{lore_id}/generate-keywords")
async def generate_lore_keywords(
    category: str, lore_id: str,
    body: GenerateKeywordsBody = Body(default_factory=GenerateKeywordsBody),
):
    p = _p()
    cfg = load_config(p)
    content = load_lore_entity(p, category, lore_id)
    if content is None:
        raise HTTPException(404, f"Lore {category}/{lore_id} not found.")
    try:
        keywords = await extract_keywords(cfg, content, kind="lore", direction=body.direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    return {"category": category, "id": lore_id, "keywords": keywords}


class SaveLoreRequest(BaseModel):
    content: str
    expected_content_fingerprint: str = ""


@app.post("/api/lore/{category}/{lore_id}")
async def save_lore_entry(category: str, lore_id: str, body: SaveLoreRequest):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", category) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", lore_id):
        raise HTTPException(422, "invalid lore identity")
    p = _p()
    current = load_lore_entity(p, category, lore_id)
    if current is None:
        raise HTTPException(404, f"Lore {category}/{lore_id} not found.")
    current_fingerprint = hashlib.sha256(current.encode("utf-8")).hexdigest()
    if body.expected_content_fingerprint and body.expected_content_fingerprint != current_fingerprint:
        raise HTTPException(409, detail={
            "code": "lore_content_conflict",
            "message": "lore sheet changed since it was loaded",
        })
    write_lore_entity(p, category, lore_id, body.content)
    return {
        "status": "saved",
        "content_fingerprint": hashlib.sha256(body.content.encode("utf-8")).hexdigest(),
    }


class NewLoreRequest(BaseModel):
    category: str
    id: str
    title: str = ""
    description: str = ""


@app.post("/api/lore")
async def create_lore(body: NewLoreRequest):
    p = _p()
    lid = _clean_id(body.id)
    cat = _clean_id(body.category)
    if not lid or not cat:
        raise HTTPException(422, "Lore category and id are required.")
    if load_lore_entity(p, cat, lid) is not None:
        raise HTTPException(409, detail={
            "code": "lore_exists", "message": f"Lore {cat}/{lid} already exists."
        })
    title = body.title or lid
    sheet = (
        f"---\nid: {lid}\ntitle: {title}\ncategory: {cat}\n---\n"
        f"# {title}\n\n{body.description or '(No description yet.)'}\n"
    )
    write_lore_entity(p, cat, lid, sheet)
    return {"status": "created", "category": cat, "id": lid}


# ── Notes API ─────────────────────────────────────────────────────────────────

@app.get("/api/notes")
async def get_notes():
    return {"notes": list_notes(_p())}


@app.get("/api/notes/{note_id}")
async def get_note(note_id: str):
    content = load_note(_p(), note_id)
    if content is None:
        raise HTTPException(404, f"Note {note_id!r} not found.")
    return {"id": note_id, "content": content}


class SaveNoteRequest(BaseModel):
    content: str


@app.post("/api/notes/{note_id}")
async def save_note_endpoint(note_id: str, body: SaveNoteRequest):
    save_note(_p(), note_id, body.content)
    return {"status": "saved", "id": note_id}


class NewNoteRequest(BaseModel):
    id: str
    title: str = ""


@app.post("/api/notes")
async def create_note(body: NewNoteRequest):
    p = _p()
    nid = body.id.strip().lower().replace(" ", "_")
    title = body.title or nid
    content = f"# {title}\n\n"
    save_note(p, nid, content)
    return {"status": "created", "id": nid}


@app.delete("/api/notes/{note_id}")
async def delete_note_endpoint(note_id: str):
    ok = delete_note(_p(), note_id)
    if not ok:
        raise HTTPException(404, f"Note {note_id!r} not found.")
    return {"status": "deleted"}


# ── Story-points AI generation ────────────────────────────────────────────────

class GenerateStoryPointsRequest(BaseModel):
    premise: str = ""
    tone: str = ""
    themes: str = ""
    world_overview: str = ""
    num_acts: int = 3
    direction: str = ""
    inspiration_files: list[str] = Field(default_factory=list)


@app.post("/api/generate-story-points")
async def generate_story_points(req: GenerateStoryPointsRequest):
    """Ask Ollama to produce structured act beats from a premise."""
    import re as _re
    p = _p()
    cfg = load_config(p)

    direction = await _steer_with_inspiration(
        req.direction, req.inspiration_files, req.premise, req.world_overview,
    )
    prompt = build_story_points_prompt(
        premise=req.premise,
        tone=req.tone,
        themes=req.themes,
        world_overview=req.world_overview,
        num_acts=req.num_acts,
        direction=direction,
    )

    try:
        raw = await call_ollama(cfg, prompt, timeout=90.0, temperature=0.4, label="story-points")
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")

    # Parse acts: ACT N: Title\n- beats...
    acts: list[dict] = []
    act_re = _re.compile(
        r'ACT\s+\d+\s*:\s*([^\n]+)\n((?:(?!ACT\s+\d|OPEN\s+QUESTIONS?)[\s\S])*)',
        _re.IGNORECASE,
    )
    for m in act_re.finditer(raw):
        name = m.group(1).strip()
        content = m.group(2).strip()
        acts.append({"name": name, "content": content})

    # Fallback: if parsing found nothing, return raw as single act
    if not acts:
        acts = [{"name": "Act 1", "content": raw.strip()}]

    # Parse open questions block
    oq_match = _re.search(
        r'OPEN\s+QUESTIONS?\s*:\s*\n(.*?)(?:\n\n|\Z)',
        raw, _re.IGNORECASE | _re.DOTALL,
    )
    open_questions = oq_match.group(1).strip() if oq_match else ""

    return {"acts": acts, "open_questions": open_questions, "raw": raw}


# ── Arcs listing ───────────────────────────────────────────────────────────────

@app.get("/api/arcs")
async def get_arcs():
    """All arc names with their passages, derived from story.json + arcs/ dirs."""
    p = _p()
    graph = load_story(p)
    arcs: dict[str, list[dict]] = {}
    for pid, entry in graph.passages.items():
        arc = entry.arc
        if arc not in arcs:
            arcs[arc] = []
        arcs[arc].append({"id": pid, "summary": entry.summary})
    if p.arcs_dir.exists():
        for d in sorted(p.arcs_dir.iterdir()):
            if d.is_dir() and d.name not in arcs:
                arcs[d.name] = []
    return {"arcs": arcs}


# ── Planning: story beats ⇄ arcs ⇄ passages ─────────────────────────────────────

@app.get("/api/plan")
async def get_plan():
    """Full planning overview: acts, beats+coverage, arcs+status, and gaps."""
    p = _p()
    return {**plan_overview(p), "story_fingerprint": _story_fingerprint(load_story(p))}


def _story_fingerprint(graph) -> str:
    return story_fingerprint(graph)


def _require_story_fingerprint(p: ProjectPaths, expected: str) -> None:
    if expected and _story_fingerprint(load_story(p)) != expected:
        raise HTTPException(409, detail={
            "code": "story_plan_conflict", "message": "story plan changed since it was loaded"
        })


class BeatRequest(BaseModel):
    text: str
    act: str = ""
    expected_story_fingerprint: str = ""


@app.post("/api/plan/beats")
async def create_beat(body: BeatRequest):
    if not body.text.strip():
        raise HTTPException(400, detail={"code": "invalid_beat_text", "message": "Beat text is required."})
    p = _p()
    try:
        beat = add_beat(
            p, body.text, body.act,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    return {"status": "created", "beat": beat.model_dump(), "story_fingerprint": _story_fingerprint(load_story(p))}


class BeatUpdateRequest(BaseModel):
    text: Optional[str] = None
    act: Optional[str] = None
    expected_story_fingerprint: str = ""


@app.put("/api/plan/beats/{beat_id}")
async def edit_beat(beat_id: str, body: BeatUpdateRequest):
    p = _p()
    try:
        updated = update_beat(
            p, beat_id, text=body.text, act=body.act,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    if not updated:
        raise HTTPException(404, f"Beat {beat_id!r} not found.")
    return {"status": "updated", "beat_id": beat_id, "story_fingerprint": _story_fingerprint(load_story(p))}


class PlanDeleteRequest(BaseModel):
    expected_story_fingerprint: str = ""


@app.delete("/api/plan/beats/{beat_id}")
async def remove_beat(beat_id: str, body: PlanDeleteRequest):
    p = _p()
    try:
        deleted = delete_beat(
            p, beat_id, expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    if not deleted:
        raise HTTPException(404, f"Beat {beat_id!r} not found.")
    return {"status": "deleted", "beat_id": beat_id, "story_fingerprint": _story_fingerprint(load_story(p))}


class ActsRequest(BaseModel):
    acts: list[str]


@app.put("/api/plan/acts")
async def edit_acts(body: ActsRequest):
    set_acts(_p(), body.acts)
    return {"status": "ok"}


class OpenQuestionsRequest(BaseModel):
    questions: list[str]


@app.put("/api/plan/open-questions")
async def edit_open_questions(body: OpenQuestionsRequest):
    set_open_questions(_p(), body.questions)
    return {"status": "ok"}


class ArcPlanRequest(BaseModel):
    goal: Optional[str] = None
    beat_ids: Optional[list[str]] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    expected_story_fingerprint: str = ""


@app.put("/api/plan/arcs/{arc_name}")
async def edit_arc_plan(arc_name: str, body: ArcPlanRequest):
    p = _p()
    try:
        ap = set_arc_plan(
            p, arc_name,
            goal=body.goal, beat_ids=body.beat_ids,
            status=body.status, summary=body.summary,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    return {"status": "ok", "arc": arc_name, "plan": ap.model_dump(), "story_fingerprint": _story_fingerprint(load_story(p))}


class PassageBeatsRequest(BaseModel):
    beat_ids: list[str]


@app.put("/api/passages/{passage_id}/beats")
async def edit_passage_beats(passage_id: str, body: PassageBeatsRequest):
    if not set_passage_beats(_p(), passage_id, body.beat_ids):
        raise HTTPException(404, f"Passage {passage_id!r} not found.")
    return {"status": "ok", "passage_id": passage_id, "beat_ids": body.beat_ids}


class ImportPointsRequest(BaseModel):
    replace: bool = False


@app.post("/api/plan/import-points")
async def import_points(body: ImportPointsRequest):
    """Promote story_points.md headings/bullets into structured plan beats."""
    return import_story_points(_p(), replace=body.replace)


class GenItemsRequest(BaseModel):
    count: int = 5
    direction: str = ""


@app.post("/api/plan/generate-beats")
async def generate_plan_beats(body: GenItemsRequest):
    """AI-propose new plot beats from premise + story points, append to the plan."""
    p = _p()
    cfg = load_config(p)
    graph = load_story(p)
    premise = p.premise_md.read_text(encoding="utf-8") if p.premise_md.exists() else ""
    story_points = p.story_points_md.read_text(encoding="utf-8") if p.story_points_md.exists() else ""
    existing = "\n".join(f"- {b.text}" for b in graph.plan.beats)
    try:
        beats = await generate_beats(cfg, premise, story_points, existing, body.count, body.direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    created = add_beats_bulk(p, beats)
    return {"status": "ok", "created": [b.model_dump() for b in created]}


@app.post("/api/plan/generate-arcs")
async def generate_plan_arcs(body: GenItemsRequest):
    """AI-propose new arcs (name + goal) from premise + beats, create them."""
    p = _p()
    cfg = load_config(p)
    graph = load_story(p)
    premise = p.premise_md.read_text(encoding="utf-8") if p.premise_md.exists() else ""
    beats_text = "\n".join(f"- {b.text}" for b in graph.plan.beats)
    existing = "\n".join(f"- {name}" for name in graph.arcs.keys())
    try:
        arcs = await generate_arcs(cfg, premise, beats_text, existing, body.count, body.direction)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    created = add_arcs_bulk(p, arcs)
    return {"status": "ok", "created": created}


class CreateArcRequest(BaseModel):
    name: str
    goal: str = ""
    expected_story_fingerprint: str = ""


@app.post("/api/plan/arcs")
async def create_arc_endpoint(body: CreateArcRequest):
    """Create a new empty arc plan by name."""
    p = _p()
    try:
        res = create_arc(
            p, body.name, body.goal,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    if res is None:
        raise HTTPException(400, detail={"code": "invalid_arc_name", "message": "Arc name is required."})
    name, ap = res
    return {"status": "created", "arc": name, "plan": ap.model_dump(), "story_fingerprint": _story_fingerprint(load_story(p))}


# ── Planned scenes (per arc) ─────────────────────────────────────────────────

class SceneRequest(BaseModel):
    title: str = ""
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    beat_ids: list[str] = Field(default_factory=list)
    expected_story_fingerprint: str = ""


@app.post("/api/plan/arcs/{arc_name}/scenes")
async def create_scene(arc_name: str, body: SceneRequest):
    p = _p()
    try:
        scene = add_scene(
            p, arc_name,
            title=body.title, summary=body.summary,
            keywords=body.keywords, characters=body.characters, beat_ids=body.beat_ids,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    return {"status": "created", "arc": arc_name, "scene": scene.model_dump(), "story_fingerprint": _story_fingerprint(load_story(p))}


class SceneUpdateRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    characters: Optional[list[str]] = None
    beat_ids: Optional[list[str]] = None
    passage_id: Optional[str] = None
    status: Optional[str] = None
    expected_story_fingerprint: str = ""


@app.put("/api/plan/arcs/{arc_name}/scenes/{scene_id}")
async def edit_scene(arc_name: str, scene_id: str, body: SceneUpdateRequest):
    p = _p()
    try:
        updated = update_scene(
            p, arc_name, scene_id,
            title=body.title, summary=body.summary,
            keywords=body.keywords, characters=body.characters,
            beat_ids=body.beat_ids, passage_id=body.passage_id, status=body.status,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    if not updated:
        raise HTTPException(404, f"Scene {scene_id!r} not found in arc {arc_name!r}.")
    return {"status": "updated", "arc": arc_name, "scene_id": scene_id, "story_fingerprint": _story_fingerprint(load_story(p))}


@app.delete("/api/plan/arcs/{arc_name}/scenes/{scene_id}")
async def remove_scene(arc_name: str, scene_id: str, body: PlanDeleteRequest):
    p = _p()
    try:
        deleted = delete_scene(
            p, arc_name, scene_id,
            expected_fingerprint=body.expected_story_fingerprint or None,
        )
    except StoryPlanConflict:
        _require_story_fingerprint(p, body.expected_story_fingerprint)
        raise
    if not deleted:
        raise HTTPException(404, f"Scene {scene_id!r} not found in arc {arc_name!r}.")
    return {"status": "deleted", "arc": arc_name, "scene_id": scene_id, "story_fingerprint": _story_fingerprint(load_story(p))}


class GenerateScenesRequest(BaseModel):
    count: int = 4
    direction: str = ""


@app.post("/api/plan/arcs/{arc_name}/generate-scenes")
async def generate_scenes(arc_name: str, body: GenerateScenesRequest):
    """AI-outline planned scenes for an arc from premise + arc goal + its beats,
    then append them to the arc plan."""
    p = _p()
    cfg = load_config(p)
    graph = load_story(p)
    ap = graph.arcs.get(arc_name)

    premise = p.premise_md.read_text(encoding="utf-8") if p.premise_md.exists() else ""
    arc_notes = p.arc_md(arc_name).read_text(encoding="utf-8") if p.arc_md(arc_name).exists() else ""
    beat_by_id = {b.id: b for b in graph.plan.beats}
    beats_text = "\n".join(
        f"- {beat_by_id[bid].text}" for bid in (ap.beat_ids if ap else []) if bid in beat_by_id
    )
    existing = "\n".join(f"- {s.title}: {s.summary}" for s in (ap.scenes if ap else []))

    try:
        scenes = await generate_arc_scenes(
            cfg,
            premise=premise,
            arc_goal=ap.goal if ap else "",
            arc_notes=arc_notes,
            beats_text=beats_text,
            existing_scenes=existing,
            count=body.count,
            direction=body.direction,
        )
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")

    created = add_scenes_bulk(p, arc_name, scenes)
    return {"status": "ok", "arc": arc_name, "created": [s.model_dump() for s in created]}


# ── Name suggestion ────────────────────────────────────────────────────────────

class SuggestNamesRequest(BaseModel):
    description: str
    suggest_arc: bool = False
    direction: str = ""


@app.post("/api/suggest-names")
async def suggest_names(req: SuggestNamesRequest):
    """Call Ollama with a tiny prompt to suggest passage slug (+ optional arc name)."""
    p = _p()
    cfg = load_config(p)
    prompt = build_suggest_names_prompt(req.description, req.suggest_arc, direction=req.direction)
    try:
        raw = await call_ollama(cfg, prompt, timeout=30.0, temperature=0.2, num_predict=64)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")

    slug = ""
    arc = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("SLUG:"):
            slug = line.split(":", 1)[1].strip().lower().replace(" ", "_")
        elif line.upper().startswith("ARC:"):
            arc = line.split(":", 1)[1].strip().lower().replace(" ", "_")
    # Fallback: if the model didn't return a slug, create one deterministically
    # from the description so the UI can still suggest an ID.
    if not slug:
        import re as _re
        s = req.description.strip().lower()
        # replace non-alphanum with underscores, collapse multiple, trim
        s = _re.sub(r"[^a-z0-9]+", "_", s)
        s = s.strip("_")
        if not s:
            s = "suggested_slug"
        # truncate to reasonable length
        slug = s[:40]
    return {"slug": slug, "arc": arc, "raw": raw}


# ── Model test score cache ─────────────────────────────────────────────────────

def _test_cache_path() -> Path:
    return _PROJECT_ROOT / ".harness" / "cache" / "model_tests.json"


def _load_test_scores() -> dict:
    cp = _test_cache_path()
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_test_scores(scores: dict) -> None:
    cp = _test_cache_path()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Ollama health check ────────────────────────────────────────────────────────

@app.get("/api/ollama/status")
async def ollama_status():
    """Ping Ollama, return available models + cached test scores."""
    import httpx as _httpx
    p = _p()
    cfg = load_config(p)
    scores = _load_test_scores()
    try:
        async with _httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{cfg.ollama_base_url.rstrip('/')}/api/tags")
            r.raise_for_status()
            data = r.json()
            models = [m["name"] for m in data.get("models", [])]
            return {
                "status": "ok",
                "models": models,
                "current": cfg.ollama_model,
                "scores": scores,   # {model: {ok, reply, error, tested_at}}
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "models": [], "current": cfg.ollama_model, "scores": scores}


# ── Per-model smoke test ───────────────────────────────────────────────────────

class TestModelRequest(BaseModel):
    model: str


def _classify_test_error(raw: str) -> dict:
    """Turn an Ollama error string into a friendlier result + flags.

    Recognises the "requires more system memory" case so the UI can mark a
    model as too-big-for-RAM rather than a generic failure.
    """
    msg = (raw or "").strip()
    low = msg.lower()
    if "more system memory" in low or "requires more" in low and "memory" in low:
        # e.g. "model requires more system memory (25.8 GiB) than is available (19.3 GiB)"
        nums = re.findall(r"([\d.]+)\s*([KMGT]i?B)", msg)
        detail = ""
        if len(nums) >= 2:
            detail = f" — needs {nums[0][0]} {nums[0][1]}, have {nums[1][0]} {nums[1][1]}"
        return {"ok": False, "error": f"too big for RAM{detail}", "reply": "", "oom": True}
    return {"ok": False, "error": msg[:160], "reply": "", "oom": False}


@app.post("/api/ollama/test-model")
async def test_model(req: TestModelRequest):
    """
    Send a minimal prompt to a specific model. Saves result to
    .harness/cache/model_tests.json so the score persists across sessions.

    Reads the response body's ``error`` field directly (instead of relying on
    raise_for_status) so Ollama's "requires more system memory" message — which
    arrives as a 500 with a JSON body — is captured and flagged as OOM.
    """
    import httpx as _httpx
    from datetime import datetime, timezone
    p = _p()
    cfg = load_config(p)
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": req.model,
        "prompt": "Reply with the single word OK and nothing else.",
        "stream": False,
        "options": {"num_predict": 5},
    }
    tested_at = datetime.now(timezone.utc).isoformat()
    result: dict
    try:
        async with _httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 404:
                result = {"ok": False, "error": "model not found on Ollama", "reply": "", "oom": False}
            else:
                # Ollama returns runtime failures (OOM, etc.) as an "error" field
                # in the JSON body, often with a 4xx/5xx status — read it first.
                body = {}
                try:
                    body = r.json()
                except Exception:
                    body = {}
                if isinstance(body, dict) and body.get("error"):
                    result = _classify_test_error(body["error"])
                elif r.status_code >= 400:
                    result = {"ok": False, "error": f"HTTP {r.status_code}", "reply": "", "oom": False}
                else:
                    reply = (body.get("response") or "").strip()
                    result = {"ok": True, "reply": reply[:80], "error": "", "oom": False}
    except _httpx.TimeoutException:
        result = {"ok": False, "error": "timed out (20s)", "reply": "", "oom": False}
    except Exception as e:
        result = {"ok": False, "error": str(e)[:120], "reply": "", "oom": False}

    # persist
    scores = _load_test_scores()
    scores[req.model] = {**result, "tested_at": tested_at}
    _save_test_scores(scores)

    return {**result, "tested_at": tested_at}


@app.get("/api/ollama/scores")
async def get_scores():
    """Return cached test scores without re-running any tests."""
    return _load_test_scores()


# ── Debug: recent model calls ───────────────────────────────────────────────────

@app.get("/api/debug/calls")
async def debug_calls():
    """Recent Ollama generation calls — model, prompt variant, options, status.

    Lets you confirm exactly which model + prompt served each call. In-memory,
    newest first, resets on server restart.
    """
    cfg = load_config(_p())
    return {
        "current_model": cfg.ollama_model,
        "model_mode": cfg.model_mode,
        "output_format": getattr(cfg, "output_format", "delimited"),
        "calls": get_call_log(),
    }


@app.post("/api/debug/calls/clear")
async def debug_calls_clear():
    clear_call_log()
    return {"status": "cleared"}


# ── Generation audit log (durable) ───────────────────────────────────────────────

@app.get("/api/generations")
async def get_generations(limit: int = 50):
    """Recent persisted generations (newest first), prompt/prose truncated.

    Unlike /api/debug/calls this survives server restarts — raw outputs live in
    .harness/cache/generations/."""
    return {"generations": list_generations(_p(), limit=limit)}


@app.get("/api/generations/{gen_id}")
async def get_generation(gen_id: str):
    """Full persisted record for one generation, including raw output + prompt."""
    rec = read_generation(_p(), gen_id)
    if rec is None:
        raise HTTPException(404, f"Generation {gen_id!r} not found.")
    return rec


# ── Immutable benchmark artifacts ────────────────────────────────────────────

def _benchmark_outputs_dir() -> Path:
    configured = os.environ.get("HARNESS_BENCHMARK_OUTPUTS", "").strip()
    return Path(configured).resolve() if configured else _p().root / "benchmark_outputs"


def _benchmark_run_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise HTTPException(404, "Benchmark run not found.")
    root = _benchmark_outputs_dir().resolve()
    candidate = (root / run_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(404, "Benchmark run not found.") from exc
    if not candidate.is_dir():
        raise HTTPException(404, "Benchmark run not found.")
    return candidate


class BenchmarkRunSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    benchmark_name: str
    benchmark_version: str
    started_at: str
    result_count: int
    has_comparison: bool


class BenchmarkRunsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[BenchmarkRunSummaryResponse]


class BenchmarkPaginationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: int
    limit: int
    total: int


class BenchmarkRunDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    manifest: dict[str, Any]
    summary: str
    results: list[dict[str, Any]]
    pagination: BenchmarkPaginationResponse


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Unreadable benchmark artifact: {path.name}") from exc


@app.get("/api/benchmarks/runs", response_model=BenchmarkRunsResponse)
async def benchmark_runs():
    root = _benchmark_outputs_dir()
    runs = []
    if root.is_dir():
        for directory in sorted(root.iterdir(), reverse=True):
            manifest_path = directory / "run_manifest.json"
            if not directory.is_dir() or not manifest_path.is_file():
                continue
            manifest = _read_json_file(manifest_path)
            results_path = directory / "results_internal.jsonl"
            result_count = 0
            if results_path.is_file():
                with results_path.open("r", encoding="utf-8") as handle:
                    result_count = sum(1 for line in handle if line.strip())
            runs.append({
                "id": directory.name,
                "run_id": manifest.get("run_id", directory.name),
                "benchmark_name": manifest.get("benchmark_name", ""),
                "benchmark_version": manifest.get("benchmark_version", ""),
                "started_at": manifest.get("started_at", manifest.get("timestamp", "")),
                "result_count": result_count,
                "has_comparison": (directory / "comparison.json").is_file(),
            })
    return {"runs": runs}


@app.get("/api/benchmarks/runs/{run_id}", response_model=BenchmarkRunDetailResponse)
async def benchmark_run(run_id: str, offset: int = 0, limit: int = 100):
    directory = _benchmark_run_dir(run_id)
    if offset < 0 or limit < 1 or limit > 500:
        raise HTTPException(422, "offset must be >= 0 and limit must be 1..500")
    manifest_path = directory / "run_manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(404, "Benchmark run manifest not found.")
    records = []
    total = 0
    results_path = directory / "results_internal.jsonl"
    if results_path.is_file():
        with results_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                if offset <= total < offset + limit:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise HTTPException(422, "Unreadable benchmark results JSONL") from exc
                total += 1
    summary_path = directory / "summary_internal.md"
    return {
        "id": directory.name,
        "manifest": _read_json_file(manifest_path),
        "summary": summary_path.read_text(encoding="utf-8") if summary_path.is_file() else "",
        "results": records,
        "pagination": {"offset": offset, "limit": limit, "total": total},
    }


@app.get("/api/benchmarks/runs/{run_id}/comparison")
async def benchmark_run_comparison(run_id: str):
    path = _benchmark_run_dir(run_id) / "comparison.json"
    if not path.is_file():
        raise HTTPException(404, "This run has no persisted comparison artifact.")
    return _read_json_file(path)


# ── Delete models ──────────────────────────────────────────────────────────────

async def _ollama_delete(base_url: str, model: str) -> tuple[bool, str]:
    """DELETE a model from the Ollama server. Returns (ok, message)."""
    import httpx as _httpx
    url = f"{base_url.rstrip('/')}/api/delete"
    # Send both keys: older Ollama wants "name", newer accepts "model".
    payload = {"name": model, "model": model}
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            r = await client.request("DELETE", url, json=payload)
            if r.status_code == 404:
                return False, "model not found on Ollama"
            r.raise_for_status()
            return True, "deleted"
    except _httpx.TimeoutException:
        return False, "timed out (30s)"
    except Exception as e:
        return False, str(e)[:160]


class DeleteModelRequest(BaseModel):
    model: str


@app.post("/api/ollama/delete-model")
async def delete_model(req: DeleteModelRequest):
    """Delete one model from Ollama and drop its cached test score."""
    p = _p()
    cfg = load_config(p)
    if not req.model.strip():
        raise HTTPException(400, "Model name required.")
    ok, msg = await _ollama_delete(cfg.ollama_base_url, req.model)
    if not ok:
        raise HTTPException(502, f"Delete failed: {msg}")
    # forget the cached score
    scores = _load_test_scores()
    if req.model in scores:
        del scores[req.model]
        _save_test_scores(scores)
    return {
        "status": "deleted",
        "model": req.model,
        # flag so the UI can prompt the user to pick a new model
        "was_current": req.model == cfg.ollama_model,
    }


@app.post("/api/ollama/delete-unresponsive")
async def delete_unresponsive():
    """Delete every model whose latest cached smoke test failed (ok == false).

    Models that were never tested are left alone — only proven-bad ones go.
    """
    p = _p()
    cfg = load_config(p)
    scores = _load_test_scores()
    failing = [m for m, sc in scores.items() if not sc.get("ok", False)]

    deleted: list[str] = []
    errors: dict[str, str] = {}
    for model in failing:
        ok, msg = await _ollama_delete(cfg.ollama_base_url, model)
        if ok:
            deleted.append(model)
            del scores[model]
        else:
            errors[model] = msg
    if deleted:
        _save_test_scores(scores)
    return {
        "status": "ok",
        "deleted": deleted,
        "errors": errors,
        "current_deleted": cfg.ollama_model in deleted,
    }


# ── Inspiration RAG ───────────────────────────────────────────────────────────

@app.get("/api/rag/status")
async def rag_status():
    """Index stats + on-disk file listing under inspiration/."""
    p = _p()
    stats = rag_index_stats(p)
    files: list[dict] = []
    if p.inspiration_dir.exists():
        for f in sorted(p.inspiration_dir.rglob("*")):
            if not f.is_file() or f.name.startswith("."):
                continue
            files.append({
                "path": f.relative_to(p.root).as_posix(),
                "size": f.stat().st_size,
                "ext": f.suffix.lower(),
            })
    return {"index": stats, "files": files}


@app.post("/api/rag/reindex")
async def rag_reindex():
    """Rebuild the inspiration vector index. Blocks until done."""
    p = _p()
    cfg = load_config(p)
    try:
        result = await rag_build_index(p, cfg)
    except Exception as e:
        raise HTTPException(500, f"Indexing failed: {e}")
    return result


def _read_inspiration_text(p: ProjectPaths, rel_path: str) -> str:
    """Read an inspiration file as plain text for summarization.

    Confined to the project inspiration/ folder. JSON game-reports are flattened
    to their passage text; .tw/.twee are lightly stripped of macros/comments.
    """
    rel = (rel_path or "").strip().lstrip("/")
    target = (p.root / rel).resolve()
    insp_root = p.inspiration_dir.resolve()
    if insp_root not in target.parents and target != insp_root:
        raise HTTPException(400, "Path must be inside inspiration/.")
    if not target.is_file():
        raise HTTPException(404, f"File {rel_path!r} not found.")

    raw = target.read_text(encoding="utf-8", errors="replace")
    suffix = target.suffix.lower()
    if suffix == ".json":
        try:
            from ..rag import _passages_from_report
            report = json.loads(raw)
            passages = _passages_from_report(report) if isinstance(report, dict) else []
            if passages:
                return "\n\n".join(pp.get("text", "") for pp in passages)[:8000]
        except Exception:
            pass
        return raw[:8000]
    if suffix in (".tw", ".twee"):
        stripped = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
        stripped = re.sub(r"<<[^>]+>>", "", stripped)
        return stripped[:8000]
    return raw[:8000]


class InspirationSummaryRequest(BaseModel):
    path: str = ""      # inspiration-relative or root-relative file path
    text: str = ""      # or raw text to summarize directly


@app.post("/api/inspiration/summarize")
async def inspiration_summarize(req: InspirationSummaryRequest):
    """Short digest of a reference item: game type, themes, characters."""
    p = _p()
    cfg = load_config(p)
    text = req.text
    if not text.strip() and req.path:
        text = _read_inspiration_text(p, req.path)
    if not text.strip():
        raise HTTPException(400, "Provide a path or text to summarize.")
    try:
        return await summarize_inspiration(cfg, text)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")


@app.get("/api/story-index/status")
async def story_index_status():
    return rag_story_index_stats(_p())


@app.post("/api/story-index/reindex")
async def story_index_reindex():
    """Rebuild the self-story index over committed passages."""
    p = _p()
    cfg = load_config(p)
    try:
        result = await rag_build_story_index(p, cfg)
    except Exception as e:
        raise HTTPException(500, f"Story indexing failed: {e}")
    return result


class RagUploadRequest(BaseModel):
    filename: str            # relative path inside inspiration/, may include subdirs
    content_b64: str         # base64-encoded file bytes
    caption: str = ""        # optional caption (used for images)


@app.post("/api/rag/upload")
async def rag_upload(body: RagUploadRequest):
    """
    Save a file into <project>/inspiration/<filename>.
    For images, also writes a sidecar <name>.caption.txt if caption is provided.
    Does NOT auto-reindex — call /api/rag/reindex after batch uploads.
    """
    import base64
    p = _p()
    # Reject path traversal — only allow paths inside inspiration/.
    safe_name = body.filename.replace("\\", "/").lstrip("/")
    if ".." in safe_name.split("/"):
        raise HTTPException(400, "Path traversal not allowed.")
    dest = (p.inspiration_dir / safe_name).resolve()
    try:
        dest.relative_to(p.inspiration_dir.resolve())
    except ValueError:
        raise HTTPException(400, "Destination escapes inspiration directory.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = base64.b64decode(body.content_b64, validate=True)
    except Exception:
        raise HTTPException(400, "content_b64 is not valid base64.")
    dest.write_bytes(data)

    # Write caption sidecar for images.
    if body.caption and dest.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        caption_path = dest.with_suffix(".caption.txt")
        caption_path.write_text(body.caption.strip() + "\n", encoding="utf-8")

    return {
        "status": "saved",
        "path": dest.relative_to(p.root).as_posix(),
        "size": len(data),
    }


@app.delete("/api/rag/file")
async def rag_delete_file(path: str):
    """Delete a file from inspiration/. Path is relative to project root."""
    p = _p()
    target = (p.root / path).resolve()
    try:
        target.relative_to(p.inspiration_dir.resolve())
    except ValueError:
        raise HTTPException(400, "Path is not inside inspiration/.")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"File {path!r} not found.")
    target.unlink()
    # Also remove sidecar caption if present
    for ext in (".caption.txt", ".txt"):
        sidecar = target.with_suffix(ext)
        if sidecar.exists() and sidecar != target:
            try:
                sidecar.unlink()
            except Exception:
                pass
    return {"status": "deleted", "path": path}


# ── SPA root ───────────────────────────────────────────────────────────────────

def _ui_index(variant: str) -> Path:
    if variant == "next":
        return _next_ui_dir / "index.html"
    return _HERE / "templates" / "index.html"


def _configured_ui() -> str:
    override = os.environ.get("HARNESS_AUTHORING_UI", "").strip().lower()
    if override in {"legacy", "next"}:
        return override
    paths = _p()
    # A bare project has not made an explicit UI choice yet. Start it in the
    # new shell; initialized/existing projects retain their persisted choice.
    if not paths.config_yaml.exists():
        return "next"
    return load_config(paths).authoring_ui


@app.get("/legacy", response_class=HTMLResponse)
async def legacy_spa():
    return HTMLResponse(_ui_index("legacy").read_text(encoding="utf-8"))


@app.get("/next", response_class=HTMLResponse)
async def next_spa():
    return HTMLResponse(_ui_index("next").read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
@app.get("/{path:path}", response_class=HTMLResponse)
async def spa(path: str = ""):
    index = _ui_index(_configured_ui())
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Harness UI not built yet</h1>")

"""Persisted ExperienceProfile revisions and non-mutating migration previews."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..models import StoryGraph
from .contracts import ExperienceMode, ExperienceProfile, StrictFrozenModel


class ExperienceProfileError(RuntimeError):
    code = "experience_profile_error"


class ExperienceProfileConflict(ExperienceProfileError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MigrationImpact(StrictFrozenModel):
    code: str
    severity: Literal["info", "warning"]
    message: str
    count: int = Field(default=0, ge=0)


class ExperienceMigrationPreview(StrictFrozenModel):
    expected_revision: int
    current_profile_fingerprint: str
    graph_fingerprint: str
    candidate: ExperienceProfile
    candidate_fingerprint: str
    preview_fingerprint: str
    graph_rewrite_required: Literal[False] = False
    impacts: tuple[MigrationImpact, ...]


def preset_for_mode(mode: ExperienceMode | str, *, revision: int = 1) -> ExperienceProfile:
    resolved = ExperienceMode(mode)
    factories = {
        ExperienceMode.STORY_DRIVEN: ExperienceProfile.story_driven,
        ExperienceMode.HYBRID: ExperienceProfile.hybrid,
        ExperienceMode.SANDBOX: ExperienceProfile.sandbox,
    }
    return factories[resolved]().model_copy(update={"revision": revision})


class ExperienceProfileStore:
    """Store canonical, immutable profile envelopes under one project directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def latest_revision(self) -> int | None:
        revisions = [
            int(path.stem)
            for path in self.root.glob("*.json")
            if path.stem.isdigit()
        ] if self.root.exists() else []
        return max(revisions) if revisions else None

    def get(self, revision: int | None = None) -> ExperienceProfile:
        target = self.latest_revision() if revision is None else revision
        if target is None:
            raise FileNotFoundError("no persisted experience profile")
        path = self._path(target)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            profile = ExperienceProfile.model_validate(envelope["profile"])
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise ExperienceProfileConflict(
                "experience_profile_corrupt", "experience profile revision is corrupt"
            ) from exc
        if profile.revision != target:
            raise ExperienceProfileConflict(
                "experience_profile_identity_mismatch",
                "experience profile path and revision differ",
            )
        if envelope.get("fingerprint") != profile.fingerprint():
            raise ExperienceProfileConflict(
                "experience_profile_fingerprint_mismatch",
                "experience profile fingerprint differs from its envelope",
            )
        return profile

    def ensure_baseline(self, profile: ExperienceProfile) -> None:
        """Materialize a compatibility baseline once without replacing any bytes."""
        try:
            self._write(profile)
        except ExperienceProfileConflict as exc:
            if exc.code != "experience_profile_revision_exists":
                raise
            if self.get(profile.revision) != profile:
                raise ExperienceProfileConflict(
                    "experience_profile_baseline_conflict",
                    "persisted baseline differs from the loaded compatibility profile",
                ) from exc

    def put(self, profile: ExperienceProfile, *, expected_revision: int) -> ExperienceProfile:
        latest = self.latest_revision()
        if latest != expected_revision:
            raise ExperienceProfileConflict(
                "experience_profile_revision_conflict",
                f"expected revision {expected_revision}, found {latest or 'none'}",
            )
        if profile.revision != expected_revision + 1:
            raise ExperienceProfileConflict(
                "experience_profile_revision_invalid",
                f"candidate revision must be {expected_revision + 1}",
            )
        self._write(profile)
        return profile

    def _path(self, revision: int) -> Path:
        if isinstance(revision, bool) or revision < 1:
            raise ValueError("revision must be positive")
        return self.root / f"{revision}.json"

    def _write(self, profile: ExperienceProfile) -> None:
        envelope = {
            "profile": profile.model_dump(mode="json"),
            "fingerprint": profile.fingerprint(),
        }
        payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        path = self._path(profile.revision)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ExperienceProfileConflict(
                    "experience_profile_revision_exists",
                    "experience profile revision already exists",
                ) from exc
        finally:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def graph_fingerprint(graph: StoryGraph) -> str:
    payload = json.dumps(
        graph.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def preview_experience_migration(
    current: ExperienceProfile,
    candidate: ExperienceProfile,
    graph: StoryGraph,
) -> ExperienceMigrationPreview:
    """Describe semantic impacts without modifying the graph or project files."""
    if candidate.revision != current.revision + 1:
        raise ExperienceProfileConflict(
            "experience_profile_revision_invalid",
            f"candidate revision must be {current.revision + 1}",
        )

    endings = sum(item.passage_type == "ending" for item in graph.passages.values())
    cycles = _cycle_edges(graph)
    impacts: list[MigrationImpact] = []
    if current.mode != candidate.mode:
        impacts.append(MigrationImpact(
            code="experience_mode_changed",
            severity="info",
            message=f"Mode changes from {current.mode.value} to {candidate.mode.value}.",
        ))
    if candidate.ending_policy.value == "required" and endings == 0:
        impacts.append(MigrationImpact(
            code="required_ending_missing",
            severity="warning",
            message="The target profile requires an ending, but the graph has none.",
        ))
    if candidate.ending_policy.value == "none" and endings:
        impacts.append(MigrationImpact(
            code="existing_endings_retained",
            severity="info",
            message="Existing ending passages remain authored content under this profile.",
            count=endings,
        ))
    if candidate.mode == ExperienceMode.STORY_DRIVEN and cycles:
        impacts.append(MigrationImpact(
            code="cyclic_routes_review",
            severity="warning",
            message="Cyclic routes remain valid but should be reviewed for directed pacing.",
            count=cycles,
        ))
    if candidate.main_plot_required and not graph.start_passage:
        impacts.append(MigrationImpact(
            code="main_plot_entry_missing",
            severity="warning",
            message="The target profile requires a main plot but no start passage is configured.",
        ))
    for field, label in (
        ("time_model", "Time model"),
        ("goal_model", "Goal model"),
        ("character_simulation", "Character simulation"),
        ("encounter_reuse", "Encounter reuse"),
        ("failure_persistence", "Failure persistence"),
    ):
        if getattr(current, field) != getattr(candidate, field):
            impacts.append(MigrationImpact(
                code=f"{field}_changed",
                severity="info",
                message=f"{label} changes; existing passages and state are retained.",
            ))
    impacts.append(MigrationImpact(
        code="graph_not_rewritten",
        severity="info",
        message="Saving this revision will not rewrite graph topology or passage files.",
    ))

    graph_hash = graph_fingerprint(graph)
    candidate_hash = candidate.fingerprint()
    token_payload = json.dumps({
        "expected_revision": current.revision,
        "current_profile_fingerprint": current.fingerprint(),
        "graph_fingerprint": graph_hash,
        "candidate_fingerprint": candidate_hash,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return ExperienceMigrationPreview(
        expected_revision=current.revision,
        current_profile_fingerprint=current.fingerprint(),
        graph_fingerprint=graph_hash,
        candidate=candidate,
        candidate_fingerprint=candidate_hash,
        preview_fingerprint=hashlib.sha256(token_payload).hexdigest(),
        impacts=tuple(impacts),
    )


def _cycle_edges(graph: StoryGraph) -> int:
    visited: set[str] = set()
    active: set[str] = set()
    back_edges = 0

    def visit(node: str) -> None:
        nonlocal back_edges
        if node in active:
            back_edges += 1
            return
        if node in visited or node not in graph.passages:
            return
        visited.add(node)
        active.add(node)
        for child in graph.passages[node].children:
            visit(child)
        active.remove(node)

    for passage_id in sorted(graph.passages):
        visit(passage_id)
    return back_edges


__all__ = [
    "ExperienceMigrationPreview",
    "ExperienceProfileConflict",
    "ExperienceProfileError",
    "ExperienceProfileStore",
    "MigrationImpact",
    "graph_fingerprint",
    "preset_for_mode",
    "preview_experience_migration",
]

"""Validation — errors block compile, warnings surface in UI."""
from __future__ import annotations
import re
from pathlib import Path

from .models import PASSAGE_TYPES, StoryGraph, ValidationIssue, ValidationResult
from .planning import recompute_beat_status
from .project import ProjectPaths, load_slots, load_story
from .passage import extract_links, scan_state_reads


def _issue(level: str, code: str, msg: str, passage: str | None = None) -> ValidationIssue:
    return ValidationIssue(level=level, code=code, message=msg, passage=passage)


# ── Individual checks ──────────────────────────────────────────────────────────

def check_broken_links(graph: StoryGraph) -> list[ValidationIssue]:
    issues = []
    for pid, entry in graph.passages.items():
        for child in entry.children:
            if child not in graph.passages:
                issues.append(_issue(
                    "error", "broken_link",
                    f"Passage {pid!r} links to {child!r} which does not exist.",
                    pid,
                ))
    return issues


def check_orphan_passages(graph: StoryGraph) -> list[ValidationIssue]:
    issues = []
    for pid, entry in graph.passages.items():
        if not entry.parents and pid != graph.start_passage:
            issues.append(_issue(
                "error", "orphan_passage",
                f"Passage {pid!r} has no parents and is not the start passage.",
                pid,
            ))
    return issues


def check_passage_types(graph: StoryGraph) -> list[ValidationIssue]:
    """Type-specific structural rules."""
    issues = []
    for pid, entry in graph.passages.items():
        t = entry.passage_type
        if t not in PASSAGE_TYPES:
            issues.append(_issue(
                "error", "bad_passage_type",
                f"Passage {pid!r} has unknown type {t!r}.", pid,
            ))
            continue
        if t == "conditional" and not entry.entry_condition:
            issues.append(_issue(
                "error", "missing_condition",
                f"Conditional passage {pid!r} has no entry_condition.", pid,
            ))
        if t == "conditional" and entry.fallback_passage and entry.fallback_passage not in graph.passages and entry.fallback_passage != "Start":
            issues.append(_issue(
                "error", "missing_fallback",
                f"Conditional passage {pid!r} fallback_passage {entry.fallback_passage!r} does not exist.", pid,
            ))
        if t == "room":
            for direction, target in entry.exits.items():
                if target and target not in graph.passages:
                    issues.append(_issue(
                        "error", "bad_exit",
                        f"Room {pid!r} exit {direction!r} → {target!r} does not exist.", pid,
                    ))
        if t == "random_event" and not (1 <= entry.event_odds <= 100):
            issues.append(_issue(
                "error", "bad_event_odds",
                f"random_event {pid!r} event_odds {entry.event_odds} out of range 1-100.", pid,
            ))
        if t == "ending" and entry.children:
            issues.append(_issue(
                "warning", "ending_has_children",
                f"Ending passage {pid!r} has {len(entry.children)} children (ending is terminal).", pid,
            ))
    return issues


def check_manifest_drift(p: ProjectPaths, graph: StoryGraph) -> list[ValidationIssue]:
    from .compile import collect_passage_files
    issues = []
    on_disk: set[str] = {
        f.relative_to(p.root).as_posix() for f in collect_passage_files(p)
    }

    in_json: set[str] = {e.file for e in graph.passages.values()}
    file_owners: dict[str, list[str]] = {}
    for pid, entry in graph.passages.items():
        file_owners.setdefault(entry.file, []).append(pid)
    for f, owners in sorted(file_owners.items()):
        if len(owners) > 1:
            issues.append(_issue(
                "error",
                "manifest_duplicate_file",
                f"File {f!r} is claimed by multiple passages: {', '.join(owners)}.",
            ))

    for f in sorted(on_disk - in_json):
        issues.append(_issue("error", "manifest_drift",
                             f"File {f!r} on disk but not in story.json."))
    for f in sorted(in_json - on_disk):
        issues.append(_issue("error", "manifest_drift",
                             f"File {f!r} in story.json but not on disk."))
    return issues


def _extract_goto_targets(tw_content: str) -> list[str]:
    """Return literal <<goto "target">> destinations from a passage."""
    targets = []
    for m in re.finditer(r'<<goto\s+["\']([^"\']+)["\']\s*>>', tw_content):
        targets.append(m.group(1))
    return targets


def check_passage_file_links(p: ProjectPaths, graph: StoryGraph) -> list[ValidationIssue]:
    """Validate navigation targets found in passage files, not just story.json children."""
    issues = []
    allowed_special = {"Start", "previous()"}
    for pid, entry in graph.passages.items():
        path = p.root / entry.file
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        targets = extract_links(content) + _extract_goto_targets(content)
        for target in targets:
            if target.startswith("UNRESOLVED_"):
                issues.append(_issue(
                    "error",
                    "unresolved_link",
                    f"Passage {pid!r} still contains unresolved target {target!r}.",
                    pid,
                ))
            elif target not in graph.passages and target not in allowed_special:
                issues.append(_issue(
                    "error",
                    "file_link_missing",
                    f"Passage {pid!r} links to {target!r}, but that passage is not in story.json.",
                    pid,
                ))
            elif target in graph.passages and target not in entry.children and target != pid:
                issues.append(_issue(
                    "warning",
                    "file_link_not_manifested",
                    f"Passage {pid!r} links to {target!r}, but story.json children does not include it.",
                    pid,
                ))
    return issues


# SugarCube container macros that require a matching <</name>>. Self-contained
# macros (set, print, =, -, goto, link-less, etc.) and continuations
# (else, elseif, case, default, next) are intentionally absent — they neither
# open nor close a block.
MACRO_CONTAINERS: frozenset[str] = frozenset({
    "if", "for", "switch", "widget", "link", "button", "capture",
    "silently", "nobr", "append", "prepend", "replace",
    "linkappend", "linkprepend", "linkreplace",
    "timed", "repeat", "type", "createplaylist", "createaudiogroup",
})

_MACRO_NAME_RE = re.compile(r'(/?)\s*([A-Za-z][\w-]*)')


def _iter_macro_tags(content: str):
    """Yield ``(is_close, name, line)`` for each ``<<...>>`` macro tag.

    Quote-aware: ``>>`` and ``<<`` inside a quoted macro argument do not start
    or end a tag, so ``<<if $x eq "a>>b">>`` is one tag, not two. Prose quotes
    are irrelevant — only the span inside a macro shields delimiters.
    """
    i, n = 0, len(content)
    while i < n:
        if content[i:i + 2] != "<<":
            i += 1
            continue
        j = i + 2
        quote = None
        matched = False
        while j < n:
            c = content[j]
            if quote:
                if c == quote:
                    quote = None
                j += 1
                continue
            if c in ('"', "'"):
                quote = c
                j += 1
                continue
            if content[j:j + 2] == ">>":
                matched = True
                break
            j += 1
        if not matched:
            break  # unterminated <<; treat the rest as text
        inner = content[i + 2:j].strip()
        m = _MACRO_NAME_RE.match(inner)
        if m:
            yield m.group(1) == "/", m.group(2).lower(), content.count("\n", 0, i) + 1
        i = j + 2


def check_macro_pairing(p: ProjectPaths, graph: StoryGraph) -> list[ValidationIssue]:
    """Validate SugarCube container-macro nesting with a stack.

    Catches what bare open/close counting cannot: wrong nesting order
    (``<<if>><<for>><</if>><</for>>``), stray closes, and unclosed blocks —
    while ignoring delimiters inside quoted arguments and custom (non-built-in)
    macros it can't reason about.
    """
    issues = []
    for pid, entry in graph.passages.items():
        path = p.root / entry.file
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        stack: list[tuple[str, int]] = []  # (name, line opened)
        for is_close, name, line in _iter_macro_tags(content):
            if not is_close:
                if name in MACRO_CONTAINERS:
                    stack.append((name, line))
                continue
            # closing tag
            if name not in MACRO_CONTAINERS:
                continue  # custom close — can't validate reliably
            if not stack:
                issues.append(_issue(
                    "error", "macro_pairing",
                    f"Passage {pid!r}: stray <</{name}>> at line {line} with no open <<{name}>>.",
                    pid,
                ))
            elif stack[-1][0] == name:
                stack.pop()
            else:
                top, top_line = stack[-1]
                issues.append(_issue(
                    "error", "macro_pairing",
                    f"Passage {pid!r}: <</{name}>> at line {line} but innermost open is "
                    f"<<{top}>> (line {top_line}).",
                    pid,
                ))
                # Recover: if this close matches something deeper, unwind to it
                # so we don't cascade. Otherwise leave the stack untouched.
                names = [s[0] for s in stack]
                if name in names:
                    while stack and stack.pop()[0] != name:
                        pass
        for name, line in stack:
            issues.append(_issue(
                "error", "macro_pairing",
                f"Passage {pid!r}: <<{name}>> opened at line {line} is never closed.",
                pid,
            ))
    return issues


def check_undeclared_state_vars(p: ProjectPaths, graph: StoryGraph) -> list[ValidationIssue]:
    """
    A read of $var is an error if:
    - $var has no declared default in state_variables, AND
    - there exists at least one path through the graph reaching the reader
      without a prior setter.

    Implemented as forward reachability per variable: O(V+E) per var, instead
    of a fresh DFS for every (passage, var) pair. On a wide branching graph the
    old recursion was exponential.
    """
    issues = []
    writers: dict[str, set[str]] = {
        pid: set(e.state_writes) for pid, e in graph.passages.items()
    }

    # Collect reads per passage once (one file read each).
    reads_by_passage: dict[str, set[str]] = {}
    vars_to_check: set[str] = set()
    for pid, entry in graph.passages.items():
        path = p.root / entry.file
        if not path.exists():
            continue
        reads = set(scan_state_reads(path.read_text(encoding="utf-8")))
        reads_by_passage[pid] = reads
        for var in reads:
            decl = graph.state_variables.get(var)
            if decl is not None and decl.default is not None:
                continue  # declared default — never an error
            vars_to_check.add(var)

    # For each variable, find every passage reachable with the var still unset,
    # then flag those that also read it.
    for var in vars_to_check:
        unset = _reachable_unset(graph, writers, var)
        for pid in unset:
            if var in reads_by_passage.get(pid, set()):
                issues.append(_issue(
                    "error", "undeclared_state_var",
                    f"Passage {pid!r} reads {var!r} but no default declared and "
                    f"some path reaches it without setting {var!r}.",
                    pid,
                ))
    return issues


def _reachable_unset(
    graph: StoryGraph,
    writers: dict[str, set[str]],
    var: str,
) -> set[str]:
    """Return passages reachable from start by at least one path on which ``var``
    is not set before arrival.

    A node's own writes don't satisfy its own read (reads treated as preceding
    writes within a passage), matching the prior DFS semantics. A node that
    writes ``var`` blocks propagation of the unset state to its children.
    Cycles terminate naturally — a node is enqueued at most once.
    """
    start = graph.start_passage
    if start not in graph.passages:
        return set()
    unset: set[str] = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        # If this node sets var, children no longer arrive unset via this node.
        if var in writers.get(node, set()):
            continue
        for child in graph.passages[node].children:
            if child in graph.passages and child not in unset:
                unset.add(child)
                stack.append(child)
    return unset


def check_unresolved_media(p: ProjectPaths) -> list[ValidationIssue]:
    """Resolved paths that don't exist on disk are errors."""
    issues = []
    slots = load_slots(p)
    for slot_id, slot in slots.slots.items():
        if slot.resolved_path is not None:
            rp = Path(slot.resolved_path)
            if not rp.is_absolute():
                rp = p.root / rp
            if not rp.exists():
                issues.append(_issue(
                    "error", "unresolved_media",
                    f"Slot {slot_id!r}: resolved_path {slot.resolved_path!r} does not exist.",
                ))
    return issues


def check_pending_media(p: ProjectPaths) -> list[ValidationIssue]:
    """Pending slots are warnings, tagged with their passage so the UI can
    surface them on the focused node."""
    issues = []
    slots = load_slots(p)
    for slot_id, slot in slots.slots.items():
        if slot.status == "pending":
            issues.append(_issue(
                "warning", "pending_media",
                f"Slot {slot_id!r} in passage {slot.passage!r} is still pending.",
                slot.passage or None,
            ))
    return issues


def check_plan_gaps(graph: StoryGraph) -> list[ValidationIssue]:
    """Surface planning gaps as warnings: open beats, arcs with no linked beats,
    and beat references that point at beats no longer in the plan."""
    issues: list[ValidationIssue] = []
    if not graph.plan.beats and not graph.arcs:
        return issues  # no structured plan in use — nothing to nag about

    recompute_beat_status(graph)
    for beat in graph.plan.beats:
        if beat.status == "open" and not any(beat.id in e.plan_beats for e in graph.passages.values()):
            issues.append(_issue(
                "warning", "uncovered_beat",
                f"Plan beat {beat.id!r} ({beat.text[:60]!r}) is not delivered by any passage.",
            ))
    known = {b.id for b in graph.plan.beats}
    for e_id, e in graph.passages.items():
        for bid in e.plan_beats:
            if bid not in known:
                issues.append(_issue(
                    "warning", "unknown_beat_ref",
                    f"Passage {e_id!r} tags beat {bid!r} which is not in the plan.",
                    e_id,
                ))
    return issues


def check_snapshot_bloat(graph: StoryGraph) -> list[ValidationIssue]:
    from .project import SNAPSHOT_MAX_THREADS, SNAPSHOT_MAX_WORLD_STATE
    issues = []
    for pid, entry in graph.passages.items():
        snap = entry.snapshot
        if len(snap.open_threads) > SNAPSHOT_MAX_THREADS:
            issues.append(_issue(
                "warning", "snapshot_bloat",
                f"Passage {pid!r} snapshot has {len(snap.open_threads)} open threads "
                f"(cap {SNAPSHOT_MAX_THREADS}).",
                pid,
            ))
        if len(snap.world_state) > SNAPSHOT_MAX_WORLD_STATE:
            issues.append(_issue(
                "warning", "snapshot_bloat",
                f"Passage {pid!r} snapshot has {len(snap.world_state)} world_state entries "
                f"(cap {SNAPSHOT_MAX_WORLD_STATE}).",
                pid,
            ))
    return issues


# ── Run all checks ─────────────────────────────────────────────────────────────

def run_validation(p: ProjectPaths) -> ValidationResult:
    graph = load_story(p)
    result = ValidationResult()

    checks = [
        check_broken_links(graph),
        check_orphan_passages(graph),
        check_passage_types(graph),
        check_manifest_drift(p, graph),
        check_passage_file_links(p, graph),
        check_macro_pairing(p, graph),
        check_undeclared_state_vars(p, graph),
        check_unresolved_media(p),
        check_pending_media(p),
        check_snapshot_bloat(graph),
        check_plan_gaps(graph),
    ]

    for check_list in checks:
        for issue in check_list:
            if issue.level == "warning":
                result.warnings.append(issue)
            else:
                result.errors.append(issue)

    return result

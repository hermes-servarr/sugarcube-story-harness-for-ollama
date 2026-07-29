"""Passage CRUD, link wiring, manifest sync."""
from __future__ import annotations
import json
import re
import threading
import uuid
from pathlib import Path

from .models import (
    BranchEntry,
    INPUT_MACRO_KINDS,
    MediaSlot,
    ModelOutput,
    PassageEntry,
    ParsedInputField,
    Snapshot,
    StoryGraph,
)
from .project import (
    ProjectPaths,
    ensure_arc,
    load_slots,
    load_story,
    make_passage_id,
    passage_filename_from_slug,
    save_slots,
    save_story,
)
from .snapshot import derive_snapshot
from .snapshot_delta import diff_snapshots


# ── Concurrency guard ─────────────────────────────────────────────────────────
# create_passage performs a read-modify-write on story.json + on-disk passage
# files. Two concurrent commits would otherwise both observe pre-commit state
# and pick the same passage id / filename — producing duplicate file claims and
# clobbered passages.
#
# Lock granularity is per-project-root: independent projects don't block each
# other, while every mutation on the same project serialises.
#
# threading.Lock (not asyncio.Lock) because create_passage is sync and FastAPI
# dispatches sync endpoints onto a threadpool.

_PASSAGE_LOCKS: dict[str, threading.Lock] = {}
_PASSAGE_LOCKS_GUARD = threading.Lock()


def _passage_lock(root: Path) -> threading.Lock:
    """Return (creating if needed) the commit lock for a given project root."""
    key = str(root.resolve())
    with _PASSAGE_LOCKS_GUARD:
        lock = _PASSAGE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PASSAGE_LOCKS[key] = lock
        return lock


# ── Passage file I/O ───────────────────────────────────────────────────────────

def _safe_slug(s: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', (s or "").lower())[:40] or "x"


def _unique_passage_identity(
    graph: StoryGraph,
    p: ProjectPaths,
    arc_name: str,
    slug: str,
) -> tuple[str, Path]:
    """Return a passage ID and file path that do not collide with existing data."""
    base_id = make_passage_id(arc_name, slug)
    base_filename = passage_filename_from_slug(slug)
    used_files = {entry.file for entry in graph.passages.values()}

    def candidate(suffix: str = "") -> tuple[str, Path]:
        passage_id = f"{base_id}{suffix}"
        if suffix:
            stem = base_filename[:-3] if base_filename.endswith(".tw") else base_filename
            filename = f"{stem}{suffix}.tw"
        else:
            filename = base_filename
        return passage_id, p.passage_file(arc_name, filename)

    passage_id, tw_path = candidate()
    while (
        passage_id in graph.passages
        or tw_path.exists()
        or tw_path.relative_to(p.root).as_posix() in used_files
    ):
        passage_id, tw_path = candidate(f"_{uuid.uuid4().hex[:4]}")
    return passage_id, tw_path


def _format_sc_value(val) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        return json.dumps(val)
    return str(val)


def _is_plain_choice(choice) -> bool:
    """True when a choice has no state writes, no skill check, no gating."""
    # TODO(macro-vocab): I2 — update docstring to include "no linkreplace" and
    # add `and not choice.linkreplace` to the return expression below (P3 I2).
    # A linkreplace choice is NOT plain even if it has no other fields set.
    return (
        choice.skill_check is None
        and not choice.state_writes
        and not choice.requires
        and not choice.blocks
    )


# ── <<capture>> wrapping for async macros inside <<for>> loops ─────────────────
#
# SugarCube <<link>> (and <<button>>/<<timed>>/<<linkreplace>> etc.) bodies run
# *asynchronously* — at click time, not at render time. Inside a <<for>> loop
# every iteration shares one closure over the loop variable, so without
# <<capture>> every link created in the loop sees the *final* value of the loop
# variable when clicked. <<capture $v>>…<</capture>> snapshots $v per iteration
# so each link's click handler sees the value it had when that link was rendered.
#
# See docs/sugarcube2-analysis.md §3.9.
#
# The harness currently emits ZERO <<for>> loops — choice lists are iterated in
# Python and emitted as flat <<link>> lines with literal values baked in — so
# no existing code path needs <<capture>> today. The helpers below are
# *preventive / forward-looking*: they let the link renderers wrap in
# <<capture>> when a loop context is active, and remain a no-op otherwise so
# existing output is byte-identical.

_ASYNC_MACROS = ("link", "button", "timed", "linkreplace", "linkappend", "linkprepend")

_VAR_REF_RE = re.compile(r"\$([a-zA-Z_]\w*)")


def _vars_in_set_rhs(state_writes: dict) -> list[str]:
    """Return $variable names read on the RHS of ``<<set $x to $y>>`` writes.

    ``_format_sc_value`` only emits literals (bool/str/int) today, so this is
    empty for current data. But ``state_writes`` is typed ``dict[str, Any]``;
    if a future code path passes a string like ``"$y"`` (a variable reference),
    ``_format_sc_value`` emits it bare (``<<set $x to $y>>``) and that read of
    ``$y`` becomes a capture candidate when a loop variable may mutate it.
    """
    out: list[str] = []
    for val in state_writes.values():
        if isinstance(val, str):
            out.extend(f"${n}" for n in _VAR_REF_RE.findall(val))
    # dedupe, preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def _capture_vars_for_choice(choice, loop_vars: list[str] | None) -> list[str]:
    """Determine which $variables a choice's link body reads that are at risk of
    changing between link creation and click, given an active loop context.

    Two sources of mutable reads:
      * ``skill_check.stat`` — read in the ``<<if $stat gte N>>`` condition.
      * RHS variable references in ``state_writes`` (``<<set $x to $y>>``).

    When ``loop_vars`` is None/empty the harness is not inside a <<for>> loop,
    so nothing is wrapped — the no-op that keeps current output identical.
    """
    if not loop_vars:
        return []
    at_risk = set(loop_vars)
    capture: list[str] = []
    seen: set[str] = set()
    # skill-check path: the condition reads sc.stat (e.g. "$strength").
    if choice.skill_check is not None and choice.skill_check.stat:
        stat = choice.skill_check.stat
        if stat not in seen and stat in at_risk:
            seen.add(stat)
            capture.append(stat)
    # state-writes RHS reads.
    for v in _vars_in_set_rhs(choice.state_writes or {}):
        if v not in seen and v in at_risk:
            seen.add(v)
            capture.append(v)
    return capture


def _capture_wrap(capture_vars: list[str], body: str) -> str:
    """Wrap ``body`` in ``<<capture $v1 $v2 ...>>…<</capture>>`` when
    ``capture_vars`` is non-empty; return ``body`` unchanged otherwise.

    Idempotent: if ``body`` is already wrapped in a ``<<capture>>`` whose
    variable list is a superset of ``capture_vars``, it is returned unchanged
    (no double-wrap). A bare ``<<capture>>`` that doesn't cover the requested
    vars is left in place and a *new* outer capture is added for the missing
    ones, so no requested variable is silently dropped.
    """
    if not capture_vars:
        return body
    # Normalise to $-prefixed names for consistent comparison.
    requested = {_ensure_dollar(v) for v in capture_vars}
    # Detect an existing <<capture ...>> wrapper around the whole body.
    m = re.match(r"^<<capture\s+(.+?)>>(.*)<</capture>>$", body, re.DOTALL)
    if m:
        existing = {f"${n}" for n in _VAR_REF_RE.findall(m.group(1))}
        if requested <= existing:
            return body  # already captured — idempotent no-op
        missing = [v for v in capture_vars if _ensure_dollar(v) not in existing]
        if missing:
            # Outer-wrap the already-captured body with the missing vars.
            vars_str = " ".join(missing)
            return f"<<capture {vars_str}>>{body}<</capture>>"
    vars_str = " ".join(capture_vars)
    return f"<<capture {vars_str}>>{body}<</capture>>"


def _ensure_dollar(v: str) -> str:
    """Return ``v`` with a leading ``$`` if it lacks one."""
    return v if v.startswith("$") else f"${v}"


def _render_choice_link(
    i: int, choice, passage_id: str, loop_vars: list[str] | None = None,
) -> str:
    """
    Render one choice as a SugarCube link / link macro.

    When ``loop_vars`` is a non-empty list of ``$var`` names active in an
    enclosing ``<<for>>`` loop, link bodies that *read* a loop variable are
    wrapped in ``<<capture $v>>…<</capture>>`` so each iteration's click
    handler sees its own value (docs/sugarcube2-analysis.md §3.9). With an
    empty/None ``loop_vars`` (the default — no SugarCube loop, the current
    harness behaviour), output is byte-identical to the pre-capture renderer.

    Idioms used (per SugarCube docs):
      • Plain navigation                → ``[[text|target]]`` wikilink.
      • State-setting navigation        → ``<<link "text" "target">>sets<</link>>``
        (SugarCube auto-navigates after body; no separate ``<<goto>>`` needed).
      • Skill-checked navigation        → ``<<link>>`` with inline ``<<if>>``
        branching to success/fail placeholders.
      • Gated (requires/blocks)         → wrapped in outer ``<<if expr>>…<</if>>``.
      • Linkreplace (choice.linkreplace) → ``<<linkreplace "text">>content<</linkreplace>>``
        where content is the state-writes rendered as visible text, with
        optional ``<<goto>>`` for navigation. Gate-wrapping and
        ``<<capture>>`` apply identically to the linkreplace form.
    """
    # TODO(macro-vocab): I1 — add a linkreplace dispatch branch in the body:
    # when choice.linkreplace is True, emit <<linkreplace "text">>content<</linkreplace>>
    # where content = state-writes rendered as visible text + optional <<goto>>
    # (P3 I1, P1 §4 G1). Gate-wrapping (_wrap_gates) and capture (_capture_wrap)
    # already operate on rendered strings and apply identically.
    placeholder = f"UNRESOLVED_choice{i}_{_safe_slug(choice.hint or choice.text)}"
    capture_vars = _capture_vars_for_choice(choice, loop_vars)

    # Skill check overrides normal rendering — target depends on roll.
    if choice.skill_check is not None:
        sc = choice.skill_check
        succ_ph = f"UNRESOLVED_choice{i}_success_{_safe_slug(sc.success_hint or 'pass')}"
        fail_ph = f"UNRESOLVED_choice{i}_fail_{_safe_slug(sc.fail_hint or 'fail')}"
        check = (
            f'<<link "{choice.text} (roll {sc.stat} vs DC {sc.dc})">>'
            f'<<if {sc.stat} gte {sc.dc}>><<goto "{succ_ph}">>'
            f'<<else>><<goto "{fail_ph}">><</if>><</link>>'
        )
        return _wrap_gates(_capture_wrap(capture_vars, check), choice)

    # State writes → SugarCube's two-arg <<link>> form: body runs, then auto-goto.
    if choice.state_writes:
        sets = " ".join(
            f"<<set {var} to {_format_sc_value(val)}>>"
            for var, val in choice.state_writes.items()
        )
        link = f'<<link "{choice.text}" "{placeholder}">>{sets}<</link>>'
        return _wrap_gates(_capture_wrap(capture_vars, link), choice)

    # Plain wikilink — most idiomatic SugarCube navigation. No deferred body,
    # so <<capture>> is never needed here (the target resolves at render time).
    link = f"[[{choice.text}|{placeholder}]]"
    return _wrap_gates(link, choice)


def _render_actions_block(choices: list, start_index: int = 0) -> str | None:
    """
    Render a hub's choice list as a SugarCube ``<<actions>>`` macro when every
    choice is a plain wikilink (no state writes, gates, or skill checks).

    ``<<actions>>`` hides each link after it has been clicked — the idiomatic
    SugarCube pattern for hub menus where every option is a one-shot.

    .. deprecated:: SugarCube v2.37.0
        ``<<actions>>`` was deprecated in SugarCube v2.37.0. The harness now
        uses :func:`_render_hub_links` (per-choice ``<<link>>`` with
        ``<<if not hasVisited()>>`` gating) as the default hub renderer. This
        function is retained only so older generated passages still validate
        and is no longer called by :func:`_render_passage_tw`. See
        docs/sugarcube2-analysis.md §3.1.

    Returns ``None`` when the choices can't all be expressed as wikilinks; the
    caller should fall back to per-choice rendering in that case.
    """
    if not choices:
        return None
    if not all(_is_plain_choice(c) for c in choices):
        return None
    items: list[str] = []
    for offset, choice in enumerate(choices):
        i = start_index + offset
        ph = f"UNRESOLVED_choice{i}_{_safe_slug(choice.hint or choice.text)}"
        items.append(f"[[{choice.text}|{ph}]]")
    return f"<<actions {' '.join(items)}>>"


def _render_hub_links(
    choices: list, start_index: int = 0, loop_vars: list[str] | None = None,
) -> list[str]:
    """
    Render a hub's choices as forward-compatible SugarCube ``<<link>>`` macros.

    Replaces the deprecated ``<<actions>>`` macro (SugarCube v2.37.0). Each
    one-shot hub option is rendered as a ``<<link>>`` that navigates on click
    and is wrapped in ``<<if not hasVisited("target")>>`` so it hides itself
    after the first visit — the same UX ``<<actions>>`` provided, without the
    deprecated macro. State-write / gated / skill-check choices fall through
    to the standard :func:`_render_choice_link` renderer, which already uses
    ``<<link>>`` and which honours ``loop_vars`` for ``<<capture>>`` wrapping.

    The plain hub links emitted here have *empty* ``<<link>>`` bodies (no
    deferred ``<<set>>``), so they never need ``<<capture>>`` themselves — the
    ``loop_vars`` is only forwarded to the non-plain fallthrough path.

    See docs/sugarcube2-analysis.md §3.1 (P1-Critical recommendation).
    """
    lines: list[str] = []
    for offset, choice in enumerate(choices):
        i = start_index + offset
        placeholder = f"UNRESOLVED_choice{i}_{_safe_slug(choice.hint or choice.text)}"
        if not _is_plain_choice(choice):
            # Non-plain choices already render as <<link>> via _render_choice_link.
            lines.append(_render_choice_link(i, choice, "", loop_vars=loop_vars))
            continue
        # One-shot hub link: hide once visited, then navigate.
        link = f'<<link "{choice.text}" "{placeholder}">><</link>>'
        gated = f'<<if not hasVisited("{placeholder}")>>{link}<</if>>'
        lines.append(gated)
    return lines


def _wrap_gates(rendered: str, choice) -> str:
    """Apply requires/blocks conditions around a rendered choice line."""
    conds: list[str] = []
    if choice.requires:
        conds.append(f"({choice.requires})")
    if choice.blocks:
        conds.append(f"!({choice.blocks})")
    if not conds:
        return rendered
    expr = " && ".join(conds)
    return f"<<if {expr}>>{rendered}<</if>>"


# TODO(achievements): I2 - add _render_achievement_block(achievements: list[ParsedAchievement]) -> str
# here, before _render_passage_tw (P3 section 2 I2). Emits one
# <<run memorize('achievements', Object.merge(recall('achievements', {}), {<id>: true}))>>
# line per earned ParsedAchievement. Returns "" when empty. Signature-only; P7 body.
#   def _render_achievement_block(achievements: list[ParsedAchievement]) -> str:
#       """Emit <<run memorize>> lines for earned achievements, or empty string."""
# See p3_interfaces.md section 2 I2, p1_research.md section 4B/3.

def _render_input_field(field: ParsedInputField) -> str:
    """Render one input macro from a ParsedInputField descriptor."""
    v = field.var
    if field.label:
        # Label on its own line, then the macro (Character Creator template idiom)
        pass  # label is added by _render_form_block, not here
    k = field.kind
    if k == "textbox":
        parts = [f'<<textbox "{v}" "{field.default if field.default is not None else ""}"']
        if field.autofocus:
            parts.append("autofocus")
        return " ".join(parts) + ">>"
    if k == "numberbox":
        parts = [f'<<numberbox "{v}" {field.default if field.default is not None else 0}']
        if field.autofocus:
            parts.append("autofocus")
        return " ".join(parts) + ">>"
    if k == "textarea":
        parts = [f'<<textarea "{v}" "{field.default if field.default is not None else ""}"']
        if field.autofocus:
            parts.append("autofocus")
        return " ".join(parts) + ">>"
    if k == "checkbox":
        parts = [f'<<checkbox "{v}" "{field.unchecked_value}" "{field.checked_value}"']
        if field.autocheck:
            parts.append("autocheck")
        elif field.checked:
            parts.append("checked")
        return " ".join(parts) + ">>"
    if k == "radiobutton":
        parts = [f'<<radiobutton "{v}" "{field.checked_value}"']
        if field.autocheck:
            parts.append("autocheck")
        elif field.checked:
            parts.append("checked")
        return " ".join(parts) + ">>"
    if k == "listbox":
        parts = [f'<<listbox "{v}"']
        if field.autoselect:
            parts.append("autoselect")
        lines = [" ".join(parts) + ">>"]
        for opt in field.options:
            opt_parts = [f'<<option "{opt.label}"']
            if opt.value and opt.value != opt.label:
                opt_parts.append(f'"{opt.value}"')
            if opt.selected:
                opt_parts.append("selected")
            lines.append(" ".join(opt_parts) + ">>")
        lines.append("<</listbox>>")
        return "\n".join(lines)
    if k == "cycle":
        parts = [f'<<cycle "{v}"']
        if field.once:
            parts.append("once")
        if field.autoselect:
            parts.append("autoselect")
        lines = [" ".join(parts) + ">>"]
        for opt in field.options:
            opt_parts = [f'<<option "{opt.label}"']
            if opt.value and opt.value != opt.label:
                opt_parts.append(f'"{opt.value}"')
            if opt.selected:
                opt_parts.append("selected")
            lines.append(" ".join(opt_parts) + ">>")
        lines.append("<</cycle>>")
        return "\n".join(lines)
    return ""


def _render_form_block(
    fields: list[ParsedInputField],
    choices: list,
    start_index: int = 0,
    loop_vars: list[str] | None = None,
) -> list[str]:
    """Render all form input fields followed by the submit choice link(s)."""
    if not fields:
        return []
    result: list[str] = []
    for field in fields:
        if field.label:
            result.append(field.label)
        result.append(_render_input_field(field))
        result.append("")  # blank separator between fields
    # Submit link(s) — reuses _render_choice_link with UNRESOLVED placeholder
    for i, choice in enumerate(choices):
        result.append(_render_choice_link(start_index + i, choice, "", loop_vars=loop_vars))
    return result



def _render_passage_tw(
    passage_id: str,
    arc_name: str,
    prose: str,
    choices: list,          # list[ParsedChoice]
    state_assigns: dict,
    media_slot_ids: list[str],
    location: str,
    characters: list[str],
    passage_type: str = "normal",
    entry_condition: str = "",
    fallback_passage: str = "",
    exits: dict[str, str] | None = None,
    event_odds: int = 100,
    dialogue_npc: str = "",
    loop_vars: list[str] | None = None,
    loop_collection: str = "",
    # TODO(achievements): I3 - add trailing kwarg before `) -> str:` (P3 section 3 I3):
    #   achievements: list[ParsedAchievement] | None = None,
    # Default None so existing callers unaffected. P7 normalizes None to [] and calls
    # _render_achievement_block. See p3_interfaces.md section 3 I3.
    inputs: list[ParsedInputField] | None = None,  # form passage input fields (P2 §5)
) -> str:
    """Render a passage to SugarCube twee source.

    ``loop_vars`` / ``loop_collection`` — when set, the choices are emitted
    inside a SugarCube ``<<for $v in ...>>`` loop over ``loop_collection``
    (e.g. ``$npcs``), and link bodies that read a loop variable are wrapped
    in ``<<capture $v>>…<</capture>>`` per §3.9. This is the one passage_type
    that genuinely generates a SugarCube-side loop; all other types iterate
    choices in Python and emit flat links (no capture needed).
    """
    exits = exits or {}
    inputs = list(inputs) if inputs else []
    lines: list[str] = []
    # Passage tags: arc + type. SugarCube hooks on tags (CSS `body.tag-ending`,
    # `Story.has()`-style checks) so type-as-tag lets authors style/route on it.
    tags = [arc_name] + (
        [passage_type] if passage_type and passage_type != "normal" else []
    )
    lines.append(f":: {passage_id} [{' '.join(tags)}]")

    # ── Harness metadata comment ──────────────────────────────────────────────
    meta_chars = ", ".join(characters) if characters else ""
    lines.append("<!-- harness:meta")
    if meta_chars:
        lines.append(f"characters: [{meta_chars}]")
    if location:
        lines.append(f"location: {location}")
    if passage_type != "normal":
        lines.append(f"type: {passage_type}")
    if entry_condition:
        lines.append(f"entry_condition: {entry_condition}")
    if dialogue_npc:
        lines.append(f"npc: {dialogue_npc}")
    if exits:
        lines.append(f"exits: {exits}")
    if passage_type == "random_event":
        lines.append(f"event_odds: {event_odds}")
    lines.append("-->")
    lines.append("")

    # ── Conditional entry gate ───────────────────────────────────────────────
    # Conditional passages re-route to fallback when entry_condition is false.
    if passage_type == "conditional" and entry_condition:
        fb = fallback_passage or "Start"
        lines.append(f"<<if not ({entry_condition})>><<goto \"{fb}\">><</if>>")
        lines.append("")

    # ── Random event roll ────────────────────────────────────────────────────
    if passage_type == "random_event":
        odds = max(1, min(int(event_odds), 100))
        lines.append(f"<<if random(1,100) gt {odds}>><<goto previous()>><</if>>")
        lines.append("")

    # ── Event one-shot guard ─────────────────────────────────────────────────
    if passage_type == "event":
        lines.append(f"<<if visited()>><<goto previous()>><</if>>")
        lines.append("")

    # ── Prose ────────────────────────────────────────────────────────────────
    # Widget and include passages render prose in their type-specific branch
    # below (widget wraps it in <<widget>>...<</widget>>; include emits it
    # verbatim), so skip the generic prose block to avoid duplication.
    if passage_type not in ("widget", "include"):
        lines.append(prose.strip())
        lines.append("")

    # ── Passage-level state assignments ──────────────────────────────────────
    for var, val in state_assigns.items():
        lines.append(f"<<set {var} to {_format_sc_value(val)}>>")
    if state_assigns:
        lines.append("")

    # TODO(achievements): _render_passage_tw body - after state-assigns, before
    # choices, emit achievement <<run memorize>> block (P3 section 8, P1 section 4B):
    #   achievements = achievements or []
    #   block = _render_achievement_block(achievements)
    #   if block:
    #       lines.append(block)
    #       lines.append("")
    # When empty/None (default), _render_achievement_block returns "" so no change.
    # See p3_interfaces.md section 2 I2 / section 3 I3, p1_research.md section 4B/7.

    # ── Choices / exits / random ─────────────────────────────────────────────
    # Placeholder format: UNRESOLVED_choice<N>_<safe_hint> so _resolve_parent_link
    # can map parent's Nth choice (choice_index) to its child unambiguously.
    if passage_type == "random" and choices:
        # weighted via repetition (SugarCube either() picks uniformly).
        weighted: list[str] = []
        for i, c in enumerate(choices):
            ph = f'"UNRESOLVED_choice{i}_{_safe_slug(c.hint or c.text)}"'
            weighted.extend([ph] * max(1, int(getattr(c, "weight", 1) or 1)))
        lines.append(f"<<goto either({', '.join(weighted)})>>")
        lines.append("")

    elif passage_type == "room":
        # Render named exits as gated links; choices act as actions performed in-room.
        for i, (direction, target) in enumerate(sorted(exits.items())):
            target_id = target or f"UNRESOLVED_choice{i}_{_safe_slug(direction)}"
            lines.append(f"[[{direction.title()}|{target_id}]]")
        for i, choice in enumerate(choices):
            lines.append(_render_choice_link(i + len(exits), choice, passage_id, loop_vars=loop_vars))
        if exits or choices:
            lines.append("")

    elif passage_type == "dialogue" and choices:
        # Dialogue choices loop back to this same passage unless hint contains "exit".
        for i, choice in enumerate(choices):
            is_exit = "exit" in (choice.hint or "").lower() or "leave" in (choice.text or "").lower()
            placeholder = (
                f"UNRESOLVED_choice{i}_{_safe_slug(choice.hint or choice.text)}"
                if is_exit else passage_id
            )
            sets = " ".join(
                f"<<set {var} to {_format_sc_value(val)}>>"
                for var, val in (choice.state_writes or {}).items()
            )
            link = f'<<link "{choice.text}">>{sets}<<goto "{placeholder}">><</link>>'
            # Wrap in <<capture>> when a loop variable the body reads is at risk.
            capture_vars = _capture_vars_for_choice(choice, loop_vars)
            lines.append(_wrap_gates(_capture_wrap(capture_vars, link), choice))
        lines.append("")

    elif passage_type == "ending":
        # Terminal — render any choices as restart links, but allow zero.
        for i, choice in enumerate(choices):
            lines.append(_render_choice_link(i, choice, passage_id, loop_vars=loop_vars))
        if choices:
            lines.append("")

    elif passage_type == "hub" and choices:
        # Hubs: every option ideally one-shot. Previously rendered via
        # <<actions>> (deprecated SugarCube v2.37.0); now uses per-choice
        # <<link>> wrapped in <<if not hasVisited()>> to reproduce the
        # hide-after-click behaviour without the deprecated macro.
        # See docs/sugarcube2-analysis.md §3.1.
        lines.extend(_render_hub_links(choices, loop_vars=loop_vars))
        lines.append("")

    elif passage_type == "widget":
        # Widget definition passage. SugarCube widgets are reusable markup
        # macros defined in a [widget]-tagged passage and called anywhere as
        # <<widget_name>>. The prose IS the widget body; we don't render
        # choices (widgets aren't navigated to). Caller is responsible for
        # wrapping the prose in <<widget "name">>...<</widget>> if needed;
        # if the prose already contains a <<widget>> macro we emit it raw.
        # See docs/sugarcube2-analysis.md §3.7, TEMPLATE_VERIFICATION_REPORT §2.3.
        if "<<widget" not in prose:
            # Auto-wrap: derive widget name from the passage slug suffix,
            # stripping the leading NN_ numeric prefix (e.g. "01_" in
            # "intro__01_stats_widget" → widget name "stats_widget").
            suffix = passage_id.rsplit("__", 1)[-1]
            widget_name = re.sub(r'^\d+_', '', suffix)
            lines.append(f'<<widget "{widget_name}">>')
            lines.append(prose.strip())
            lines.append("<</widget>>")
        else:
            lines.append(prose.strip())
        lines.append("")

    elif passage_type == "include":
        # Shared-content passage meant to be <<include>>d by other passages,
        # not navigated to directly (Title Page's "Menu Elements", Simple
        # Book's "Navigation", etc.). Render prose verbatim; ignore choices
        # since include passages have no player-facing navigation of their own.
        # See docs/sugarcube2-analysis.md §3.8, TEMPLATE_VERIFICATION_REPORT §2.3.
        lines.append(prose.strip())
        lines.append("")

    elif passage_type == "loop" and choices and loop_vars and loop_collection:
        # Render choices inside a genuine SugarCube <<for>> loop over an
        # arbitrary collection (e.g. one link per NPC in $npcs). Each link
        # that reads a loop variable is wrapped in <<capture $v>> so its
        # click handler sees the iteration value, not the final one
        # (docs/sugarcube2-analysis.md §3.9). When a single choice template
        # is given, it is repeated per element; otherwise the choice list
        # is emitted once per iteration (the LLM conventionally supplies a
        # single templated choice whose text/state reference $loopvar).
        loop_head = (
            f"<<for {loop_vars[0]} in {loop_collection}>>"
            if len(loop_vars) == 1
            else f"<<for _i, {loop_vars[0]} in {loop_collection}>>"
        )
        lines.append(loop_head)
        for i, choice in enumerate(choices):
            lines.append(_render_choice_link(i, choice, passage_id, loop_vars=loop_vars))
        lines.append("<</for>>")
        lines.append("")

    elif passage_type == "form":
        # Form passage: render input macros + a single submit <<link>>.
        # Inputs come from ModelOutput.inputs (P2 §5); submit reuses choices[0]
        # via the UNRESOLVED_choice0_* placeholder (P1 §2.8, Q1).
        lines.extend(_render_form_block(inputs, choices, start_index=0, loop_vars=loop_vars))
        lines.append("")

    else:
        # normal / conditional / event / random_event default rendering
        for i, choice in enumerate(choices):
            lines.append(_render_choice_link(i, choice, passage_id, loop_vars=loop_vars))
        if choices:
            lines.append("")

    # ── Media slots ──────────────────────────────────────────────────────────
    for slot_id in media_slot_ids:
        lines.append(f"<!-- media:{slot_id} -->")
    return "\n".join(lines) + "\n"


def _update_passage_links(content: str, link_map: dict[str, str]) -> str:
    """Replace UNRESOLVED_<hint> placeholders with real passage IDs."""
    def replacer(m):
        hint = m.group(1)
        target = link_map.get(f"UNRESOLVED_{hint}", f"UNRESOLVED_{hint}")
        return f"[[{m.group(2)}|{target}]]"
    return re.sub(r'\[\[([^\|]+)\|UNRESOLVED_([^\]]+)\]\]', lambda m: replacer(m), content)


def read_passage_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_passage_file(path: Path, content: str) -> None:
    from .project import _atomic_write_text
    _atomic_write_text(path, content)


# ── Link extraction ────────────────────────────────────────────────────────────

def extract_links(tw_content: str) -> list[str]:
    """Return all [[target]] and [[text|target]] link targets from a passage."""
    targets = []
    for m in re.finditer(r'\[\[(?:[^\|]+\|)?([^\]]+)\]\]', tw_content):
        targets.append(m.group(1))
    return targets


# ── Create passage ─────────────────────────────────────────────────────────────

def create_passage(
    p: ProjectPaths,
    arc_name: str,
    slug: str,
    output: ModelOutput,
    parent_id: str | None,
    branch_name: str = "main",
    choice_index: int | None = None,  # which choice of parent led here
    passage_type: str = "normal",     # see PASSAGE_TYPES in models
    entry_condition: str = "",
    fallback_passage: str = "",
    exits: dict[str, str] | None = None,
    event_odds: int = 100,
    dialogue_npc: str = "",
    skill_branch: str = "",           # "success"/"fail" if parent choice was a skill check
    loop_vars: list[str] | None = None,       # <<for>> loop vars (for "loop" passage_type)
    loop_collection: str = "",                # SugarCube collection expr to iterate
) -> tuple[str, StoryGraph]:
    """
    Commit a model-proposed passage to disk and update story.json.
    Returns (new_passage_id, updated_graph).

    Serialised per-project via :func:`_passage_lock` so concurrent commits
    cannot pick the same passage id / file path before either has saved.
    """
    with _passage_lock(p.root):
        graph = load_story(p)
        ensure_arc(p, arc_name)

        passage_id, tw_path = _unique_passage_identity(graph, p, arc_name, slug)

        # derive snapshot
        parent_snapshot: Snapshot | None = None
        if parent_id and parent_id in graph.passages:
            parent_snapshot = graph.passages[parent_id].snapshot
        new_snapshot = derive_snapshot(parent_snapshot, output)

        # compute delta from parent to new snapshot
        delta_base = parent_snapshot if parent_snapshot is not None else Snapshot()
        snapshot_delta = diff_snapshots(delta_base, new_snapshot)

        # Auto-summary fallback: covers human edits that clear the field, and
        # ModelOutputs assembled programmatically (e.g. in tests).
        if not output.summary.strip() and output.prose.strip():
            first = re.split(r'(?<=[.!?])\s', output.prose.strip())[0].strip()
            output.summary = first[:150]

        # detect characters present (from snapshot + new_characters)
        characters_in_scene = [c.id for c in new_snapshot.characters_present]

        # detect state writes
        state_writes = list(output.state.keys())
        # declare new state variables if not already known
        for var, val in output.state.items():
            if var not in graph.state_variables:
                from .models import StateVariable
                vtype = "bool" if isinstance(val, bool) else "int" if isinstance(val, int) else "str"
                graph.state_variables[var] = StateVariable(
                    type=vtype, default=None, declared_in=passage_id
                )

        # media slots
        slots = load_slots(p)
        media_slot_ids: list[str] = []
        for m in output.media:
            slot_id = f"slot_{uuid.uuid4().hex[:8]}"
            slots.slots[slot_id] = MediaSlot(
                passage=passage_id,
                keywords=m.keywords,
                type=m.type,
                status="pending",
                resolved_path=None,
                description=getattr(m, "description", ""),
            )
            media_slot_ids.append(slot_id)
        save_slots(p, slots)

        # write .tw file
        tw_content = _render_passage_tw(
            passage_id=passage_id,
            arc_name=arc_name,
            prose=output.prose,
            choices=output.choices,
            state_assigns=output.state,
            media_slot_ids=media_slot_ids,
            location="",
            characters=characters_in_scene,
            passage_type=passage_type,
            entry_condition=entry_condition,
            fallback_passage=fallback_passage,
            exits=exits or {},
            event_odds=event_odds,
            dialogue_npc=dialogue_npc,
            loop_vars=loop_vars,
            loop_collection=loop_collection,
            # TODO(achievements): thread achievements=output.achievements into
            # this _render_passage_tw call (P3 section 8, I3). Add:
            #   achievements=output.achievements,
            # See p3_interfaces.md section 3 I3, p2_data_structures.md section 4 D4.
            inputs=output.inputs,
        )
        rendered_state_reads = scan_state_reads(tw_content)
        # Merge input-macro target vars into state_writes (P1 §2.6, P3 §5.4).
        # scan_state_writes now recognizes the 7 input macros as writers; merge
        # its results so PassageEntry.state_writes is complete for form passages.
        rendered_state_writes = scan_state_writes(tw_content)
        for w in rendered_state_writes:
            if w not in state_writes:
                state_writes.append(w)
        write_passage_file(tw_path, tw_content)

        # build graph entry
        entry = PassageEntry(
            file=str(tw_path.relative_to(p.root)).replace("\\", "/"),
            arc=arc_name,
            parents=[parent_id] if parent_id else [],
            children=[],
            state_writes=state_writes,
            state_reads=rendered_state_reads,
            media_slots=media_slot_ids,
            location="",
            summary=output.summary,
            beats=list(output.beats),
            snapshot=new_snapshot,
            snapshot_delta=snapshot_delta,
            passage_type=passage_type,
            entry_condition=entry_condition,
            fallback_passage=fallback_passage,
            exits=exits or {},
            event_odds=event_odds,
            dialogue_npc=dialogue_npc,
        )
        graph.passages[passage_id] = entry

        # wire parent → child
        if parent_id and parent_id in graph.passages:
            if passage_id not in graph.passages[parent_id].children:
                graph.passages[parent_id].children.append(passage_id)
            # update parent .tw file link
            _resolve_parent_link(
                p, graph, parent_id, choice_index, passage_id,
                branch_label=skill_branch,
            )

        # set start passage if none
        if not graph.start_passage:
            graph.start_passage = passage_id

        # branch head update
        if branch_name not in graph.branches:
            diverges_at = parent_id if parent_id else None
            graph.branches[branch_name] = BranchEntry(head=passage_id, diverges_at=diverges_at)
        else:
            graph.branches[branch_name].head = passage_id

        save_story(p, graph)
        return passage_id, graph


def _resolve_parent_link(
    p: ProjectPaths,
    graph: StoryGraph,
    parent_id: str,
    choice_index: int | None,
    new_passage_id: str,
    branch_label: str = "",   # "success"/"fail" for skill-check branches, "" otherwise
) -> None:
    """Replace UNRESOLVED_choice<N>_* placeholder in parent .tw with new_passage_id.

    Handles:
      • [[text|UNRESOLVED_choice<N>_hint]]               — wikilink form
      • <<goto "UNRESOLVED_choice<N>_..." >>             — link macros / random
      • UNRESOLVED_choice<N>_success_*                   — skill check pass branch
      • UNRESOLVED_choice<N>_fail_*                      — skill check fail branch

    branch_label narrows the match for skill checks. Falls back to first
    UNRESOLVED_ placeholder if choice_index is None or no indexed match found
    (handles passages written before this scheme).
    """
    parent_entry = graph.passages[parent_id]
    tw_path = p.root / parent_entry.file
    if not tw_path.exists():
        return
    content = tw_path.read_text(encoding="utf-8")

    def _pick(matches: list[re.Match], capture_index: int) -> re.Match | None:
        if not matches:
            return None
        if choice_index is not None:
            if branch_label:
                # exact match: UNRESOLVED_choice<N>_<branch>_*
                exact = f"UNRESOLVED_choice{choice_index}_{branch_label}_"
                for m in matches:
                    if m.group(capture_index).startswith(exact):
                        return m
            prefix = f"UNRESOLVED_choice{choice_index}_"
            for m in matches:
                token = m.group(capture_index)
                if token.startswith(prefix):
                    # skip skill-check branches when no branch_label given
                    suffix = token[len(prefix):]
                    if not branch_label and (
                        suffix.startswith("success_") or suffix.startswith("fail_")
                    ):
                        continue
                    return m
        return matches[0]

    # ── Try standard [[text|UNRESOLVED_...]] links ─────────────────────────
    pattern1 = re.compile(r'(\[\[[^\|]+\|)(UNRESOLVED_[^\]]+)(\]\])')
    matches1 = list(pattern1.finditer(content))
    m1 = _pick(matches1, 2)
    if m1:
        new_content = (
            content[:m1.start()]
            + m1.group(1)
            + new_passage_id
            + m1.group(3)
            + content[m1.end():]
        )
        tw_path.write_text(new_content, encoding="utf-8")
        return

    # ── Try random either("UNRESOLVED_...") pattern ────────────────────────
    pattern2 = re.compile(r'"(UNRESOLVED_[^"]+)"')
    matches2 = list(pattern2.finditer(content))
    m2 = _pick(matches2, 1)
    if m2:
        new_content = (
            content[:m2.start()]
            + f'"{new_passage_id}"'
            + content[m2.end():]
        )
        tw_path.write_text(new_content, encoding="utf-8")


def _repoint_links_to_deleted(content: str, target_id: str) -> str:
    """Rewrite a parent's links to a deleted passage into UNRESOLVED_ markers.

    Covers ``[[text|target]]`` wikilinks and ``<<goto "target">>`` macros so the
    validator flags them (unresolved_link) and the author re-points or removes
    them, rather than the link silently dangling.
    """
    marker = f"UNRESOLVED_deleted_{_safe_slug(target_id)}"
    # [[text|target]]  and  [[target]]
    content = re.sub(
        r'\[\[([^\|\]]+)\|' + re.escape(target_id) + r'\]\]',
        rf'[[\1|{marker}]]', content,
    )
    content = re.sub(
        r'\[\[' + re.escape(target_id) + r'\]\]',
        f'[[{marker}]]', content,
    )
    # <<goto "target">> / either("target")
    content = content.replace(f'"{target_id}"', f'"{marker}"')
    return content


def delete_passage(p: ProjectPaths, passage_id: str) -> tuple[bool, str]:
    """Delete a passage: remove its file + manifest entry and clean up all
    references (parent children/links, child parents, media slots, branches,
    start passage). Children are NOT deleted — they may become orphans, which
    validation then surfaces. Returns (ok, message).

    Serialised per-project via :func:`_passage_lock`.
    """
    with _passage_lock(p.root):
        graph = load_story(p)
        entry = graph.passages.get(passage_id)
        if entry is None:
            return False, f"Passage {passage_id!r} not found."

        # ── Detach from parents: drop child ref + repoint their .tw links ──────
        for parent_id in entry.parents:
            parent = graph.passages.get(parent_id)
            if not parent:
                continue
            if passage_id in parent.children:
                parent.children.remove(passage_id)
            ptw = p.root / parent.file
            if ptw.exists():
                content = ptw.read_text(encoding="utf-8")
                rewritten = _repoint_links_to_deleted(content, passage_id)
                if rewritten != content:
                    ptw.write_text(rewritten, encoding="utf-8")

        # ── Detach from children: drop parent ref ─────────────────────────────
        for child_id in entry.children:
            child = graph.passages.get(child_id)
            if child and passage_id in child.parents:
                child.parents.remove(passage_id)

        # ── Drop media slots owned by this passage ────────────────────────────
        slots = load_slots(p)
        removed_slots = [
            sid for sid in entry.media_slots if sid in slots.slots
        ]
        for sid in removed_slots:
            del slots.slots[sid]
        # also catch any slot whose passage points here but wasn't manifested
        for sid, slot in list(slots.slots.items()):
            if slot.passage == passage_id:
                del slots.slots[sid]
        save_slots(p, slots)

        # ── Branch heads / divergence pointing at this passage ────────────────
        fallback = entry.parents[0] if entry.parents else ""
        for bname, branch in list(graph.branches.items()):
            if branch.diverges_at == passage_id:
                branch.diverges_at = None
            if branch.head == passage_id:
                branch.head = fallback or graph.start_passage

        # ── Start passage ─────────────────────────────────────────────────────
        if graph.start_passage == passage_id:
            remaining = [pid for pid in graph.passages if pid != passage_id]
            graph.start_passage = (
                entry.children[0] if entry.children and entry.children[0] in graph.passages
                else (remaining[0] if remaining else "")
            )

        # ── Remove the passage + its file ─────────────────────────────────────
        tw_path = p.root / entry.file
        del graph.passages[passage_id]
        save_story(p, graph)
        if tw_path.exists():
            tw_path.unlink()

        return True, f"Deleted {passage_id!r} (and {len(removed_slots)} media slot(s))."


# ── Manifest sync ──────────────────────────────────────────────────────────────

def sync_manifest(p: ProjectPaths) -> tuple[list[str], list[str]]:
    """
    Ensure story.json and on-disk passage files (.tw + .twee) are in sync.
    Returns (missing_from_json, missing_from_disk).
    """
    from .compile import collect_passage_files
    graph = load_story(p)

    on_disk: set[str] = {
        f.relative_to(p.root).as_posix() for f in collect_passage_files(p)
    }
    in_json: set[str] = {e.file for e in graph.passages.values()}

    missing_from_json = sorted(on_disk - in_json)
    missing_from_disk = sorted(in_json - on_disk)
    return missing_from_json, missing_from_disk


# ── Read state reads from passage ─────────────────────────────────────────────

def scan_state_reads(tw_content: str) -> list[str]:
    """Extract $variable references that are reads (not inside <<set ...>>).

    Covers the SugarCube expression contexts the harness emits and that the
    validator needs to reason about (docs/sugarcube2-analysis.md §3.12-3.14):

    * Naked variable interpolation in prose — ``$gold`` auto-interpolates.
    * ``<<if $var ...>>`` / ``<<elseif $var ...>>`` conditions.
    * ``<<print $expr>>`` / ``<<= $expr>>`` output macros.
    * Link setters — ``[[Text|Target][$var to val]]`` and the
      ``<<link \"Text\" \"Target\">><<set ...>><</link>>`` body.

    ``<<set $var to ...>>`` right-hand side *can* read other variables
    (``<<set $b to $a + 1>>``); those RHS reads are now included too. The
    earlier implementation stripped whole ``<<set>>`` blocks, which masked
    reads like ``$a`` in that example and left them undeclared-undetected.
    """
    reads: set[str] = set()

    # 1) Strip the LHS of every <<set $var to/= ...>> so its *target* variable
    #    is not counted as a read, but keep the RHS for read scanning. This
    #    catches `<<set $b to $a + 1>>` reading $a.
    def _strip_set_lhs(m: re.Match) -> str:
        return m.group(2)  # keep only the RHS after `to`/`=`
    cleaned = re.sub(
        r'<<set\s+\$(\w+)\s+(?:to|=)\s*([^>]*)>>',
        _strip_set_lhs,
        tw_content,
    )

    # Strip the quoted first argument of input macros so their receiver names
    # (e.g. the "$name" in <<textbox "$name" "default">>) are NOT counted as
    # reads (P3 §6.2, P1 §2.7). This prevents form field target vars from
    # being misclassified as reads → false undeclared_state_var errors.
    _INPUT_MACRO_RE = re.compile(
        r'<<(?:' + '|'.join(INPUT_MACRO_KINDS) + r')\s+"\$([a-zA-Z_]\w*)"',
    )
    cleaned = _INPUT_MACRO_RE.sub('', cleaned)

    # 2) Collect every $var token remaining. This naturally includes:
    #    - naked prose interpolation ($name in text)
    #    - <<if>>/<<elseif>> condition variables
    #    - <<print>>/<<=>> expression variables
    #    - link setter expressions [[..][..][$x ..]]
    #    - RHS of <<set>> (kept above)
    for m in re.finditer(r'\$([a-zA-Z_]\w*)', cleaned):
        reads.add(f"${m.group(1)}")
    return sorted(reads)


def scan_state_writes(tw_content: str) -> list[str]:
    """Extract $variables assigned via <<set $var to ...>> / <<set $var = ...>>."""
    writes = set()
    for m in re.finditer(r'<<set\s+\$(\w+)\s*(?:to\b|=)', tw_content):
        writes.add(f"${m.group(1)}")
    # Also recognize the 7 input macros as writers of their quoted target var
    # (P3 §6.1, P1 §2.7). Input macros like <<textbox "$name" "default">> write
    # to $name in real time but are NOT matched by the <<set>> regex above.
    _INPUT_MACRO_WRITE_RE = re.compile(
        r'<<(?:' + '|'.join(INPUT_MACRO_KINDS) + r')\s+"\$([a-zA-Z_]\w*)"',
    )
    for m in _INPUT_MACRO_WRITE_RE.finditer(tw_content):
        writes.add(f"${m.group(1)}")
    return sorted(writes)


# ── Rebuild story.json from disk ───────────────────────────────────────────────

_TW_HEADER_RE = re.compile(r'^::\s*(\S+)(?:\s*\[([^\]]*)\])?', re.MULTILINE)
_MEDIA_SLOT_RE = re.compile(r'<!-- media:(slot_[a-zA-Z0-9_]+) -->')


def _parse_tw_header(content: str) -> tuple[str, list[str]]:
    """Return (passage_id, tags) from the first ``:: id [tags]`` line, or ("", [])."""
    m = _TW_HEADER_RE.search(content)
    if not m:
        return "", []
    pid = m.group(1).strip()
    tags = (m.group(2) or "").split()
    return pid, tags


def _parse_meta_block(content: str) -> dict:
    """Parse the ``<!-- harness:meta ... -->`` comment into a dict.

    Recognises: characters ([a, b]), location, type, entry_condition, npc,
    exits ({'north': 'pid'}), event_odds. Tolerates a missing block.
    """
    m = re.search(r'<!--\s*harness:meta\s*(.*?)-->', content, re.DOTALL)
    meta: dict = {}
    if not m:
        return meta
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if not val:
            continue
        if key == "characters":
            inner = val.strip("[]")
            meta["characters"] = [c.strip() for c in inner.split(",") if c.strip()]
        elif key == "exits":
            try:
                import ast
                parsed = ast.literal_eval(val)
                if isinstance(parsed, dict):
                    meta["exits"] = {str(k): str(v) for k, v in parsed.items()}
            except (ValueError, SyntaxError):
                pass
        elif key == "event_odds":
            try:
                meta["event_odds"] = int(val)
            except ValueError:
                pass
        else:
            meta[key] = val
    return meta


def rebuild_story(p: ProjectPaths, *, preserve_meta: bool = True) -> tuple[StoryGraph, list[str]]:
    """Reconstruct the story graph from the .tw files on disk.

    Structural fields (file, arc, children, parents, state reads/writes, media
    slots, type-specific fields) are taken as ground truth from disk — this is
    what repairs manifest drift, duplicate file ownership, and stale links.

    Authorial fields that don't live in the .tw (summary, beats, plan_beats,
    snapshot) plus graph-level metadata (state-variable defaults, branches,
    plan, arcs, start_passage) are preserved from the existing story.json when
    ``preserve_meta`` is set and the passage/var still exists.

    Returns (graph, report) where report is a list of human-readable notes.
    Does not write — call :func:`rebuild_and_save` to persist.
    """
    from .compile import collect_passage_files
    from .models import StateVariable

    old = load_story(p) if p.story_json.exists() else StoryGraph()
    report: list[str] = []
    graph = StoryGraph(version=old.version)

    for tw_path in collect_passage_files(p):
        content = tw_path.read_text(encoding="utf-8")
        pid, _tags = _parse_tw_header(content)
        rel = tw_path.relative_to(p.root).as_posix()
        if not pid:
            report.append(f"skipped {rel}: no '::' passage header found")
            continue
        if pid in graph.passages:
            report.append(
                f"duplicate id {pid!r}: {rel} overrides {graph.passages[pid].file}"
            )
        meta = _parse_meta_block(content)
        try:
            arc = tw_path.relative_to(p.arcs_dir).parts[0]
        except (ValueError, IndexError):
            arc = meta.get("arc", "")

        entry = PassageEntry(
            file=rel,
            arc=arc,
            state_writes=scan_state_writes(content),
            state_reads=scan_state_reads(content),
            media_slots=_MEDIA_SLOT_RE.findall(content),
            location=meta.get("location", ""),
            passage_type=meta.get("type", "normal"),
            entry_condition=meta.get("entry_condition", ""),
            fallback_passage="",
            exits=meta.get("exits", {}),
            event_odds=meta.get("event_odds", 100),
            dialogue_npc=meta.get("npc", ""),
        )

        if preserve_meta and pid in old.passages:
            o = old.passages[pid]
            entry.summary = o.summary
            entry.beats = list(o.beats)
            entry.plan_beats = list(o.plan_beats)
            entry.snapshot = o.snapshot
            entry.location = entry.location or o.location
            entry.fallback_passage = o.fallback_passage

        graph.passages[pid] = entry

    # ── Resolve children from links + gotos, then derive parents ──────────────
    allowed_special = {"Start", "previous()"}
    for pid, entry in graph.passages.items():
        content = (p.root / entry.file).read_text(encoding="utf-8")
        targets: list[str] = []
        for t in extract_links(content) + re.findall(r'<<goto\s+["\']([^"\']+)["\']\s*>>', content):
            if (
                t in graph.passages and t != pid
                and t not in allowed_special and t not in targets
            ):
                targets.append(t)
        entry.children = targets

    for pid, entry in graph.passages.items():
        for child in entry.children:
            parents = graph.passages[child].parents
            if pid not in parents:
                parents.append(pid)

    # ── Start passage ─────────────────────────────────────────────────────────
    if old.start_passage in graph.passages:
        graph.start_passage = old.start_passage
    else:
        rootless = [pid for pid, e in graph.passages.items() if not e.parents]
        graph.start_passage = sorted(rootless)[0] if rootless else (
            sorted(graph.passages)[0] if graph.passages else ""
        )
        if old.start_passage and old.start_passage != graph.start_passage:
            report.append(
                f"start_passage {old.start_passage!r} gone; inferred {graph.start_passage!r}"
            )

    # ── State variables: preserve declarations for vars still used; add new ────
    used_vars: set[str] = set()
    for e in graph.passages.values():
        used_vars.update(e.state_writes)
        used_vars.update(e.state_reads)
    for var in sorted(used_vars):
        if var in old.state_variables:
            graph.state_variables[var] = old.state_variables[var]
        else:
            graph.state_variables[var] = StateVariable(type="str", default=None)
            report.append(f"discovered undeclared variable {var!r} (no default)")

    # ── Branches: keep those whose head still exists ──────────────────────────
    for name, br in old.branches.items():
        if br.head in graph.passages:
            graph.branches[name] = br
        else:
            report.append(f"dropped branch {name!r}: head {br.head!r} no longer exists")

    # ── Plan / arcs are pure author metadata — carry forward verbatim ─────────
    graph.plan = old.plan
    graph.arcs = old.arcs

    return graph, report


def rebuild_and_save(p: ProjectPaths, *, preserve_meta: bool = True) -> list[str]:
    """Rebuild the graph from disk and persist it. Returns the change report."""
    with _passage_lock(p.root):
        graph, report = rebuild_story(p, preserve_meta=preserve_meta)
        save_story(p, graph)
    return report

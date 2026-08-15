"""Pure, deterministic SugarCube rendering.

This module performs no project I/O, model calls, or mutable configuration reads.
"""
from __future__ import annotations

import json
import re
import html

from ..models import ParsedChoice, ParsedInputField, ParsedInputOption
from .contracts import (
    CompileArtifact,
    Diagnostic,
    DiagnosticLevel,
    DiagnosticOwner,
    DiagnosticStage,
    EntityReferencePart,
    NarrativeBlockKind,
    PassageDraft,
    StateEffect,
    StateOperation,
    StateReferencePart,
    TextPart,
)


COMPILER_VERSION = "generation-compiler-v2"


class _SugarCubeExpression(str):
    """Compiler-owned expression marker; model-authored strings stay quoted."""


def _safe_slug(s: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', (s or "").lower())[:40] or "x"


def _format_sc_value(val) -> str:
    if isinstance(val, _SugarCubeExpression):
        return str(val)
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
        and is no longer called by :func:`render_passage_tw`. See
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



def render_passage_tw(
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
    state_effect_lines: list[str] | None = None,
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
    state_effect_lines = list(state_effect_lines) if state_effect_lines else []
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
    if state_effect_lines:
        lines.extend(state_effect_lines)
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
        lines.append(
            f"<<set _harnessRoute to either({', '.join(weighted)})>>"
            "<<goto _harnessRoute>>"
        )
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
            is_exit = (
                (choice.hint or "").startswith("HARNESS_EXIT")
                or "exit" in (choice.hint or "").lower()
                or "leave" in (choice.text or "").lower()
            )
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
            f"<<for {loop_vars[0]} range {loop_collection}>>"
            if len(loop_vars) == 1
            else f"<<for _i, {loop_vars[0]} range {loop_collection}>>"
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




def compile_passage_draft(
    draft: PassageDraft,
    *,
    passage_id: str,
    arc_name: str,
    media_slot_ids: tuple[str, ...] = (),
) -> CompileArtifact:
    """Compile a validated typed draft without project or network access."""
    plan = draft.plan
    narrative_by_id = {slot.slot_id: slot for slot in draft.fill.narrative}
    prose_blocks: list[str] = []
    for planned in plan.narrative_slots:
        filled = narrative_by_id[planned.id]
        text = "".join(_render_inline_part(part) for part in filled.parts)
        if planned.kind == NarrativeBlockKind.DIALOGUE:
            prose_blocks.append(f'{_escape_model_text(planned.speaker)}: "{text}"')
        elif planned.kind == NarrativeBlockKind.THOUGHT:
            prose_blocks.append(f"//{text}//")
        else:
            prose_blocks.append(text)

    choice_copy = {slot.slot_id: slot for slot in draft.fill.choices}
    choices: list[ParsedChoice] = []
    choice_label_tokens: dict[str, str] = {}
    for index, planned in enumerate(plan.choice_slots):
        copy = choice_copy[planned.id]
        label_token = f"HARNESS_CHOICE_LABEL_{index}"
        choice_label_tokens[label_token] = copy.text
        writes = {}
        for effect in planned.effects:
            target = f"${effect.target}"
            effect_value = (
                _SugarCubeExpression(f"${effect.source}")
                if effect.source else effect.value
            )
            if effect.operation == StateOperation.SET:
                writes[target] = effect_value
            elif effect.operation == StateOperation.ADD:
                writes[target] = _SugarCubeExpression(
                    f"{target} + {_format_sc_value(effect_value)}"
                )
            elif effect.operation == StateOperation.SUBTRACT:
                writes[target] = _SugarCubeExpression(
                    f"{target} - {_format_sc_value(effect_value)}"
                )
            else:
                writes[target] = _SugarCubeExpression(f"not {target}")
        requires = " and ".join(_render_condition(item) for item in planned.conditions)
        choices.append(ParsedChoice(
            # Render with a parser-safe token first. After trusted destinations
            # are resolved, the token is replaced by a SugarCube string
            # expression so punctuation is displayed exactly without granting
            # model copy markup or macro authority.
            text=label_token,
            hint=(
                f"HARNESS_EXIT {copy.hint}"
                if plan.passage_mode.value == "dialogue_loop" and planned.destination
                else copy.hint
            ),
            requires=requires,
            state_writes=writes,
            weight=planned.weight,
        ))

    passage_mode = (
        "dialogue"
        if plan.passage_mode.value == "dialogue_loop"
        else plan.passage_mode.value
    )
    entry_condition = " and ".join(_render_condition(item) for item in plan.eligibility)
    source = render_passage_tw(
        passage_id=passage_id,
        arc_name=arc_name,
        prose="\n\n".join(prose_blocks),
        choices=choices,
        state_assigns={},
        media_slot_ids=list(media_slot_ids),
        location="",
        characters=[],
        passage_type=passage_mode,
        entry_condition=entry_condition,
        fallback_passage=plan.fallback_passage,
        exits={route.label: route.destination for route in plan.exits},
        event_odds=plan.event_odds,
        loop_vars=(
            [f"${plan.loop_binding.variable}"] if plan.loop_binding else None
        ),
        loop_collection=(
            f"${plan.loop_binding.collection}" if plan.loop_binding else ""
        ),
        inputs=[
            ParsedInputField(
                kind=field.kind,
                var=f"${field.id}",
                label=field.label,
                default=field.default,
                unchecked_value=field.unchecked_value,
                checked_value=field.checked_value,
                options=[
                    ParsedInputOption(
                        label=option.label,
                        value=option.value,
                        selected=option.selected,
                    )
                    for option in field.options
                ],
                autofocus=field.autofocus,
                autocheck=field.autocheck,
                checked=field.checked,
                once=field.once,
                autoselect=field.autoselect,
            )
            for field in plan.form_fields
        ],
        state_effect_lines=[
            _render_effect(effect) for effect in draft.resolved_effects
        ],
    )
    source = _apply_trusted_destinations(
        source,
        plan.choice_slots,
        index_offset=(len(plan.exits) if plan.passage_mode.value == "room" else 0),
        blank_destination=(
            passage_id
            if plan.passage_mode.value in {"dialogue_loop", "loop", "room"}
            else ""
        ),
    )
    source = _apply_safe_choice_labels(source, choice_label_tokens)
    if plan.passage_mode.value == "ending":
        for index, planned in enumerate(plan.choice_slots):
            if not planned.restart:
                continue
            copy = choice_copy[planned.id]
            source = source.replace(
                f'<<link {json.dumps(copy.text, ensure_ascii=False)} '
                f'{json.dumps(planned.destination, ensure_ascii=False)}>><</link>>',
                f'<<link {json.dumps(copy.text, ensure_ascii=False)}>>'
                f'<<run UI.restart()>><</link>>',
            )

    diagnostics: list[Diagnostic] = []
    unresolved = sorted(set(re.findall(r"UNRESOLVED_[A-Za-z0-9_]+", source)))
    if unresolved:
        diagnostics.append(Diagnostic(
            code="unresolved_link_target",
            level=DiagnosticLevel.WARNING,
            stage=DiagnosticStage.COMPILE,
            owner=DiagnosticOwner.PLAN,
            message=f"{len(unresolved)} link target(s) remain unresolved",
            path=("plan", "choice_slots"),
        ))

    reads = list(plan.allowed_state_refs)
    for condition in (*plan.eligibility, *(c for choice in plan.choice_slots for c in choice.conditions)):
        if condition.target not in reads:
            reads.append(condition.target)
    choice_effects = tuple(
        effect for choice in plan.choice_slots for effect in choice.effects
    )
    form_effects = tuple(
        StateEffect(
            component_id=f"form_{field.id}",
            target=field.id,
            operation=StateOperation.SET,
            value=field.default,
        )
        for field in plan.form_fields
    )
    return CompileArtifact(
        twee_source=source,
        state_reads=tuple(reads),
        state_writes=(*draft.resolved_effects, *choice_effects, *form_effects),
        link_targets=(
            *(slot.destination for slot in plan.choice_slots if slot.destination),
            *(route.destination for route in plan.exits),
        ),
        media_placeholders=media_slot_ids,
        diagnostics=tuple(diagnostics),
        compiler_version=COMPILER_VERSION,
        source_draft_fingerprint=draft.fingerprint(),
    )


def _render_inline_part(part: TextPart | StateReferencePart | EntityReferencePart) -> str:
    if isinstance(part, TextPart):
        return _escape_model_text(part.text)
    if isinstance(part, StateReferencePart):
        return f"<<print ${part.target}>>"
    return f'<<print setup.entities["{part.target}"]>>'


def _escape_model_text(value: str) -> str:
    """Keep model-owned copy out of SugarCube, HTML, and macro syntax."""
    escaped = html.escape(value, quote=True)
    return (
        escaped.replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("\\", "&#92;")
        # SugarCube wikifies $variables and _temporaryVariables even in prose.
        # Entity encoding preserves their visible spelling while preventing
        # model-owned copy from reading state outside typed reference parts.
        .replace("$", "&#36;")
        .replace("_", "&#95;")
    )


def _apply_safe_choice_labels(source: str, labels: dict[str, str]) -> str:
    """Replace compiler-only label tokens with inert SugarCube string values.

    HTML entities are correct for prose but SugarCube's link parser treats
    them as literal label text.  Macro string arguments preserve author-visible
    punctuation while JSON quoting prevents quotes, brackets, pipes, and macro
    markers in model copy from becoming executable markup.
    """
    for token, text in labels.items():
        rendered = json.dumps(text, ensure_ascii=False)
        # Existing <<link>> renderers quote the compiler token. Replacing the
        # complete quoted token retains the macro body and trusted target.
        source = source.replace(json.dumps(token), rendered)
        # Plain choices are initially wikilinks. Convert them to <<link>> so the
        # label is evaluated as a string rather than parsed as wiki markup.
        source = re.sub(
            rf"\[\[{re.escape(token)}\|([^\]\r\n]+)\]\]",
            lambda match, label=rendered: (
                f"<<link {label} {json.dumps(match.group(1), ensure_ascii=False)}>><</link>>"
            ),
            source,
        )
    return source


def _render_condition(condition) -> str:
    target = f"${condition.target}"
    if condition.operation == "truthy":
        return target
    if condition.operation == "falsy":
        return f"not ({target})"
    operators = {"eq": "is", "ne": "isnot", "gt": "gt", "gte": "gte", "lt": "lt", "lte": "lte"}
    return f"{target} {operators[condition.operation]} {_format_sc_value(condition.value)}"


def _render_effect(effect) -> str:
    target = f"${effect.target}"
    value = _format_sc_value(
        _SugarCubeExpression(f"${effect.source}")
        if effect.source else effect.value
    )
    if effect.operation == StateOperation.ADD:
        return f"<<set {target} += {value}>>"
    if effect.operation == StateOperation.SUBTRACT:
        return f"<<set {target} -= {value}>>"
    if effect.operation == StateOperation.TOGGLE:
        return f"<<set {target} to not {target}>>"
    return f"<<set {target} to {value}>>"


def _apply_trusted_destinations(
    source: str,
    choice_slots,
    *,
    index_offset: int = 0,
    blank_destination: str = "",
) -> str:
    for index, slot in enumerate(choice_slots):
        destination = slot.destination or blank_destination
        if not destination:
            continue
        source = re.sub(
            rf"UNRESOLVED_choice{index + index_offset}_[A-Za-z0-9_]+",
            lambda _match, destination=destination: destination,
            source,
        )
    return source


__all__ = ["COMPILER_VERSION", "compile_passage_draft", "render_passage_tw"]

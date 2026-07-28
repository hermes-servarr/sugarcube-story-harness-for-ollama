"""Output parsing — delimited PROSE/CHOICES/... and JSON-mode responses.

All JSON salvage routes through :func:`parse_json_object` so fence/preamble
handling lives in one place.
"""
from __future__ import annotations
import json
import re
from typing import Any

from pydantic import ValidationError

from .models import (
    CharacterDelta,
    ExtractedEntities,
    ModelOutput,
    ParsedCharacter,
    ParsedChoice,
    ParsedLore,
    ParsedMediaSlot,
    SkillCheck,
)


# ── Delimited-section parser ─────────────────────────────────────────────────

# Matches section headers whether the model puts content on the same line or not.
# TODO(timed-narrative): add `|TIMED` to the _SECTION_RE alternation below
# (P3 §4.1, P1 §3.4). TIMED is an OPTIONAL section — do NOT add it to
# REQUIRED_SECTIONS (most passages are not timed). Exact change: append
# `|TIMED` to the last alternation group, before the closing `)`:
#   r'CHARACTERS_PRESENT|CHARACTERS_EXIT|CHARACTER_STATUS|SUMMARY|BEATS|TIMED)\s*:\s*',
# See p3_interfaces.md §4.1, p1_research.md §3.4.
_SECTION_RE = re.compile(
    r'^(PROSE|CHOICES|STATE|MEDIA|NEW_CHARACTERS|NEW_LORE|THREADS_OPEN|'
    r'THREADS_CLOSE|WORLD_STATE_ADD|WORLD_STATE_REMOVE|'
    r'CHARACTERS_PRESENT|CHARACTERS_EXIT|CHARACTER_STATUS|SUMMARY|BEATS)\s*:\s*',
    re.MULTILINE | re.IGNORECASE,
)

REQUIRED_SECTIONS = {"PROSE", "CHOICES", "SUMMARY"}

# Matches a state assignment anywhere (used to rescue mis-placed STATE lines)
_STATE_ASSIGN_RE = re.compile(r'\$(\w+)\s*=\s*(.+?)(?:\s*[→>|].*)?$')

_TEMPLATE_BRACE_RE = re.compile(r'^\{.+\}$')
_TEMPLATE_PAREN_RE = re.compile(r'^\([a-z_ /-]+\)$', re.IGNORECASE)

# Phrases that appear verbatim when a small model echoes the format spec
_TEMPLATE_PHRASES: frozenset[str] = frozenset({
    "write the passage prose here",
    "this is what the player reads",
    "one paragraph describing this new character",
    "one paragraph about this new location, faction, or item",
    "one paragraph about this location, faction, or item",
    "one paragraph about this entry",
    "one sentence describing what happens in this passage",
    "brief hint about where this leads",
    "brief hint about destination",
    "first choice text",
    "second choice text",
    "a new plot thread",
    "a resolved plot thread",
    "a new fact about the world state",
    "a world fact that is no longer true",
    "character_id",
    "lowercase_id",
    "category/entry_id",
    "category/id",
    "character id",
})

_ANNOTATION_KEYS = frozenset({
    "requires", "if", "blocks", "unless", "sets", "do",
    "weight", "w", "skill", "check", "dc",
})

_SKILL_RE = re.compile(
    r'\$?(\w+)\s*(?:>=|gte|≥|>=?|>|gt)\s*(\d+)',
    re.IGNORECASE,
)


def _split_sections(raw: str) -> dict[str, str]:
    """Split raw model output on section headers (case-insensitive, inline or newline)."""
    sections: dict[str, str] = {}
    parts = _SECTION_RE.split(raw)
    i = 1
    while i + 1 < len(parts):
        name = parts[i].strip().upper()
        content = parts[i + 1].strip()
        sections[name] = content
        i += 2
    return sections


def _is_template(s: str) -> bool:
    """True if the string looks like an un-filled template placeholder."""
    s = s.strip()
    sl = s.lower().rstrip(".")
    return (
        bool(_TEMPLATE_BRACE_RE.match(s))
        or bool(_TEMPLATE_PAREN_RE.match(s))
        or sl in _TEMPLATE_PHRASES
        or bool(re.match(r'^\((?:omit|skip|none of|write the|one |include only)', s, re.I))
    )


def _strip_bullet(line: str) -> str:
    """Remove leading list markers: -, *, •, ·, >, 1., 1) …"""
    return re.sub(r'^[\s]*[-*•·>]|^\s*\d+[.)]\s*', '', line).strip()


def _coerce_value(val_str: str):
    """Best-effort coerce a string to bool/int/str."""
    val_str = val_str.strip().strip("\"'").rstrip(";,")
    low = val_str.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    return val_str


def _looks_like_annotation(s: str) -> bool:
    """True if string looks like a `key:value` choice annotation, not a hint."""
    if ":" not in s:
        return False
    head = s.split(":", 1)[0].strip().lower()
    return head in _ANNOTATION_KEYS


def _apply_choice_annotation(choice: ParsedChoice, ann: str) -> None:
    """Parse one `key:value` annotation and mutate choice in-place."""
    if ":" not in ann:
        return
    key, val = ann.split(":", 1)
    key = key.strip().lower()
    val = val.strip()
    if not val:
        return
    if key in ("requires", "if"):
        choice.requires = val
    elif key in ("blocks", "unless"):
        choice.blocks = val
    elif key in ("sets", "do"):
        for assign in re.split(r'[;,]', val):
            m = re.match(r'\$?(\w+)\s*=\s*(.+)', assign.strip())
            if m:
                choice.state_writes[f"${m.group(1)}"] = _coerce_value(m.group(2))
    elif key in ("weight", "w"):
        try:
            choice.weight = max(1, int(val))
        except ValueError:
            pass
    elif key in ("skill", "check"):
        m = _SKILL_RE.search(val)
        if m:
            choice.skill_check = SkillCheck(
                stat=f"${m.group(1)}",
                dc=int(m.group(2)),
            )


def _parse_character_delta(line: str, *, is_exit: bool = False) -> CharacterDelta | None:
    """Parse one pipe-delimited character delta line.

    Present/status form: ``id | status | knows; knows; ... | relationship``
    Exit form:           ``id | last known location/state``

    All fields after ``id`` are optional. ``knows`` is a semicolon-separated
    list. Returns ``None`` for empty/template lines or invalid ids.
    """
    line = _strip_bullet(line)
    if not line or _is_template(line):
        return None
    parts = [seg.strip() for seg in line.split("|")]
    cid = parts[0].strip().lower().replace(" ", "_")
    if not cid or not re.match(r'^[a-z][a-z0-9_]*$', cid):
        return None
    if is_exit:
        last_known = parts[1] if len(parts) > 1 and not _is_template(parts[1]) else ""
        return CharacterDelta(id=cid, last_known=last_known)
    status = parts[1] if len(parts) > 1 and not _is_template(parts[1]) else ""
    knows: list[str] = []
    if len(parts) > 2 and not _is_template(parts[2]):
        for k in parts[2].split(";"):
            k = k.strip()
            if k and not _is_template(k):
                knows.append(k)
    relationship = parts[3] if len(parts) > 3 and not _is_template(parts[3]) else ""
    return CharacterDelta(
        id=cid, status=status, knows=knows, relationship_to_player=relationship,
    )


def parse_model_output(raw: str) -> ModelOutput:
    sections = _split_sections(raw)
    warnings: list[str] = []
    output = ModelOutput()

    for req in REQUIRED_SECTIONS:
        if req not in sections:
            warnings.append(f"Required section {req!r} missing from model output.")

    # ── PROSE ──────────────────────────────────────────────────────────────
    prose = sections.get("PROSE", "")
    output.prose = "" if _is_template(prose) else prose

    # ── CHOICES ────────────────────────────────────────────────────────────
    choices_raw = sections.get("CHOICES", "")
    for line in choices_raw.splitlines():
        line = _strip_bullet(line)
        if not line or _is_template(line):
            continue
        # Rescue mis-placed STATE assignment
        if re.match(r'^STATE\s*:', line, re.I) or line.startswith('$'):
            m = _STATE_ASSIGN_RE.search(line)
            if m:
                var = f"${m.group(1)}"
                output.state[var] = _coerce_value(m.group(2).strip().strip("\"'"))
            continue

        for sep in (" → ", "→", " -> ", "->"):
            line = line.replace(sep, " | ")

        parts = [seg.strip() for seg in line.split("|")]
        text = parts[0]
        if not text or _is_template(text):
            continue
        hint = ""
        if len(parts) > 1 and not _looks_like_annotation(parts[1]):
            hint = re.sub(r'^\{hint:\s*', '', parts[1]).rstrip("}").strip()
            annotation_parts = parts[2:]
        else:
            annotation_parts = parts[1:]

        choice = ParsedChoice(text=text, hint=hint)
        for ann in annotation_parts:
            _apply_choice_annotation(choice, ann)
        output.choices.append(choice)

    # ── STATE ──────────────────────────────────────────────────────────────
    state_raw = sections.get("STATE", "")
    for line in state_raw.splitlines():
        line = _strip_bullet(line)
        m = re.match(r'\$?(\w+)\s*(?:=|:|to)\s*(.+)', line)
        if m:
            var = f"${m.group(1)}"
            val_str = m.group(2).strip().strip("\"'").rstrip(";,")
            val: bool | int | str
            if val_str.lower() == "true":
                val = True
            elif val_str.lower() == "false":
                val = False
            else:
                try:
                    val = int(val_str)
                except ValueError:
                    val = val_str
            output.state[var] = val

    # ── MEDIA ──────────────────────────────────────────────────────────────
    media_raw = sections.get("MEDIA", "")
    for line in media_raw.splitlines():
        line = line.strip()
        if ":" in line and not _is_template(line):
            mtype, rest = line.split(":", 1)
            mtype = mtype.strip()
            # Optional "kw, kw | one-line description" form.
            description = ""
            if "|" in rest:
                rest, description = rest.split("|", 1)
                description = description.strip()
            keywords = []
            for k in rest.split(","):
                keyword = k.strip().strip("(){}[]")
                if keyword and not _is_template(keyword):
                    keywords.append(keyword)
            if mtype and keywords and not _is_template(mtype):
                output.media.append(
                    ParsedMediaSlot(type=mtype, keywords=keywords, description=description)
                )

    # ── NEW_CHARACTERS ─────────────────────────────────────────────────────
    for line in sections.get("NEW_CHARACTERS", "").splitlines():
        line = line.strip()
        if not line or _is_template(line):
            continue
        if "|" in line:
            cid, prose_sheet = line.split("|", 1)
            cid = cid.strip().lower().replace(" ", "_")
            prose_sheet = prose_sheet.strip()
            if (
                cid and prose_sheet
                and re.match(r'^[a-z][a-z0-9_]*$', cid)
                and not _is_template(cid)
                and not _is_template(prose_sheet)
            ):
                output.new_characters.append(ParsedCharacter(id=cid, prose_sheet=prose_sheet))

    # ── NEW_LORE ───────────────────────────────────────────────────────────
    for line in sections.get("NEW_LORE", "").splitlines():
        line = line.strip()
        if not line or _is_template(line):
            continue
        if "|" in line:
            path_part, prose_sheet = line.split("|", 1)
            prose_sheet = prose_sheet.strip()
            if "/" in path_part:
                cat, lid = path_part.strip().split("/", 1)
                cat = cat.strip()
                lid = lid.strip()
                if (
                    cat and lid and prose_sheet
                    and re.match(r'^[a-z][a-z0-9_-]*$', cat)
                    and re.match(r'^[a-z][a-z0-9_-]*$', lid)
                    and not _is_template(cat)
                    and not _is_template(lid)
                    and not _is_template(prose_sheet)
                ):
                    output.new_lore.append(ParsedLore(category=cat, id=lid, prose_sheet=prose_sheet))

    # ── THREADS ────────────────────────────────────────────────────────────
    for line in sections.get("THREADS_OPEN", "").splitlines():
        t = _strip_bullet(line)
        if t and t not in ("(none)", "(none).") and not _is_template(t):
            output.threads_open.append(t)
    for line in sections.get("THREADS_CLOSE", "").splitlines():
        t = _strip_bullet(line)
        if t and t not in ("(none)", "(none).") and not _is_template(t):
            output.threads_close.append(t)

    # ── WORLD_STATE ────────────────────────────────────────────────────────
    for line in sections.get("WORLD_STATE_ADD", "").splitlines():
        f = _strip_bullet(line)
        if f and not _is_template(f):
            output.world_state_add.append(f)
    for line in sections.get("WORLD_STATE_REMOVE", "").splitlines():
        f = _strip_bullet(line)
        if f and not _is_template(f):
            output.world_state_remove.append(f)

    # ── CHARACTER PRESENCE DELTAS ──────────────────────────────────────────
    for line in sections.get("CHARACTERS_PRESENT", "").splitlines():
        delta = _parse_character_delta(line)
        if delta:
            output.characters_present.append(delta)
    for line in sections.get("CHARACTER_STATUS", "").splitlines():
        delta = _parse_character_delta(line)
        if delta:
            output.character_status.append(delta)
    for line in sections.get("CHARACTERS_EXIT", "").splitlines():
        delta = _parse_character_delta(line, is_exit=True)
        if delta:
            output.characters_exit.append(delta)

    # ── SUMMARY ────────────────────────────────────────────────────────────
    summary = sections.get("SUMMARY", "")
    output.summary = "" if _is_template(summary) else summary

    # ── BEATS ──────────────────────────────────────────────────────────────
    for line in sections.get("BEATS", "").splitlines():
        beat = _strip_bullet(line)
        if beat and beat not in ("(none)", "(none).") and not _is_template(beat):
            output.beats.append(beat)

    # TODO(timed-narrative): parse the TIMED section here, after BEATS and before
    # the fallbacks (P3 §4.1, P2 §2.3/§3.3). An inline branch in the section loop,
    # NOT a separate _parse_timed_section helper (P3 §7 — YAGNI). Populates
    # output.timed (Optional[TimedProposal]) from the section content: timed_mode
    # (first line), timed_reveals (delay/content pairs), timed_config (for
    # countdown/recurring). Absent section → output.timed stays None (default).
    # Must import TimedProposal, TimedReveal, TimedConfig from .models.
    # Exact code sketch:
    #   timed_raw = sections.get("TIMED", "")
    #   if timed_raw.strip():
    #       from .models import TimedProposal, TimedReveal, TimedConfig
    #       # parse timed_mode (first non-empty line), then reveal blocks or config
    #       output.timed = TimedProposal(...)  # populate fields from section content
    # See p3_interfaces.md §4.1, p2_data_structures.md §2.3/§3.3.

    # ── Fallbacks for small models that ignore the format ──────────────────
    # PROSE fallback: if empty, scan raw for the first substantial prose block
    if not output.prose:
        lines = raw.strip().splitlines()
        prose_lines: list[str] = []
        _known_headers = {
            "PROSE", "CHOICES", "STATE", "MEDIA", "NEW_CHARACTERS",
            "NEW_LORE", "THREADS_OPEN", "THREADS_CLOSE",
            "WORLD_STATE_ADD", "WORLD_STATE_REMOVE",
            "CHARACTERS_PRESENT", "CHARACTERS_EXIT", "CHARACTER_STATUS",
            "SUMMARY", "BEATS",
        }
        for ln in lines:
            ln_upper = ln.strip().upper()
            if any(ln_upper.startswith(h + ":") for h in _known_headers):
                break
            stripped = _strip_bullet(ln)
            if stripped and any(sep in stripped for sep in (" | ", "→", "->")):
                break
            prose_lines.append(ln)
        candidate = "\n".join(prose_lines).strip()
        if candidate and not _is_template(candidate):
            output.prose = candidate
            warnings.append("PROSE section missing — used raw output as prose fallback.")

    # CHOICES fallback A: bullets appended inside PROSE
    if not output.choices and output.prose:
        prose_lines = output.prose.splitlines()
        tail_bullets: list[str] = []
        for ln in reversed(prose_lines):
            s = ln.strip()
            if not s:
                if tail_bullets:
                    break
                continue
            if re.match(r'^[-*•·]|^\d+[.)]\s', s):
                tail_bullets.insert(0, s)
            else:
                break
        if len(tail_bullets) >= 2:
            for raw_line in tail_bullets:
                txt = _strip_bullet(raw_line)
                if not txt or _is_template(txt):
                    continue
                text = txt
                hint = ""
                for sep in (" | ", "|", " → ", "→", " -> ", "->"):
                    if sep in txt:
                        text, hint = txt.split(sep, 1)
                        text, hint = text.strip(), hint.strip()
                        break
                if text and len(text) > 2:
                    output.choices.append(ParsedChoice(text=text[:120], hint=hint[:80]))
            if output.choices:
                cut = len(prose_lines) - len(tail_bullets)
                output.prose = "\n".join(prose_lines[:cut]).rstrip()
                warnings.append("CHOICES extracted from trailing bullet list in PROSE.")

    # CHOICES fallback B: scan all lines
    if not output.choices:
        for ln in raw.splitlines():
            stripped = _strip_bullet(ln)
            if not stripped or _is_template(stripped):
                continue
            if re.match(r'^[A-Z_]{3,}\s*:', stripped):
                continue
            for sep in (" | ", "|", " → ", "→", " -> ", "->"):
                if sep in stripped:
                    txt, hnt = stripped.split(sep, 1)
                    txt = txt.strip()
                    hnt = re.sub(r'^\{hint:\s*', '', hnt.strip()).rstrip("}").strip()
                    if txt and len(txt) > 3 and not _is_template(txt):
                        output.choices.append(ParsedChoice(text=txt, hint=hnt))
                    break
        if output.choices:
            warnings.append("CHOICES section missing — extracted choices from raw output.")

    # SUMMARY fallback: first sentence of prose
    if not output.summary and output.prose:
        first = re.split(r'(?<=[.!?])\s', output.prose)[0].strip()
        output.summary = first[:150]
        warnings.append("SUMMARY section missing — used first prose sentence as fallback.")

    output.parse_warnings = warnings
    return output


# ── JSON salvage (canonical) ─────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r'\{[\s\S]*\}')


def parse_json_object(raw: str) -> dict | None:
    """
    Return the first decodable top-level JSON object inside ``raw``.

    Tolerates code fences (```json ... ```), prose preambles, and trailing
    chatter — returns ``None`` if no decodable object is found.
    """
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.match(r'^```(?:json)?\s*([\s\S]+?)```$', text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{"):
        m = _JSON_BLOCK_RE.search(text)
        if not m:
            return None
        text = m.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _first_validation_error(e: ValidationError) -> str:
    errors = e.errors()
    if not errors:
        return "unknown"
    first = errors[0]
    loc = ".".join(str(x) for x in first.get("loc", ()))
    return f"{loc}: {first.get('msg', '')}"[:120]


def parse_model_output_json(raw: str) -> ModelOutput:
    """
    Parse strict-JSON output from Ollama's ``format`` mode.

    On parse failure, fall back to the delimited parser and append a warning so
    the caller can decide whether to retry/repair.
    """
    if not (raw or "").strip():
        out = parse_model_output(raw)
        out.parse_warnings.append("Empty model response — delimited parser fallback.")
        return out

    data = parse_json_object(raw)
    if data is None:
        out = parse_model_output(raw)
        out.parse_warnings.append("JSON-mode response had no JSON object — delimited parser fallback.")
        return out

    try:
        out = ModelOutput.model_validate(data)
    except ValidationError as e:
        # Salvage pass: keep only known top-level keys and re-validate.
        allowed = set(ModelOutput.model_fields.keys())
        salvaged = {k: v for k, v in data.items() if k in allowed}
        try:
            out = ModelOutput.model_validate(salvaged)
            out.parse_warnings.append(f"JSON validation salvaged after error: {_first_validation_error(e)}.")
        except ValidationError as e2:
            fallback = parse_model_output(raw)
            fallback.parse_warnings.append(
                f"JSON validation failed ({_first_validation_error(e2)}) — delimited parser fallback."
            )
            return fallback

    if not out.summary and out.prose:
        first = re.split(r'(?<=[.!?])\s', out.prose)[0].strip()
        out.summary = first[:150]
        out.parse_warnings.append("JSON missing summary — used first prose sentence as fallback.")
    return out


def parse_keywords_json(raw: str, max_keywords: int = 12) -> list[str]:
    """Normalise a ``{"keywords": [...]}`` response: lowercase, dedupe, cap."""
    data = parse_json_object(raw)
    if data is None:
        return []
    raw_list = data.get("keywords")
    if not isinstance(raw_list, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw_list:
        if not isinstance(item, str):
            continue
        kw = item.strip().lower().strip(".,;:")
        if not kw or len(kw) > 40 or kw in seen:
            continue
        seen.add(kw)
        out.append(kw)
        if len(out) >= max_keywords:
            break
    return out


def parse_entities_json(raw: str) -> ExtractedEntities:
    """Validate a ``{characters, locations, items, themes}`` response."""
    data = parse_json_object(raw)
    if data is None:
        return ExtractedEntities()
    try:
        return ExtractedEntities.model_validate(data)
    except ValidationError:
        allowed = set(ExtractedEntities.model_fields.keys())
        salvaged = {k: v for k, v in data.items() if k in allowed}
        try:
            return ExtractedEntities.model_validate(salvaged)
        except ValidationError:
            return ExtractedEntities()


# ── Heuristics used by the auto-repair loop in generators ────────────────────

def structured_score(parsed: ModelOutput) -> int:
    score = 0
    if parsed.prose.strip():
        score += 4
    if parsed.summary.strip():
        score += 2
    score += min(len(parsed.choices), 3) * 2
    if parsed.state:
        score += 1
    score -= len(parsed.parse_warnings)
    return score


def needs_repair(parsed: ModelOutput) -> bool:
    if not parsed.prose.strip():
        return True
    if not parsed.summary.strip():
        return True
    return len(parsed.choices) == 0

"""Centralized prompt templates.

All Ollama-bound prompts live here so they can be versioned, snapshotted, and
tuned independently of the call-site code.

PROMPT_VERSION bumps any time wording or structure changes — golden regression
tests pin against this number.
"""
from __future__ import annotations

PROMPT_VERSION = 9
# TODO(macro-vocab): I12 — bump PROMPT_VERSION from 7 to 8 (P3 I12, P2 DS-4).
# Reflects SUGARCUBE_GUIDANCE content changes (I11) and available_includes
# parameter additions (I4/I5/I6). Golden tests pin against this number.


# ── SugarCube 2 authoring guidance ───────────────────────────────────────────
#
# Compact cheat sheet injected into the full and JSON passage prompts so the
# model emits SugarCube-idiomatic markup instead of markdown / generic Twine.
# Distilled from docs/sugarcube2-analysis.md §5 (Key Patterns) and the SugarCube
# 2 docs. Kept short to respect token budgets on local models.
SUGARCUBE_GUIDANCE = """\
[SUGARCUBE AUTHORING NOTES]
Variable scopes:
- $var  : persistent story state (flags, inventory, relationships) — saved.
- _var  : temporary per-turn value (loop counters, temp math) — not saved.
State writes use the `to` operator: <<set $flag to true>>, <<set $gold to 5>>.
Markup (NOT markdown):
- ''bold''  //italic//  __underline__  ~~strike~~  ""highlight""
- $var auto-interpolates in prose: "You have $gold coins."
- Complex expressions: <<print $obj.prop>>  (use for dot/bracket access).
- Conditional prose: <<if $open>>open<<else>>shut<</if>>
- Shared/repeated content: <<include "passage_name">>
- Reusable markup macros (widget): define once in a [widget]-tagged passage,
  call anywhere as <<widget_name>>.
Choices the harness renders for you — just give text + hint; do NOT emit
SugarCube link/macro syntax in CHOICES.
<<capture>> rule: any <<link>>/<<button>>/<<timed>> inside a <<for>> loop,
or whose <<set>> body references a loop variable, MUST be wrapped in
<<capture $loopvar>>…<</capture>> so each iteration's click handler sees
its own value (docs/sugarcube2-analysis.md §3.9).

Input macros (for form passages) use QUOTED variable names:
- <<textbox "$name" "default">>  <<numberbox "$age" 18>>  <<textarea "$bio" "">>
- <<checkbox "$flag" "off" "on">>  <<radiobutton "$g" "F">>  <<radiobutton "$g" "M">>
- <<listbox "$x">><<option "A">><<option "B">><</listbox>>
- <<cycle "$y">><<option "A">><<option "B">><</cycle>>
The quotes pass the NAME, not the value — SugarCube writes to $var as the
player interacts. Emit inputs in the INPUT section: `kind | $var | default | label`.
"""
# TODO(achievements): I7 - append one memorize/recall scope note BEFORE the
# closing triple-quote of SUGARCUBE_GUIDANCE above (P3 section 4 I7, P1 section 4C). Text:
#   - memorize()/recall(): cross-playthrough data (achievements, NG+) -
#     persists across restarts, not in saves.
# Only included when achievements_enabled. See p3_interfaces.md section 4 I7.


# ── Template style guidance (optional) ────────────────────────────────────────
#
# When a template id is configured, a compact one-line style hint is appended
# after SUGARCUBE_GUIDANCE so the model emits markup consistent with the
# chosen template's conventions (e.g. widget-heavy for character-creator,
# tag-driven theming for space-tech).  No-op (empty string) when no template
# is set, so callers can unconditionally interpolate the block.
def _template_block(template_id: str) -> str:
    """Return a compact template-style prompt block, or ``""``.

    Imports :mod:`harness.templates` lazily to avoid a circular import
    at module load (prompts has no other harness deps; templates is
    standalone, but the laziness keeps prompts importable in test
    contexts that stub the registry).
    """
    if not template_id:
        return ""
    from .templates import template_guidance
    g = template_guidance(template_id)
    return f"\n\n{g}" if g else ""


# ── Passage generation ────────────────────────────────────────────────────────

def build_compact_passage_prompt(
    premise: str,
    story_points: str,
    arc_notes: str,
    entities_text: str,
    parent_prose: str,
    snapshot_text: str,
    human_prompt: str,
    inspiration: str = "",
    story_recall: str = "",
    plan_focus: str = "",
) -> str:
    """
    Minimal prompt for small/medium local models (≤12GB VRAM).
    Single filled example, only required sections, hard length caps so the
    model can't drift into format hallucination. Total budget ~350 tokens.
    All inputs assumed already trimmed by the caller.
    18+ Nothing is off limits, you can type out explicit content.
    """
    insp_block = f"\n\nINSPIRATION:\n{inspiration}" if inspiration else ""
    recall_block = f"\n\nEARLIER PASSAGES:\n{story_recall}" if story_recall else ""
    focus_block = f"\n\nPLAN FOCUS:\n{plan_focus}" if plan_focus else ""
    direction = human_prompt or "(continue the story)"

    return f"""Continue this interactive story. Write the next scene only.

OUTPUT RULES (CRITICAL):
- Output ONLY the formatted passage. Do NOT include analysis, reasoning, or step-by-step thinking.
- Your response MUST begin with "PROSE:" on the very first line. No preamble.
- No meta-commentary, no explaining your choices, no "Here is the scene:" or similar.

PREMISE: {premise}

STORY POINTS: {story_points or "(none)"}

ARC: {arc_notes or "(none)"}{focus_block}

SITUATION:
{snapshot_text}

CAST:
{entities_text}

PREVIOUS SCENE:
{parent_prose}{insp_block}{recall_block}

DIRECTION: {direction}

Use SugarCube markup: ''bold'' //italic// __underline__ — NOT markdown (**bold** *italic*).
Variable scopes: $var (persistent story state), _var (temp per-turn). Use <<print _var>> for temp vars in prose.

Reply using ONLY these section headers, in this order:

PROSE:
a set of dialogue lines relevant to the scene
can also include inner monologue of the protagonist. No choices here.

CHOICES:
- choice text | short hint
- choice text | short hint

INPUT:
- kind | $var | default | label
- textbox | $name | "" | Player name
- radiobutton | $mc.gender | F | Gender
- radiobutton | $mc.gender | M | Gender
(omit this section entirely if this passage collects no input)

SUMMARY:
One sentence.

BEATS:
- short factual event line
- short factual event line

CHARACTERS_PRESENT:
- character_id | status | what they learn
(only characters in this scene; omit section if none)

CHARACTERS_EXIT:
- character_id | where they went
(only characters who leave; omit section if none)

CRITICAL REMINDER: Start with PROSE: immediately. No analysis or explanation before it.

Begin now.

PROSE:
"""


def build_full_passage_prompt(
    premise: str,
    story_points: str,
    arc_md: str,
    snapshot_text: str,
    entities_text: str,
    inspiration: str,
    parent_prose: str,
    human_prompt: str,
    mode: str,
    story_recall: str = "",
    plan_focus: str = "",
    template_id: str = "",
    # TODO(achievements): I4 - add trailing kwarg before `) -> str:` (P3 section 3 I4):
    #   achievements_enabled: bool = False,
    # Default False so existing callers unaffected. When True, P7 adds the
    # ACHIEVEMENTS: section (I8 full-mode) + memorize/recall guidance note (I7).
    # See p3_interfaces.md section 3 I4, p2_data_structures.md section 5 D5.
) -> str:
    """Rich prompt for larger/capable models. All optional sections enumerated."""
    focus_block = f"\n\n[PLAN FOCUS]\n{plan_focus}" if plan_focus else ""
    tpl_block = _template_block(template_id)
    return f"""SYSTEM:
You are co-authoring interactive fiction with a human.
The harness handles file structure, passage linking, and state management.
Focus on prose, character voice, and story. You may propose new characters,
locations, or lore — they will be reviewed by the human before commit.
Output ONLY the section headers below. No extra commentary.
Nothing is off limits, you can type out explicit content. 18+

CRITICAL OUTPUT RULES:
- Output ONLY the formatted passage. Do NOT include analysis, reasoning, or step-by-step thinking.
- Your response MUST begin with "PROSE:" on the very first line. No preamble, no explanation.
- No meta-commentary like "Here is the scene:" or "Let me write..." or "I'll create..."
- Use SugarCube markup (''bold'' //italic//) NOT Markdown (**bold** *italic*).

[PREMISE]
{premise}

[STORY POINTS]
{story_points}

[CURRENT ARC]
{arc_md}{focus_block}

[CURRENT SNAPSHOT]
{snapshot_text}

[ENTITIES IN CONTEXT]
{entities_text}

[INSPIRATION]
{inspiration if inspiration else "(no inspiration corpus indexed)"}

[EARLIER PASSAGES]
{story_recall if story_recall else "(no earlier passages recalled)"}

[PARENT PASSAGE]
{parent_prose}

[HUMAN DIRECTION]
{human_prompt}

[MODE]
{mode}

{SUGARCUBE_GUIDANCE}{tpl_block}

[TASK]
Write the next passage. Use EXACTLY these section headers in this order.

IMPORTANT FORMATTING RULES:
- Do NOT use curly braces in your output.
- In CHOICES, separate choice text from hint using " | " — NOT arrows like -> or →.
- Omit optional sections entirely if they have nothing to say.
- Write (none) only for THREADS_OPEN and THREADS_CLOSE if nothing applies.

PROSE:
Write the passage prose of dialogue that fits the scene. This is what the player reads.
can also include inner monologue of the protagonist.

CHOICES:
- First choice text | hint about where this leads
- Second choice text | hint about where this leads

INPUT:
- kind | $var | default | label
- textbox | $name | "" | Player name
- numberbox | $age | 18 | Age
- checkbox | $hardcore | "off" | "on" | Hardcore mode
- radiobutton | $mc.gender | F | Gender
- radiobutton | $mc.gender | M | Gender
- listbox | $class | | Class
  - option | Fighter
  - option | Mage
- cycle | $tone | | Tone
  - option | Serious
  - option | Playful
(omit this section entirely if this passage collects no input)

STATE:
$variable_name = value
(omit this section entirely if no state changes)

MEDIA:
image: keyword, keyword, keyword | one-line description of the shot
(the "| description" part is optional; omit this section entirely if no media needed)

NEW_CHARACTERS:
character_id | One paragraph describing this new character.
Include: physical appearance, personality, motivation, backstory, key relationships, and speech mannerisms if space allows.
(omit this section entirely if no new characters appear)

NEW_LORE:
category/entry_id | One paragraph about this new location, faction, or item.
(omit this section entirely if no new lore is introduced)

THREADS_OPEN:
A new plot thread.
(none)

THREADS_CLOSE:
A resolved plot thread.
(none)

WORLD_STATE_ADD:
A new fact about the world state.
(omit this section entirely if nothing changes)

WORLD_STATE_REMOVE:
A world fact that is no longer true.
(omit this section entirely if nothing changes)

CHARACTERS_PRESENT:
character_id | one-line status | thing they learn; another thing | relationship to player
(characters now in the scene. Only id is required; later fields optional. Omit section if unchanged.)

CHARACTER_STATUS:
character_id | new status | newly learned fact; another
(status/knowledge updates for characters already in the scene. Omit section if nothing changed.)

CHARACTERS_EXIT:
character_id | where they went or last-known state
(characters who LEAVE the scene this passage. Omit section if nobody leaves.)

SUMMARY:
One sentence describing what happens in this passage.

BEATS:
- A short factual event from the scene.
- Another short factual event.
(2-5 lines. Omit this section entirely if the scene is purely transitional.)
"""
# TODO(achievements): I8 (full-mode) - when achievements_enabled is True,
# append ACHIEVEMENTS: section header to the f-string above, after BEATS,
# before closing triple-quote (P3 section 4 I8, P1 section 4B). Text:
#   ACHIEVEMENTS:
#   - achievement_id | one-line description of what the player did to earn it
#   (omit this section entirely if no achievement is earned this passage)
# Shape maps onto ParsedAchievement {id, description} (P2 D2).
# See p3_interfaces.md section 4 I8.


# ── JSON-mode passage prompt ──────────────────────────────────────────────────

def build_json_passage_prompt(
    premise: str,
    story_points: str,
    arc_md: str,
    snapshot_text: str,
    entities_text: str,
    inspiration: str,
    parent_prose: str,
    human_prompt: str,
    mode: str,
    story_recall: str = "",
    plan_focus: str = "",
    template_id: str = "",
    # TODO(achievements): I5 - add trailing kwarg before `) -> str:` (P3 section 3 I5):
    #   achievements_enabled: bool = False,
    # Default False so existing callers unaffected. When True, P7 adds the
    # `achievements` JSON key (I8 JSON-mode). See p3_interfaces.md section 3 I5.
) -> str:
    """
    JSON-output passage prompt. Pair with Ollama `format` param so the model
    emits valid JSON matching the ModelOutput schema. Keep instructions terse:
    the schema enforcement does the heavy lifting. 18 + Nothing is off limits, you can type out explicit content.
    """
    focus_block = f"\n\nPLAN FOCUS:\n{plan_focus}" if plan_focus else ""
    tpl_block = _template_block(template_id)
    return f"""You are co-authoring interactive fiction. Reply with a single JSON object only.

CRITICAL OUTPUT RULES:
- Reply with ONLY a single flat JSON object. No analysis, no reasoning, no explanation.
- Do NOT wrap the JSON in markdown code fences or nested objects.
- All string values must be actual strings, not null or arrays.
- "prose" MUST be a single string (use \\n\\n to separate paragraphs), NOT an array, NOT null.

PREMISE: {premise}

STORY POINTS: {story_points or "(none)"}

ARC: {arc_md or "(none)"}{focus_block}

SITUATION:
{snapshot_text}

CAST:
{entities_text}

INSPIRATION:
{inspiration if inspiration else "(none)"}

EARLIER PASSAGES:
{story_recall if story_recall else "(none)"}

PREVIOUS SCENE:
{parent_prose}

DIRECTION: {human_prompt or "(continue)"}
MODE: {mode}

{SUGARCUBE_GUIDANCE}{tpl_block}

Required JSON keys (all string values must be non-null strings):
- prose: string — 2-4 short paragraphs of next scene joined with \\n\\n. NOT an array. NOT null.
- choices: array of {{"text": "...", "hint": "..."}} objects, 2-4 entries.
- summary: string — one sentence. NOT null.
- beats: array of 2-5 short factual event strings from the scene.

Optional JSON keys (omit or empty if unused):
- state: {{"$var": value}} pairs the choice/scene sets.
- media: [{{"type": "image|audio|video", "keywords": [...], "description": "one-line shot description"}}]
- new_characters: [{{"id": "lowercase_id", "prose_sheet": "...", "physical": "...", "personality": "...", "motivation": "...", "backstory": "...", "relationships": "...", "speech": "..."}}]
- new_lore: [{{"category", "id", "prose_sheet"}}]
- threads_open / threads_close: arrays of plot-thread strings.
- world_state_add / world_state_remove: arrays of world fact strings.
- characters_present: [{{"id", "status", "knows": [...], "relationship_to_player"}}] — characters now in the scene.
- character_status: same shape — status/knowledge updates for characters already present.
- characters_exit: [{{"id", "last_known"}}] — characters who leave the scene.
- inputs: [{{"kind": "textbox|numberbox|textarea|checkbox|radiobutton|listbox|cycle", "var": "$name", "label": "...", "default": "...", "options": [{{"label", "value", "selected"}}], "autofocus": bool, ...}}] — form input fields. Omit or empty if not a form passage.
# TODO(achievements): I8 (JSON-mode) - when achievements_enabled is True,
# append to the Optional JSON keys list above, after characters_exit (P3 section 4 I8):
#   - achievements: [{{"id": "achievement_id", "description": "one-line text"}}] -
#     achievements earned this passage (omit or empty if none).
# Shape maps onto ParsedAchievement (P2 D2). See p3_interfaces.md section 4 I8.

Reply with ONLY the JSON object. No prose preamble, no code fences.
"""


# ── Thinking-aware passage prompt ───────────────────────────────────────────
#
# For models that produce chain-of-thought reasoning (DeepSeek-R1, QwQ,
# gpt-oss, etc.). Explicitly allows thinking before the formatted output,
# with a clear separator. The harness's thinking.py module extracts the
# thinking content and scores it separately from the formatted output.
#
# The prompt instructs the model to:
# 1. Think through the scene (state variables, character motivations, plot)
# 2. Output a clear separator line: ===PASSAGE===
# 3. Output the formatted SugarCube passage after the separator
#
# This tests whether thinking models can produce BETTER SugarCube output
# when their reasoning is acknowledged and structured rather than suppressed.

_THINKING_SEPARATOR = "===PASSAGE==="


def build_thinking_passage_prompt(
    premise: str,
    story_points: str,
    arc_md: str,
    snapshot_text: str,
    entities_text: str,
    inspiration: str,
    parent_prose: str,
    human_prompt: str,
    mode: str,
    story_recall: str = "",
    plan_focus: str = "",
    template_id: str = "",
) -> str:
    """Thinking-aware prompt for reasoning models.

    Explicitly invites chain-of-thought reasoning before the formatted output,
    with a clear separator. The thinking content is extracted and scored by
    score_thinking_quality in the benchmark.

    The thinking section should cover:
    - State variable analysis (what $vars exist, what should change)
    - Character motivations and reactions
    - SugarCube markup decisions (which macros to use)
    - Direction-following plan (how to address the human_prompt)

    After thinking, the model outputs the separator, then the formatted
    passage using the same section headers as the full prompt.
    """
    focus_block = f"\n\n[PLAN FOCUS]\n{plan_focus}" if plan_focus else ""
    tpl_block = _template_block(template_id)
    return f"""You are co-authoring interactive fiction with a human. You are a reasoning model: think before you write.

CRITICAL OUTPUT FORMAT:
- First, write your thinking/reasoning about the scene.
- Then output the separator line: {_THINKING_SEPARATOR}
- Then output the formatted SugarCube passage (starting with PROSE:).

Your thinking should cover:
1. State analysis: What variables exist ($gold, $hasMetKing, etc.)? What should change?
2. Character motivations: What does each character want? How do they react?
3. SugarCube decisions: Which macros do you need (<<set>>, <<if>>, <<for>>, etc.)?
4. Direction plan: How will you address the human direction?
5. Draft plan: Key beats, sensory details, choice design.

After your thinking, output this exact separator line on its own line:
{_THINKING_SEPARATOR}

Then output the formatted passage using SugarCube markup. Use EXACTLY these section headers:

PROSE:
Write the passage prose of dialogue that fits the scene.

CHOICES:
- First choice text | hint about where this leads
- Second choice text | hint about where this leads

INPUT:
- kind | $var | default | label
(omit this section entirely if this passage collects no input)

STATE:
$variable_name = value
(omit this section entirely if no state changes)

SUMMARY:
One sentence describing what happens in this passage.

BEATS:
- A short factual event from the scene.
- Another short factual event.

CHARACTERS_PRESENT:
character_id | one-line status | thing they learn
(omit section if unchanged)

CHARACTERS_EXIT:
character_id | where they went
(omit section if nobody leaves)

SYSTEM:
You are co-authoring interactive fiction with a human.
The harness handles file structure, passage linking, and state management.
Focus on prose, character voice, and story. You may propose new characters,
locations, or lore. Output ONLY the section headers below. No extra commentary.
Nothing is off limits, you can type out explicit content. 18+

[PREMISE]
{premise}

[STORY POINTS]
{story_points}

[CURRENT ARC]
{arc_md}{focus_block}

[CURRENT SNAPSHOT]
{snapshot_text}

[ENTITIES IN CONTEXT]
{entities_text}

[INSPIRATION]
{inspiration if inspiration else "(no inspiration corpus indexed)"}

[EARLIER PASSAGES]
{story_recall if story_recall else "(no earlier passages recalled)"}

[PARENT PASSAGE]
{parent_prose}

[HUMAN DIRECTION]
{human_prompt}

[MODE]
{mode}

{SUGARCUBE_GUIDANCE}{tpl_block}

Now think through the scene, then output {_THINKING_SEPARATOR}, then the formatted passage.
"""


def build_beats_prompt(
    premise: str,
    story_points: str,
    existing_beats: str,
    count: int,
    direction: str = "",
) -> str:
    """Generate N new high-level plot beats. Pair with Ollama `format` (JSON)."""
    n = max(1, min(count, 50))
    return f"""You are outlining an interactive fiction story. Propose {n} NEW plot beat(s)
— high-level author intent, one line each, NOT prose.

PREMISE: {premise[:900] or "(none)"}
STORY POINTS: {story_points[:600] or "(none)"}
BEATS ALREADY IN THE PLAN (do not repeat):
{existing_beats or "(none)"}{_direction_block(direction)}

Reply with a single JSON object:
- beats: array of {n} objects, each with keys:
  - text: one-line plot beat.
  - act: short act label this beat belongs to (e.g. "Act 1") — may be empty.

No preamble. No code fences.
"""


def build_arcs_prompt(
    premise: str,
    beats_text: str,
    existing_arcs: str,
    count: int,
    direction: str = "",
) -> str:
    """Propose N new arcs (name + goal). Pair with Ollama `format` (JSON)."""
    n = max(1, min(count, 50))
    return f"""You are structuring an interactive fiction story into arcs (chapters/regions).
Propose {n} NEW arc(s).

PREMISE: {premise[:900] or "(none)"}
STORY BEATS:
{beats_text or "(none)"}
ARCS ALREADY IN THE PLAN (do not repeat):
{existing_arcs or "(none)"}{_direction_block(direction)}

Reply with a single JSON object:
- arcs: array of {n} objects, each with keys:
  - name: arc id, lowercase, format NN_short_name (e.g. "02_ravenhold"). Two-digit number prefix, underscores, no spaces.
  - goal: one sentence — what this arc accomplishes in the story.

IMPORTANT: The name MUST start with a two-digit number followed by an underscore.
Do NOT use "nn" literally. Use actual numbers like 01, 02, 03, etc.
Do NOT include the word "arc" in the name.

No preamble. No code fences.
"""


def build_arc_scenes_prompt(
    premise: str,
    arc_goal: str,
    arc_notes: str,
    beats_text: str,
    existing_scenes: str,
    count: int,
    direction: str = "",
) -> str:
    """Outline N planned scenes for one arc — sketches, not full prose.

    Pair with Ollama `format` for strict JSON. Each scene is a title + one-line
    summary + a few keywords + the characters present.
    """
    n = max(1, min(count, 50))
    return f"""You are outlining scenes for one arc of an interactive fiction story.
Sketch {n} planned scene(s) — high-level beats, NOT full prose.

PREMISE: {premise[:800] or "(none)"}
ARC GOAL: {arc_goal[:400] or "(none)"}
ARC NOTES: {arc_notes[:500] or "(none)"}
STORY BEATS THIS ARC ADVANCES:
{beats_text or "(none)"}
SCENES ALREADY PLANNED (do not repeat):
{existing_scenes or "(none)"}{_direction_block(direction)}

Reply with a single JSON object:
- scenes: array of {n} objects, each with keys:
  - title: 2-5 word scene title.
  - summary: one sentence — what happens.
  - keywords: array of 3-6 short mood/imagery/action tags.
  - characters: array of character names present in the scene (may be empty).

No preamble. No code fences.
"""


def build_inspiration_summary_prompt(text: str) -> str:
    """Compact digest of a reference/inspiration item: game type, themes, cast.

    Pair with Ollama `format` so output is strict JSON.
    """
    snippet = (text or "").strip()
    if len(snippet) > 4000:
        snippet = snippet[:4000].rsplit(" ", 1)[0]
    return f"""Analyze the reference material below. It may be an interactive-fiction
story, world notes, or a parsed game report. Be concise.

Reply with a single JSON object:
- game_type: short phrase for the kind of game/story (e.g. "branching dark-fantasy mystery").
- themes: array of 2-5 short theme keywords (1-3 words each).
- characters: array of up to 6 named characters (names only, no descriptions).
- summary: one or two sentences capturing premise and tone.

No preamble. No code fences.

MATERIAL:
{snippet}
"""


def build_summary_prompt(prose: str) -> str:
    """One-sentence summary prompt used as a fallback when SUMMARY is missing."""
    snippet = (prose or "").strip()
    if len(snippet) > 1400:
        snippet = snippet[:1400].rsplit(" ", 1)[0]
    return f"""Summarize the passage in ONE sentence. Be concise and factual.

PASSAGE:
{snippet}

SUMMARY:
"""


def build_scene_keywords_prompt(text: str) -> str:
    """Extract scene keywords + a one-sentence summary from prose or direction."""
    snippet = (text or "").strip()
    if len(snippet) > 1800:
        snippet = snippet[:1800].rsplit(" ", 1)[0]
    return f"""Extract scene keywords and a one-sentence summary.

Return JSON with keys:
- keywords: array of 5-12 short keywords/phrases
- summary: one concise sentence describing what is happening

TEXT:
{snippet}

JSON:
"""


def build_scene_threads_prompt(text: str) -> str:
    """Extract open threads and world state from a scene."""
    snippet = (text or "").strip()
    if len(snippet) > 1800:
        snippet = snippet[:1800].rsplit(" ", 1)[0]
    return f"""Extract open plot threads and world state facts.

Return JSON with keys:
- open_threads: array of 0-5 short unresolved questions/tensions
- world_state: array of 0-6 factual world state lines

TEXT:
{snippet}

JSON:
"""


def build_scene_choices_prompt(text: str) -> str:
    """Suggest choices (text + hint) for a scene."""
    snippet = (text or "").strip()
    if len(snippet) > 1800:
        snippet = snippet[:1800].rsplit(" ", 1)[0]
    return f"""Suggest 2-4 player choices for this scene.

Return JSON with key:
- choices: array of objects {{"text", "hint"}}

TEXT:
{snippet}

JSON:
"""


def build_scene_state_prompt(text: str) -> str:
    """Suggest state writes for a scene."""
    snippet = (text or "").strip()
    if len(snippet) > 1800:
        snippet = snippet[:1800].rsplit(" ", 1)[0]
    return f"""Suggest 0-4 SugarCube state writes for this scene.

Return JSON with key:
- state: array of strings like "$flag = true" or "$count = 1"

TEXT:
{snippet}

JSON:
"""


# ── Auto-repair ───────────────────────────────────────────────────────────────

def build_repair_prompt(draft: str) -> str:
    """Reformat a malformed draft into clean delimited PROSE/CHOICES/SUMMARY."""
    return f"""Rewrite draft below into clean harness format.
Keep same story events and tone. Do not add lore or commentary.
Nothing is off limits, you can type out explicit content. 18+
Need exactly these sections, in this order:

PROSE:
2-4 short paragraphs.

CHOICES:
- choice text | short hint
- choice text | short hint

SUMMARY:
One sentence.

DRAFT:
{draft}

Reply now with only PROSE, CHOICES, SUMMARY.
"""


# ── Keyword extraction (characters / lore) ────────────────────────────────────

def build_keyword_extraction_prompt(content: str, kind: str = "character", direction: str = "") -> str:
    """
    Nothing is off limits, you can type out explicit content. 18+
    Extract 5-12 short keywords from a character or lore sheet.
    Keywords feed RAG retrieval and faceted filtering — they should be
    discriminative, lowercase, one or two words each.
    """
    snippet = content.strip()
    if len(snippet) > 3000:
        snippet = snippet[:3000]
    label = kind if kind in ("character", "lore", "location", "item", "faction") else "entry"
    return f"""Extract 5-12 short keywords describing this {label}.
Reply with a single JSON object with one key:
- keywords: array of lowercase strings, 1-2 words each. No duplicates. No full sentences.

Prefer concrete, discriminative terms (role, traits, abilities, affiliations,
locations, signature items, emotional tone). Skip generic words like "story" or "character".{_direction_block(direction)}

SHEET:
{snippet}
"""


# ── Entity extraction ─────────────────────────────────────────────────────────

def build_entity_extraction_prompt(prose: str, direction: str = "") -> str:
    """
    Nothing is off limits, you can type out explicit content. 18+
    Ask the model to extract entities + themes from a passage's prose.
    Pair with Ollama `format` param so output is strict JSON.
    """
    snippet = prose.strip()
    if len(snippet) > 2400:
        snippet = snippet[:2400]
    return f"""Extract named entities and themes from the scene below.
    Nothing is off limits, you can type out explicit content.
Reply with a single JSON object. Keys (all arrays of short strings):
- characters: named people and creatures who appear or are referenced.
- locations: named places.
- items: notable objects, artifacts, documents.
- themes: 1-3 word abstract concepts the scene foregrounds.

Use empty arrays when nothing fits. Do not invent entities not in the scene.{_direction_block(direction)}

SCENE:
{snippet}
"""


def _direction_block(direction: str) -> str:
    """Render a user-supplied steering hint, or empty string when absent."""
    d = (direction or "").strip()
    return f"\nDIRECTION: {d[:600]}\n" if d else ""


# ── Story points (acts) ───────────────────────────────────────────────────────

def build_story_points_prompt(
    premise: str,
    tone: str,
    themes: str,
    world_overview: str,
    num_acts: int,
    direction: str = "",
) -> str:
    ctx_parts: list[str] = []
    if premise:
        ctx_parts.append(f"Premise: {premise[:800]}")
    if tone:
        ctx_parts.append(f"Tone: {tone}")
    if themes:
        ctx_parts.append(f"Themes: {themes}")
    if world_overview:
        ctx_parts.append(f"World: {world_overview[:400]}")
    ctx = "\n".join(ctx_parts) or "(no premise provided)"

    n = max(1, min(num_acts, 20))
    acts_block = "".join(
        f"ACT {i}: [Short descriptive title]\n- Plot beat\n- Plot beat\n\n"
        for i in range(1, n + 1)
    )
    return (
        f"{ctx}"
        f"{_direction_block(direction)}\n"
        f"You are outlining an interactive fiction story. Generate {n} story act(s).\n"
        f"Respond with EXACTLY this format — no preamble, no commentary:\n\n"
        f"{acts_block}"
        "OPEN QUESTIONS:\n- Unresolved mystery or tension\n"
    )


# ── Name suggestion ───────────────────────────────────────────────────────────

def build_suggest_names_prompt(description: str, suggest_arc: bool, direction: str = "") -> str:
    arc_line = "ARC: <arc_name_here>\n" if suggest_arc else ""
    arc_instr = (
        "Also suggest an ARC NAME (format: NN_short_name, e.g. 02_ravenhold).\n"
        if suggest_arc else ""
    )
    return (
        "You are naming passages in a SugarCube interactive fiction story.\n"
        "Rules:\n"
        "- Passage slug: lowercase, underscores only, start with two-digit number, e.g. 03_dark_alley\n"
        "- Max 4 words after the number\n"
        f"{arc_instr}"
        f"Description: {description}"
        f"{_direction_block(direction)}\n"
        "Respond with ONLY:\n"
        "SLUG: <your_slug_here>\n"
        f"{arc_line}"
        "(no other text)"
    )


# ── Story-init generation steps (wizard helpers) ──────────────────────────────

def build_premise_prompt(seed: str, direction: str = "") -> str:
    """
    Turn a seed idea (a few words or a sentence) into a full premise paragraph.
    JSON output: {"title": str, "premise": str}.
    """
    return f"""You are designing an interactive fiction story.
Expand the seed below into a story premise.

SEED: {seed[:600] or "(no seed; invent something compelling)"}{_direction_block(direction)}

Reply with a single JSON object:
- title: short, evocative title (3-7 words).
- premise: 2-4 sentences. Establish setting, central tension, and what the player is doing.

No preamble. No code fences.
"""


def build_tone_themes_prompt(premise: str, direction: str = "") -> str:
    """JSON output: {"tone": str, "themes": str}."""
    return f"""Given the premise below, suggest narrative tone and thematic concerns.

PREMISE: {premise[:1200]}{_direction_block(direction)}

Reply with a single JSON object:
- tone: 1-2 sentences describing voice, mood, register (e.g. "dark fantasy with dry humour").
- themes: 1-2 sentences listing 3-5 thematic preoccupations.

No preamble. No code fences.
"""


def build_world_prompt(
    premise: str,
    tone: str = "",
    themes: str = "",
    direction: str = "",
) -> str:
    """JSON output: {"world_overview": str}."""
    return f"""Given the premise (and optional tone/themes), sketch a world overview.

PREMISE: {premise[:1200]}
TONE: {tone[:300] or "(unspecified)"}
THEMES: {themes[:300] or "(unspecified)"}{_direction_block(direction)}

Reply with a single JSON object:
- world_overview: 3-5 sentences. Geography, history hook, distinct rules or factions, sensory feel.

No preamble. No code fences.
"""


def build_opening_prompt(
    premise: str,
    world_overview: str = "",
    direction: str = "",
) -> str:
    """JSON output: {"opening_situation": str}."""
    return f"""Given the premise and world, write the opening situation — where the player begins.

PREMISE: {premise[:1200]}
WORLD: {world_overview[:800] or "(unspecified)"}{_direction_block(direction)}

Reply with a single JSON object:
- opening_situation: 2-4 sentences. Where the player is, what is immediately happening, what is at stake.

No preamble. No code fences.
"""


def build_characters_sketch_prompt(
    premise: str,
    world_overview: str = "",
    count: int = 3,
    direction: str = "",
) -> str:
    """JSON output: {"characters": [{"id", "name", "description", ...}, ...]}.

    Enriched to produce deep characters with structured fields:
    physical description, personality traits, motivation, backstory,
    relationships, and speech mannerisms. Each field is optional in the
    JSON schema so smaller models that omit some fields still parse, but
    the prompt explicitly requests all six.
    """
    n = max(1, min(count, 12))
    return f"""Given the premise (and optional world overview), invent {n} principal characters.

PREMISE: {premise[:1200]}
WORLD: {world_overview[:800] or "(unspecified)"}{_direction_block(direction)}

Reply with a single JSON object:
- characters: array of {n} objects with keys:
  - id: lowercase_snake_case slug, 1-3 words (e.g. "warden_kael").
  - name: display name.
  - description: 2-3 sentences covering role, distinguishing trait, and tension with the world.
  - physical: 1-2 sentences describing appearance, build, clothing, distinguishing features.
  - personality: 2-3 key personality traits, comma-separated or short phrases.
  - motivation: 1-2 sentences — what drives this character, what they want.
  - backstory: 2-3 sentences — relevant history that shaped them.
  - relationships: 1-2 sentences — key connections to other characters or factions.
  - speech: 1-2 sentences — how they talk, verbal tics, vocabulary, accent.

All seven fields (description, physical, personality, motivation, backstory,
relationships, speech) are REQUIRED. Write concrete, specific details — not
generic archetypes. Characters should feel like real people with depth.

No preamble. No code fences.
"""


def build_locations_sketch_prompt(
    premise: str,
    world_overview: str = "",
    count: int = 3,
    direction: str = "",
) -> str:
    """JSON output: {"locations": [{"id", "name", "description"}, ...]}."""
    n = max(1, min(count, 12))
    return f"""Given the premise (and optional world overview), invent {n} key locations.

PREMISE: {premise[:1200]}
WORLD: {world_overview[:800] or "(unspecified)"}{_direction_block(direction)}

Reply with a single JSON object:
- locations: array of {n} objects with keys:
  - id: lowercase_snake_case slug, 1-3 words (e.g. "ravenhold_market").
  - name: display name.
  - description: 2-3 sentences covering geography, mood, and what happens there.

No preamble. No code fences.
"""

# Technical Report: Anonymized SugarCube 2 Compiled Game (`example-structure.html`)

Analysis of `examples/game_templates/example-structure.html` — a real SugarCube 2
game compiled to a single HTML file, then anonymized. **File: 10,227 lines,
676 KB, 158 passages.** Line references below point into this file.

This report complements `docs/sugarcube2-analysis.md` (which covers the SugarCube
*documentation*); here we analyze a *compiled game artifact*.

---

## 1. Overall HTML Structure

The file is a standard Twine/SugarCube 2 single-file build: HTML document
wrapping a `<tw-storydata>` root that holds all passages, plus head/body
scaffolding. SugarCube normally injects its engine via `<script>` blocks; here
those blocks survive structurally but their contents are blanked (see §3).

| Section | Lines | Contents |
|---|---|---|
| `<!DOCTYPE>` + `<html>` | 1–2 | `data-init=""` (attribute emptied) |
| `<head>` | 3–20 | 1 `<script>` + 11 `<style>` blocks, all `/* Lorem ipsum… */` |
| `<body>` UI scaffold | 21–26 | 3 nested `<div id="">` containers: noscript fallback, loading text, story region |
| `<tw-storydata>` root | 27–10224 | Story metadata + embedded `<style>`/`<script>` + 158 `<tw-passagedata>` |
| Trailing `<script>` | 10225 | SugarCube engine loader (blanked) |
| `</body></html>` | 10226–10227 | close |

**Key structural facts:**
- The `<tw-storydata>` element (line 27) carries the full standard attribute set:
  `name`, `startnode`, `creator`, `creator-version`, `format`, `format-version`,
  `ifid`, `options`, `tags`, `zoom`, `hidden` — **all emptied to `""`** during
  anonymization except `tags="lorem-ipsum"` and `hidden`.
- Inside `<tw-storydata>` (line 27, same line): an embedded `<style role="" id=""
  type="">` and `<script role="" id="" type="">` — both empty. In a real build
  these carry the story's user CSS and the SugarCube story-format bootstrap.
- All 158 passages are `<tw-passagedata>` elements with attributes
  `pid`, `name`, `tags`, `position`, `size` — all emptied, all `tags="lorem-ipsum"`.
- Passages are stored **inline in the HTML** (not as JSON). This is the classic
  Twine 2 "compiled to HTML" format, not the Twine 2 source JSON format.
- `</tw-storydata>` closes at line 10224; a final `<script>` at 10225 would
  normally load/run the SugarCube runtime.

**Structure is fully intact; only attribute *values* and text *content* were
anonymized.** The tag tree, attribute names, and document order are preserved.

---

## 2. SugarCube-Specific Patterns

### 2.1 Macro Inventory (entity-encoded as `&lt;&lt;…&gt;&gt;`)

Because passage text is HTML-escaped in `<tw-passagedata>`, macros appear as
`&lt;&lt;macro&gt;&gt;`. Counts:

| Macro | Opens | Closes | Notes |
|---|---|---|---|
| `<<linkreplace>>` | 260 | 259 | **1 unclosed** — original bug or anonymization artifact |
| `<<set>>` | 119 | — | Always `<<set $varNNN identifier006 0>>` |
| `<<if>>` | 75 | (`<</if>>`) | Single-branch only — **no `<<else>>`/`<<elseif>>`** anywhere |
| `<<goto>>` | 53 | — | Always `<<goto [[identifierNNN]]>>` |
| `<<include>>` | 13 | — | Embed other passages |
| `<<macro001>>` | 75 | — | Custom macro — **never defined in passages**; def was in JS |

### 2.2 Variable & State System

- **65 story variables:** `$variable001` … `$variable065`. All appear to be
  numeric state flags (set to `0`, tested with `is 0`).
- **Anonymization of `to` operator:** `<<set $varNNN identifier006 0>>` decodes
  to `<<set $varNNN to 0>>`. The token `identifier006` (119 occurrences, always
  between `$var` and a value, always followed by `0`) is the anonymized SugarCube
  `to` assignment operator. (See `docs/core/macros.md:115` — SugarCube's
  idiomatic `<<set $x to value>>`.)
- **Reset-then-gate pattern:** A passage sets several flags to 0, then later
  content is gated on `<<if $varNNN is 0>>`. Example (lines 193–228):
  ```
  <<set $variable001 to 0>>  (lines 193–196, four vars reset)
  …
  <<if $variable002 is 0>> … <<macro001>>  (line 209)
  <<if $variable001 is 0>> … <<macro001>>  (line 213)
  ```
- **"All choices made" compound gate** (line 224): `<<if $variable004 is 0 and
  $variable001 is 0 and $variable002 is 0 and $variable003 is 0>>` — appears
  before an advance button, requiring all sub-choices exhausted first. This
  pattern recurs throughout (e.g. line 394, 731).
- **`$variable057` is the most-used flag (19×)** — likely a primary
  scene/progression tracker; gated on with `<<if $variable057 is 0>>` 13×.

### 2.3 Passage Types & Content Patterns

No special passage tags survive (all `tags="lorem-ipsum"`), but content reveals
several functional passage archetypes:

1. **Choice-hub passage** (e.g. lines 27–62): lists several
   `<<linkreplace "Lorem ipsum">><<goto [[identifierNNN]]>><</linkreplace>>`
   blocks — a menu of single-use choices, each navigating to a branch.
2. **Dialogue passage** (e.g. lines 63–94): media + `@@CharacterN: …@@` lines.
3. **Reset/state passage** (e.g. lines 193–196): only `<<set $varNNN to 0>>`.
4. **Include/advance passage** (e.g. lines 8298–8299, 10223–10224):
   `<<set $variable057 to 0>><<include [[0]]>>` — set flag then embed.
5. **2 truly empty passages** (line 7008) — likely placeholders or deprecated
   stubs.

### 2.4 Dialogue Markup: `@@` Aligned-Style Blocks

4,623 `@@` markers. The pattern `@@ Character1: <span style="">…</span>@@`
uses SugarCube's `@@…@@` **custom-style/aligned-text markup** (see
`docs/core/markup.md:715`: `@@style-list;Text@@`). Here it wraps per-speaker
dialogue in a block. 22 distinct speakers, heavily skewed to 4 leads:

| Speaker | Lines (approx) | Role |
|---|---|---|
| Character1 | 2,111 | Primary speaker |
| Character4 | 1,132 | Secondary |
| Character2 | 630 | Tertiary |
| Character3 | 518 | Tertiary |
| Character5–22 | 3–59 each | Minor/NPC |

### 2.5 Navigation & Media Patterns

- **Image-map navigation** (139 occurrences): `<a data-passage="" class="">
  <img src="media-placeholder" style="">` — a clickable image acting as a
  "continue"/advance button. `data-passage` is SugarCube's HTML-attribute
  passage-link directive (`docs/core/markup.md:277`).
- **Media display:** 767 `<img src="media-placeholder">`, 352
  `<video autoplay muted loop><source src="media-placeholder">` — the game
  uses autoplaying muted looping video extensively (atmospheric/cutscene).
  `<center>` wraps images/video for centering.
- **External resource link** (2×): `<a href="resource-placeholder">` — an
  outbound link, distinct from in-story navigation.

### 2.6 CSS Integration

- 11 `<style>` blocks in `<head>` (lines 9–19) — all blanked to
  `/* Lorem ipsum… */`.
- 1 embedded `<style role="" id="" type="">` inside `<tw-storydata>` (line 27).
- 5,812 inline `style=""` attributes on `<span>`/`<img>`/`<a>` elements — all
  emptied. The game clearly relied heavily on inline styling for per-element
  visual effects (e.g. coloring dialogue spans).

---

## 3. Anonymization Approach

The anonymization is **structural-preserving but content-obliterating**. It
kept the tag tree and attribute names while replacing every *value* with a
category-specific placeholder. This is ideal for analyzing *structure* but
destroys all *semantic* content.

### 3.1 Replacement Scheme

| Original | Replaced with | Scope |
|---|---|---|
| All prose/text | `Lorem ipsum dolor sit amet.` | Universal |
| Story title, meta | `Lorem ipsum dolor sit amet.` | `<title>`, `<meta>` |
| Story name | `Lorem ipsum` | `tw-storydata name=` |
| Passage names | `Lorem ipsum` | all 158 `tw-passagedata name=` |
| Link text | `Lorem ipsum` | all `<<linkreplace "…">>` |
| All CSS | `/* Lorem ipsum dolor sit amet. */` | all `<style>` blocks |
| All JS | `/* Lorem ipsum dolor sit amet. */` | all `<script>` blocks |
| Image sources | `media-placeholder` | all `<img src>` |
| External links | `resource-placeholder` | `<a href>` |
| Passage references | `identifier001`–`identifier061` | `<<goto [[…]]>>`, `<<include [[…]]>>` |
| Variable names | `$variable001`–`$variable065` | all `$` vars |
| Custom macro name | `macro001` | `<<macro001>>` |
| Operator `to` | `identifier006` | inside every `<<set>>` |
| Passage tags | `lorem-ipsum` | all `tags=` attrs |
| All other attrs | `""` (empty) | id, class, style, pid, ifid, format, position, size, startnode, creator, role, type, charset, options, zoom |

### 3.2 What Was Removed/Changed (identifying content)

- **Author names:** `creator=""`, `creator-version=""` emptied.
- **IFID:** `ifid=""` — the Twine Interactive Fiction ID (used by the save
  system) is blanked.
- **Story format:** `format=""`, `format-version=""` — normally `sugarcube-2`
  and a version string.
- **Title:** `<title>` and `<meta name>` → Lorem ipsum.
- **Comment:** line 7 HTML comment blanked.
- **Passage coordinates:** `position=""`, `size=""` — the Twine editor layout
  positions are gone (these are editor-only metadata, irrelevant to runtime).
- **All narrative content, character names, item names** — replaced.

### 3.3 What Remains Intact

- Full HTML document tree and nesting.
- `<tw-storydata>`/`<tw-passagedata>` element structure with correct attribute
  *names* (only values lost).
- SugarCube macro *syntax* (`<<…>>`, `<<if>>`, `<<set>>`, etc.) and entity encoding.
- Variable sigil `$` and the distinction of story (`$`) vs would-be-temp (`_`).
- `@@…@@` markup syntax (the wrapper survives; styles inside are blanked).
- `data-passage` attribute (navigation intent preserved; target blanked).
- Media element structure (`<img>`, `<video autoplay muted loop>`).
- **Quantitative structure:** relative counts of macros, variables, characters,
  media — useful for understanding the game's *shape*.
- The structural *relationships* between passages (which passages set which
  variables, which gate on which, which include which).

---

## 4. Interesting Mechanics, UI Patterns & Techniques

These are patterns a story-generation harness (like
`sugarcube-story-harness-for-ollama`) could learn from or explicitly model:

1. **Flag-reset-on-entry + conditional-advance (the core state pattern).**
   Entering a hub resets choice flags to 0 (`<<set $varNNN to 0>>`), each
   sub-choice is shown via `<<linkreplace>>`, and the "advance" button only
   appears once all flags are checked via a compound `<<if $a is 0 and $b is 0
   and $c is 0>>` gate. This is the game's primary interaction loop.

2. **`<<linkreplace>>` + `<<goto>>` as single-use choices.**
   `<<linkreplace "option text">><<goto [[branch]]>><</linkreplace>>` — a
   self-disabling link that immediately navigates. Simpler than `<<link>>` for
   pure branching; the `linkreplace` visually crosses out the used option.

3. **Custom `<<macro001>>` as a reusable "continue" widget.**
   Invoked 75×, always at the end of a content block (often after an `<<if>>`).
   Its definition (in JS) is gone, but usage shows it's a "render a continue/
   advance button" macro — a DRY pattern for the most-repeated UI element.
   A harness should let authors define such custom macros and reuse them.

4. **Block-level dialogue attribution via `@@…@@`.**
   `@@ CharacterN: <span style="">text</span>@@` wraps each speaker's line,
   giving consistent visual dialogue formatting without per-line CSS. The
   harness should support this idiom (SugarCube `@@` aligned-style blocks).

5. **Image-map navigation (`<a data-passage>` + `<img>`).**
   139× — clickable images as "continue" buttons, richer than text links. The
   `data-passage` attribute is the SugarCube-native way to make any HTML
   element navigate. A harness generating visual IF should model this.

6. **Autoplay muted looping video for atmosphere.**
   352 `<video autoplay muted loop>` elements — the game leans heavily on
   short looping video clips for scene-setting. Media-first storytelling.

7. **`<<include>>` for passage composition.**
   13× — embedding one passage inside another (e.g. shared content blocks,
   conditional snippets). The `<<if $variable057 is 0>><<include
   [[identifier047]]>><<macro001>>` pattern (line 6771) shows conditional
   inclusion of a sub-scene.

8. **No `<<else>>`/`<<elseif>>` — pure additive gating.**
   The game never uses else-branches; all logic is "show this if flag set,
   show that if flag unset." This is a deliberate minimal-branching design
   that's easy to generate but produces linear-with-optional-content flow.

9. **`<center>` for media centering.**
   Pervasive use of `<center>` (deprecated HTML but widely supported in
   SugarCube's renderer) for images/video. Simple, reliable layout.

10. **Dense, self-contained passages.**
    Each passage typically bundles: a media element (img/video), several
    `@@Character@@` dialogue lines, one or more `<<linkreplace>>` choices,
    a `<<set>>` block, and a conditional `<<macro001>>` advance. The passage
    is the unit of authorship — not split across many small passages.

---

## 5. What's Missing or Broken Due to Anonymization

These are defects that would prevent the file from running as-is in SugarCube,
or that obscure its structure. Some are anonymization artifacts; at least one
(`startnode`) may be a pre-existing issue.

| # | Issue | Line(s) | Severity |
|---|---|---|---|
| 1 | `startnode=""` on `<tw-storydata>` | 27 | **Fatal** — SugarCube needs a start passage PID; game won't load |
| 2 | All passage `name="Lorem ipsum"` | all 158 | **Fatal** — 158 name collisions; navigation impossible |
| 3 | All `<<goto>>`/`<<include>>` targets `identifierNNN` match no passage name | all goto/include | **Fatal** — all links broken |
| 4 | 5 references to `[[0]]` or `[[0 …]]` | 36, 7397, 7400, 8298, 9593–94, 10223 | Broken numeric refs (anonymization leftovers) |
| 5 | 1 unclosed `<<linkreplace>>` (260 open vs 259 close) | scattered | Parse error — either original bug or anonymization slip |
| 6 | `macro001` undefined — its JS definition was blanked | invoked 75×, def gone | All 75 invocations would throw "unknown macro" |
| 7 | All `<script>` blocks blanked | 8, 27, 10225 | **SugarCube engine entirely absent** — no runtime |
| 8 | All `<style>` blocks blanked | 9–19, 27 | No CSS — game would render unstyled |
| 9 | `ifid=""` | 27 | Save system non-functional (IFID required) |
| 10 | `format=""`, `format-version=""` | 27 | Loader can't identify story format |
| 11 | All inline `style=""` (5,812×) | all spans/imgs | Per-element visual effects lost |
| 12 | 2 completely empty passages | 7008 | Dead passages (likely stubs) |
| 13 | `data-passage=""` (139×) | all `<a>` nav | All image-map links point nowhere |
| 14 | All `<img src="media-placeholder">` (767×), `<video src>` (352×) | all media | All media missing — broken images/videos |

**Net effect:** The file is structurally valid HTML and a *parseable* Twine
archive, but it is **not runnable**. It serves purely as a *structural template*
showing how a real SugarCube game's passages, macros, variables, and media are
organized — not as a functional game.

---

## Appendix: Quick Reference — Key Lines

- **`<head>` script+styles:** lines 8–19 (12 blocks, all blanked)
- **Body UI scaffold:** lines 21–26
- **`<tw-storydata>` opening:** line 27
- **First passage (choice hub):** line 27 (continues to 62)
- **First `<<goto [[identifier001]]>>`:** line 31
- **First `<<set $variable001 to 0>>`:** line 193 (`identifier006` = `to`)
- **First `<<if>>` gate:** line 209
- **First `<<macro001>>`:** line 209
- **First `@@Character@@` dialogue:** line 70 (Character1)
- **First `<a data-passage>` image nav:** line 119
- **First `<video autoplay muted loop>`:** line 80
- **`$variable057` (primary flag) first set:** line 8298
- **Empty passages:** line 7008 (two consecutive)
- **`</tw-storydata>`:** line 10224
- **Trailing engine `<script>`:** line 10225

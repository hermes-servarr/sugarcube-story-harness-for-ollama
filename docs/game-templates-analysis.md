# Anonymized Example Game Analysis

**Date:** 2026-07-28
**Commit:** 81a5022 (origin/main)
**Files analyzed:**
- `examples/game_templates/example-structure.html` (10,227 lines, 691KB, 159 passages)
- `examples/game_templates/example-structure (2).html` (20,598 lines, 928KB, 487 passages)
- `examples/game_templates/example-structure (3).html` (52,693 lines, 3.6MB, 785 passages)

---

## 1. Anonymization Approach

The author ran these files through a parser that:

| What | How |
|---|---|
| All text content | Replaced with "Lorem ipsum dolor sit amet." |
| All attribute values | Emptied (`id=""`, `name=""`, `format=""`, `ifid=""`, `startnode=""`, `pid=""`, etc.) |
| Passage names | All replaced with "Lorem ipsum" |
| Passage tags | All replaced with "lorem-ipsum" |
| Variable names | Replaced with `$variable001` through `$variable242` (sequential) |
| Temp variables | Replaced with `_variable001` etc. |
| Function/identifier names | Replaced with `identifier001` etc. |
| Custom macro names | Replaced with `macro001` through `macro025` |
| Character dialogue labels | Replaced with `Character1` through `Character9` |
| Media references | Replaced with `media-placeholder` and `resource-placeholder` |
| tw-tag names | Replaced with "Lorem ipsum" |
| CSS content | Replaced with `/* Lorem ipsum dolor sit amet. */` |
| JS content | Replaced with `/* Lorem ipsum dolor sit amet. */` |
| SugarCube engine JS | **Completely stripped** (no SugarCube code remains) |
| HTML structure | Preserved (tags, nesting, data-twine-* elements) |

### Critical finding: these files are NOT playable

The anonymization stripped the SugarCube engine JavaScript and all CSS. A normal
compiled SugarCube HTML file (like the Cartographer's Dilemma) contains ~440KB of
SugarCube engine JS. These files have 66-99 bytes of script content total, all
"Lorem ipsum" comments. They are **structural skeletons** showing passage
organization and macro usage patterns, not runnable games.

### What is preserved and useful

- The full HTML element structure (head, body, tw-storydata, tw-passagedata)
- The number and nesting of passages
- Macro usage patterns (which macros, how often, how nested)
- Variable reference patterns (how many vars, how they're used)
- Conditional branching structure (if/elseif/else chains)
- Navigation patterns (linkreplace vs link vs goto)
- Widget definitions and invocations
- Media reference patterns (img, video, audio placeholders)
- Dialogue formatting patterns (@@Character1: ... @@)
- Input form usage (textbox, radiobutton, listbox, numberbox)

---

## 2. Per-Game Analysis

### Game 1: example-structure.html (10k lines, 159 passages)

**Type:** Visual novel with branching dialogue
**Character:** VN-style with `@@Character1: ... @@` dialogue labels (9 characters)
**Navigation:** `<<linkreplace>>` + `<<goto>>` (260 linkreplace, 53 goto)
**State:** 65 story variables, 61 identifiers
**Branching:** 75 if blocks, no elseif/else (simple conditionals)
**Media:** 767 media-placeholder references (heavy image/video use)
**Widgets:** None
**Custom macros:** 1 (`macro001`)
**Notable:** Uses `<<linkreplace>>` as primary interaction pattern (click text, replace with new content, then goto). Heavy video use (`<video autoplay muted loop>`).

### Game 2: example-structure (2).html (20k lines, 487 passages)

**Type:** Complex RPG with character systems
**Navigation:** Mix of `<<linkreplace>>` (832), `<<link>>` (68), `<<goto>>` (255)
**State:** 179 story variables, 121 temp variables, 90 identifiers
**Branching:** 1951 if, 1240 elseif, 1264 else (deep conditional trees)
**Widgets:** 14 widget definitions
**Custom macros:** 22 (`macro001` through `macro022`)
**Input forms:** textbox (4), radiobutton (16), listbox (4), numberbox (2)
**Other macros:** `<<timed>>` (20), `<<switch>>` (2), `<<addclass>>`, `<<remove>>`, `<<run>>` (3), `<<print>>` (79), `<<unset>>` (7), `<<nobr>>` (46)
**Notable:** Most macro-diverse game. Uses input forms for character creation. Heavy `<<include>>` (396) for reusable content. `nobr` tag on 46 passages.

### Game 3: example-structure (3).html (52k lines, 785 passages)

**Type:** Large-scale narrative game with media
**Navigation:** `<<link>>` (1578) + `<<goto>>` (528), no linkreplace
**State:** 242 story variables, 72 temp variables, 57 identifiers
**Branching:** 5293 if, 1427 elseif, 3853 else (very deep)
**Widgets:** 21 widget definitions
**Custom macros:** 25 (`macro001` through `macro025`)
**Input forms:** radiobutton (14)
**Other macros:** `<<timed>>` (101), `<<for>>` (47), `<<button>>` (62), `<<back>>` (46), `<<print>>` (317)
**Media:** 458 media-placeholder, 26 resource-placeholder references
**Notable:** Uses `<<for>>` loops (47 instances) - only game with loops. Heavy `<<button>>` usage. Uses `<<back>>` for navigation. 101 `<<timed>>` calls suggest animated sequences.

---

## 3. Gap Analysis: Harness vs Real Games

### Macro Vocabulary Gap

The harness currently generates 4 macro types. Real games use 25+:

| Macro | Harness | Game 1 | Game 2 | Game 3 | Gap |
|---|---|---|---|---|---|
| `<<set>>` | 19 | 119 | 2087 | 7613 | Used but under-scaled |
| `<<if>>` | 3 | 75 | 1951 | 5293 | Massively under-used |
| `<<elseif>>` | 0 | 0 | 1240 | 1427 | **Missing** |
| `<<else>>` | 3 | 0 | 1264 | 3853 | Under-used |
| `<<linkreplace>>` | 0 | 260 | 832 | 0 | **Missing** |
| `<<link>>` | 0 | 0 | 68 | 1578 | **Missing** |
| `<<goto>>` | 0 | 53 | 255 | 528 | **Missing** |
| `<<actions>>` | 17 | 0 | 0 | 0 | Harness-only, not used in real games |
| `<<include>>` | 0 | 13 | 396 | 107 | **Missing** |
| `<<widget>>` | 0 | 0 | 14 | 21 | **Missing** |
| `<<timed>>` | 0 | 0 | 20 | 101 | **Missing** |
| `<<for>>` | 0 | 0 | 0 | 47 | **Missing** |
| `<<button>>` | 0 | 0 | 8 | 62 | **Missing** |
| `<<print>>` | 0 | 0 | 79 | 317 | **Missing** |
| `<<switch>>` | 0 | 0 | 2 | 1 | **Missing** |
| `<<textbox>>` | 0 | 0 | 4 | 0 | **Missing** |
| `<<radiobutton>>` | 0 | 0 | 16 | 14 | **Missing** |
| `<<listbox>>` | 0 | 0 | 4 | 0 | **Missing** |
| `<<numberbox>>` | 0 | 0 | 2 | 0 | **Missing** |
| `<<nobr>>` | 0 | 0 | 46 | 0 | **Missing** |
| `<<back>>` | 0 | 0 | 1 | 46 | **Missing** |
| `<<run>>` | 0 | 0 | 3 | 2 | **Missing** |

### Key structural gaps

1. **`<<actions>>` is a dead end.** The harness uses `<<actions>>` for all choices, but none of the three real games use it. They use `<<link>>` + `<<goto>>` or `<<linkreplace>>` + `<<goto>>` instead. `<<actions>>` is deprecated in modern SugarCube and creates a different UX (disappearing links vs persistent links).

2. **No `<<include>>` for passage composition.** Real games compose passages from shared snippets (396 includes in Game 2). The harness generates monolithic passages with no shared content.

3. **No `<<widget>>` for reusable patterns.** Real games define widgets for repeated patterns (stat bars, character displays, UI elements). 14-21 widget definitions per game.

4. **No `<<linkreplace>>` for inline interaction.** Games 1 and 2 use this heavily (260, 832 instances) for click-to-reveal and click-to-advance patterns. The harness has no support for this.

5. **No `<<timed>>` for animation sequences.** Games 2 and 3 use timed macros (20, 101 instances) for animated text, delays, and scripted sequences.

6. **No input form macros.** Game 2 has character creation with `<<textbox>>`, `<<radiobutton>>`, `<<listbox>>`, `<<numberbox>>`. The harness has no support for player input forms.

7. **No `<<for>>` loops.** Game 3 has 47 for-loops for iterating over collections (inventory items, character stats, etc.).

8. **No `<<print>>` for dynamic content.** Games 2 and 3 use `<<print>>` extensively (79, 317) for displaying variable values, computed text, and dynamic content.

9. **Minimal conditional logic.** The harness uses 3 if blocks total. Real games use 75-5293. The harness doesn't generate `<<elseif>>` at all.

10. **No dialogue system.** Game 1 uses `@@Character1: ... @@` SugarCube inline styling for dialogue. The harness has no dialogue formatting support.

---

## 4. Ideas for Future Revision

### Priority 1: Navigation overhaul (high impact, moderate effort)
Replace `<<actions>>` with `<<link>>` + `<<goto>>` as the default navigation pattern. Add `<<linkreplace>>` support for inline interactions. This matches what real games actually do.

### Priority 2: Add `<<include>>` support (high impact, low effort)
Allow passages to include other passages by name. The harness already has `story.json` tracking passage relationships. Add a "snippet" passage type that can be included by multiple parent passages.

### Priority 3: Widget generation (high impact, high effort)
Add a widget definition system. When the harness detects repeated patterns (stat displays, character info, UI elements), generate a `<<widget>>` definition and invoke it instead of duplicating content.

### Priority 4: Richer conditionals (high impact, moderate effort)
Teach the LLM to generate `<<if>>/<<elseif>>/<<else>>` chains. The harness currently generates flat prose with minimal branching. Real games have deep conditional trees based on game state.

### Priority 5: `<<print>>` and dynamic content (medium impact, low effort)
Use `<<print>>` to display variable values in prose. Currently the harness hardcodes text. Real games interpolate `$variable` values.

### Priority 6: Input form support (medium impact, high effort)
For character creation or choice screens, support `<<textbox>>`, `<<radiobutton>>`, `<<listbox>>`, `<<numberbox>>`. The Character Creator template already shows these patterns.

### Priority 7: `<<timed>>` animation support (low impact, moderate effort)
For dramatic text reveals and scripted sequences. Not essential but adds polish.

### Priority 8: `<<for>>` loop support (medium impact, moderate effort)
For iterating over inventory, stats, and collections. Useful for RPG-style games.

### Priority 9: Dialogue formatting system (low impact, low effort)
Support `@@Character: ... @@` inline styling for dialogue. The harness currently has no dialogue formatting.

### Priority 10: Anonymization tool (low impact, low effort)
Build a tool that can anonymize a SugarCube HTML game while preserving the SugarCube engine JS (so the result is still playable). The current anonymization strips the engine, making the files non-functional as reference games.

---

## 5. What's Glaringly Missing (Kanban Candidates)

### A. The anonymized files are not playable
The anonymization stripped the SugarCube engine JS. These files cannot be opened in a browser and played. They're only useful as structural references. A proper anonymization would preserve the engine while stripping identifying content.

### B. The harness generates a tiny subset of SugarCube
4 macros vs 25+ in real games. `<<actions>>` is not used in any real game. The harness is generating a SugarCube subset that doesn't match real-world usage patterns.

### C. No passage composition system
Real games compose passages from shared snippets via `<<include>>` and `<<widget>>`. The harness generates flat, monolithic passages. This limits code reuse and makes generated games feel repetitive.

---

## 6. Additional Findings from Subagent Analysis

Detailed per-file reports:
- `docs/example-structure-analysis.md` (Game 1, 304 lines)
- Subagent report for Game 2 (inline, 236 lines)
- `examples/game_templates/example-structure-3-analysis.md` (Game 3, 328 lines)

### Game 1: VN-style click-to-reveal with heavy media
- Primary loop: reset flags -> `<<linkreplace>>` choices -> compound `<<if>>` gate to reveal advance button
- 352 inline `<video autoplay muted loop>` clips for atmospheric background
- 139 image-map navigation links (`<a data-passage>` + `<img>`)
- 22 character speakers via `@@CharacterN: ... @@` inline styling
- 1 unclosed `<<linkreplace>>` (260 opens vs 259 closes) - either original bug or anonymization artifact

### Game 2: OOP-style entity system with grid rendering
- Deeply nested state objects: `$variable003.identifier004`, `$variable027.identifier008.identifier072`
- 242 object literal initializations (centralized state setup, likely in a StoryInit-type passage)
- `identifier001(0,0) >= 0` called 486 times - a pervasive game-mechanic function (skill check, distance, difficulty)
- `macro020` called 100+ times with coordinates - a grid/map cell renderer
- `<<run $variable027.identifier008.identifier072(_variable128)>>` - methods stored inside state objects (OOP entities with behavior)
- 2D array indexing: `identifier088.identifier089[$variable056[0]][$variable056[0]]` - multidimensional lookup tables
- Computed damage scaling: `<<set _var *= $variable002.identifier030>>` followed by `Math.floor`-like function
- `<<timed 0.1s>>` for 100ms delay transitions between passages

### Game 3: Centralized init, widget-heavy, `<<link>>`+`<<replace>>` dominant
- `<<link>>` + `<<replace>>` as primary same-page interaction (1578 links, 3663 replaces), not passage navigation
- 21 widgets abstracting reusable rendering logic
- 25 custom macros including a function called 2,916 times (likely dice/random)
- 10 structured entity objects with 13-17 properties each
- `<<for>>` loops (47 instances) for iterating collections
- `<<button>>` (62) and `<<back>>` (46) for navigation
- 101 `<<timed>>` calls for animated sequences
- Color-coded feedback via `<font color="">` tags

### Cross-game patterns the harness should adopt

1. **Centralized state initialization** (all 3 games): A single passage (like StoryInit) sets up all game state with nested objects. The harness should generate a StoryInit passage that initializes all `$variable` state.

2. **Click-to-reveal as primary interaction** (Games 1 and 2): `<<linkreplace>>` is the dominant interaction, not page navigation. Players click to progressively reveal narrative without leaving the passage. The harness only generates `<<actions>>` (page navigation).

3. **`<<link>>` + `<<replace>>` for same-page updates** (Game 3): Instead of navigating to a new passage, links replace content on the current page. This is a completely different interaction model from what the harness generates.

4. **Widget abstraction** (Games 2 and 3): Reusable rendering logic is extracted into widgets (14-21 per game). The harness should detect repeated patterns and generate widgets.

5. **OOP entity objects** (Games 2 and 3): Game state uses deeply nested objects with methods. The harness currently uses flat `$has_discovered_power` boolean flags.

6. **Pervasive custom functions** (all 3 games): Games define custom functions/macros called hundreds or thousands of times. The harness has no custom function support.

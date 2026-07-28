# Anonymized Example Game Analysis

**Date:** 2026-07-28 (updated)
**Commits:** 81a5022 (initial), c98c1e0 (added CSS+JS), ece2dfc (updated again)
**Files analyzed (current state on origin/main):**
- `examples/game_templates/example-structure.html` (60,687 lines, 4.5MB, 785 passages) - large narrative game
- `examples/game_templates/example-structure (2).html` (10,247 lines, 1.5MB, 159 passages) - visual novel
- `examples/game_templates/example-structure (3).html` (29,502 lines, 1.9MB, 487 passages) - RPG with character systems

**NOTE:** File contents were swapped between commits. The current mapping is:
- `example-structure.html` = Game 3 (large narrative, 785 passages) WITH engine JS+CSS
- `example-structure (2).html` = Game 1 (VN, 159 passages) WITH engine JS+CSS
- `example-structure (3).html` = Game 2 (RPG, 487 passages) WITH engine JS+CSS

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
| CSS content (SugarCube default) | Anonymized: `selector001`-`selector138` for class/id names, all values zeroed, `color-placeholder` for colors, `resource-placeholder` for font URLs |
| JS content (engine) | Anonymized: ALL identifiers replaced with `identifier001`-`identifier999`, including JS builtins (`document`, `window`, `JSON`, `localStorage` etc), all strings to "Lorem ipsum", all numbers to 0 |
| JS content (user-defined) | Game-specific JS preserved in structure: 0-32KB per game, function/var patterns intact, jQuery patterns visible |
| SugarCube engine JS | **Present** (~630-696KB per file), fully anonymized but structurally intact |
| HTML structure | Preserved (tags, nesting, data-twine-* elements) |

### Critical finding: these files are NOT playable

The anonymization emptied `startnode`, all passage names, `format`, `format-version`, and `ifid`. Even though the SugarCube engine JS is present, the game cannot start because the start passage pointer is empty and all passages share the name "Lorem ipsum", making navigation impossible. All CSS values are zeroed (widths, heights, colors all 0 or `#000000`), so even if it ran, it would be visually broken.

### What is preserved and useful

- The full HTML element structure (head, body, tw-storydata, tw-passagedata)
- The SugarCube engine JS (630-696KB, anonymized but structurally intact)
- The SugarCube default CSS (~5KB, anonymized)
- Game-specific CSS (0-11KB inside tw-storydata, anonymized selectors but patterns visible)
- User-defined JavaScript (0-32KB per game, showing custom game logic patterns)
- The number and nesting of passages
- Macro usage patterns (which macros, how often, how nested)
- Variable reference patterns (how many vars, how they're used)
- Conditional branching structure (if/elseif/else chains)
- Navigation patterns (linkreplace vs link vs goto)
- Widget definitions and invocations
- Media reference patterns (img, video, audio placeholders)
- Dialogue formatting patterns (@@Character1: ... @@)
- Input form usage (textbox, radiobutton, listbox, numberbox)
- jQuery usage patterns in user JS (event binding, DOM manipulation)
- CSS structural patterns (@keyframes, @media, transitions, gradients, flexbox)

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
The anonymization emptied `startnode`, `ifid`, `format`, all passage names, and zeroed all CSS values. Even though the SugarCube engine JS is now present (~630-696KB), the game cannot start. A proper anonymization would keep `startnode`, `format`, `format-version`, unique passage names (hashed), and non-zero CSS values while stripping author-identifying content.

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

---

## 7. Engine JS and CSS Analysis (Updated Files)

### Engine JS Structure

All 3 files contain the full SugarCube engine JavaScript, anonymized:

| File | script[0] | script[1] (user JS) | script[2] | Total engine |
|---|---|---|---|---|
| example-structure.html (785 passages) | 227KB | 20KB | 450KB | 697KB |
| example-structure (2).html (159 passages) | 233KB | 0KB | 398KB | 631KB |
| example-structure (3).html (487 passages) | 233KB | 32KB | 397KB | 662KB |

- **script[0]**: Engine bootstrap + early initialization (~227-233KB)
- **script[1]**: User-defined JavaScript (0-32KB, game-specific custom code)
- **script[2]**: Main SugarCube engine body (~397-450KB)

### SugarCube Version Identification

Files B and C share identical engine script[0] (hash=5bb03f4ce98b) and CSS (hash=01fbce057f74), confirming the same SugarCube version. File A has different hashes, indicating a different version. All engines are larger than v2.37.3 (550KB), suggesting v2.37.x or newer.

| Known version | Total engine JS |
|---|---|
| v2.30.0 (Cartographer's Dilemma) | 440KB |
| v2.37.3 (manonamora templates) | 551KB |
| Example games (Files B+C) | 631KB |
| Example games (File A) | 677KB |

### Anonymization of Engine JS

The anonymization is extremely thorough. It replaced:
- ALL JavaScript identifiers (variable names, function names, object properties) with `identifier001`-`identifier999`
- ALL string literals with "Lorem ipsum"
- ALL numeric values with 0
- Even JS builtins (`document`, `window`, `JSON`, `localStorage`, `Math`) are replaced with identifiers
- CSS selectors replaced with `selector001`-`selector138`
- CSS colors replaced with `#000000` or `color-placeholder`
- Font URLs replaced with `resource-placeholder`

This means the engine JS is structurally intact (you can see the code flow, function definitions, control structures) but semantically opaque (you cannot tell what any function does).

### User-Defined JavaScript

| Game | User JS | Pattern |
|---|---|---|
| Game 1 (VN, 159 passages) | 0KB | No custom JS, pure SugarCube macros |
| Game 3 (narrative, 785 passages) | 20KB | 40 jQuery calls, 31 event handlers, 8 try/catch, heavy DOM event binding |
| Game 2 (RPG, 487 passages) | 32KB | 68 if blocks, 14 jQuery calls, 83 comment lines, logic-heavy with async patterns |

Key patterns:
- Games use jQuery for event binding and DOM manipulation beyond what SugarCube macros provide
- RPG game (32KB user JS) has the most complex custom logic: async patterns (.catch), regex validation, conditional rendering
- VN game needs no custom JS at all, everything is done via SugarCube macros
- User JS defines custom macros, event handlers, and game-specific state management

### Game-Specific CSS (inside tw-storydata)

| Game | Game CSS | Key patterns |
|---|---|---|
| Game 1 (VN, 159 passages) | 0KB | No custom CSS |
| Game 3 (narrative, 785 passages) | 5.6KB | 3 @import fonts, 33 selectors, font-family/size definitions, image positioning |
| Game 2 (RPG, 487 passages) | 10.8KB | 2 @keyframes, 14 transitions, 12 linear-gradients, 27 border-radius, 62 selectors, styled buttons, table styling |

The RPG game has the richest CSS: gradient buttons, animated elements, custom table styling, and 62 unique selectors. The harness currently generates no game-specific CSS.

### SugarCube Default CSS

All 3 files share the same SugarCube default CSS structure (~5KB):
- `@keyframes init-loading-spin` - loading spinner animation
- `@media` responsive rules
- Dialog overlay styles (`html[data-dialog] body{overflow:hidden}`)
- Sidebar/passage layout
- Transition and opacity animations

### Implications for the Harness

1. **The harness should generate user JS for complex games.** Real games with character systems (RPG) need 20-32KB of custom JavaScript beyond SugarCube macros. The harness currently generates zero user JS.

2. **The harness should generate game-specific CSS.** Real games have 5-11KB of custom CSS for fonts, buttons, tables, gradients, and animations. The harness currently generates none.

3. **Two SugarCube versions are in use.** The harness should pin to one version and ensure compatibility. The example games use a version newer than v2.37.3.

4. **jQuery is the primary user-JS pattern.** Games use jQuery for event binding and DOM manipulation, not vanilla JS. The harness should generate jQuery-compatible code.

5. **VN games can be macro-only.** The VN game (159 passages) has zero user JS and zero game CSS, proving that SugarCube macros alone can build a complete game. The harness could target this as the baseline complexity level.

# SugarCube 2 Documentation Analysis: Harness Improvement Opportunities

## Executive Summary

Analysis of all 40 SugarCube 2 documentation files (core/, api/, guides/) against the
sugarcube-story-harness-for-ollama codebase. The harness has solid foundational
SugarCube awareness (Twee format, core macros, state variables, link conventions)
but misses several capabilities that would improve generation quality, validation
coverage, and runtime fidelity.

---

## 1. SugarCube 2 Key Capabilities

### 1.1 Variable System

**Two variable scopes:**
- Story variables (`$` sigil): persisted in history, survive navigation, stored in saves
- Temporary variables (`_` sigil): per-turn only, not persisted, ideal for loop counters

**Variable naming rules:** sigil + letter/`$`/`_` as second char, then `A-Za-z0-9$_`

**Supported types in story variables:** boolean, number, string, null, undefined,
Array, Date, Map, Set, generic objects. NOT supported: circular references,
getters/setters, functions, symbol properties.

**Non-persistent storage:** `setup` object (author-owned, not saved), `window`
object (browser auto-globals, not saved).

**Assignment operators:** SugarCube `to` (idiomatic) and standard JS `=`, `+=`, `-=`, etc.

**Conditional operators:** `is`/`isnot` (strict), `eq`/`neq` (loose, not recommended),
`gt`/`gte`/`lt`/`lte`, `and`, `or`, `not`, `def`/`ndef` (defined/undefined check).

### 1.2 Markup System

- **Naked variables:** `$variable` in passage text auto-interpolates. Supports
  dot notation (`$obj.prop`) and bracket notation (`$arr[0]`, `$obj["key"]`).
  Complex expressions need `<<print>>`.
- **Links:** `[[Target]]`, `[[Text|Target]]`, `[[Target][Setter]]`,
  `[[Text|Target][Setter]]`. Arrow separators: `Text->Link`, `Link<-Text`.
  Setters are `<<set>>` expressions evaluated on click, separated by `;`.
- **Images:** `[img[src]]`, `[img[Text|src][Link][Setter]]`.
- **HTML attribute directives:** `sc-eval:attr` or `@attr` evaluates attribute
  value as TwineScript. `data-passage` for passage links on HTML elements.
  `data-setter` for setter expressions on HTML elements.
- **Escaping:** `"""..."""` (nowiki), `<nowiki>...</nowiki>`, `$$` (escape $ sigil).
- **Line continuation:** `\` at line start/end joins lines, removes whitespace.
- **Headings:** `!` through `!!!!!!` (h1-h6).
- **Styles:** `//em//`, `''strong''`, `__underline__`, `~~strike~~`, `""highlight""`,
  `@@text@@` (inline), `@@class;text@@`, `@@#id;text@@`.

### 1.3 Macro Catalog (by category)

**Variables:** `<<capture>>` (localize vars for async macros), `<<set>>`, `<<unset>>`

**Scripting:** `<<run>>` (alias for `<<set>>`), `<<script [language]>>` (JS or TwineScript)

**Display:** `<<=>>`/`<<print>>` (output expression), `<<->>` (HTML-escaped output),
`<<include>>` (embed passage), `<<nobr>>` (collapse newlines), `<<silent>>` (discard
output), `<<type>>` (typewriter effect), `<<do>>`/`<<redo>>` (dynamic content update,
v2.37.0)

**Control:** `<<if>>`/`<<elseif>>`/`<<else>>`, `<<for>>` (conditional + range forms),
`<<break>>`, `<<continue>>`, `<<switch>>`/`<<case>>`/`<<default>>`

**Interactive:** `<<button>>`, `<<checkbox>>`, `<<cycle>>`/`<<option>>`/`<<optionsfrom>>`,
`<<link>>`, `<<linkappend>>`, `<<linkprepend>>`, `<<linkreplace>>`, `<<listbox>>`,
`<<numberbox>>`, `<<radiobutton>>`, `<<textarea>>`, `<<textbox>>`

**Navigation:** `<<back>>`, `<<return>>`, `<<goto>>`, `<<actions>>` (DEPRECATED v2.37.0),
`<<choice>>` (DEPRECATED v2.37.0)

**DOM:** `<<addclass>>`, `<<append>>`, `<<copy>>`, `<<prepend>>`, `<<remove>>`,
`<<removeclass>>`, `<<replace>>`, `<<toggleclass>>`

**Audio:** `<<audio>>`, `<<cacheaudio>>`, `<<createaudiogroup>>`, `<<createplaylist>>`,
`<<masteraudio>>`, `<<playlist>>`, `<<removeaudiogroup>>`, `<<removeplaylist>>`,
`<<waitforaudio>>`

**Timing:** `<<timed>>`/`<<next>>`, `<<repeat>>`, `<<stop>>`, `<<done>>`

**Widgets:** `<<widget name [container]>>` (create custom macros using markup),
`_args` (widget arguments), `_contents` (container widget body)

### 1.4 Functions

- `clone()` - deep copy (critical for avoiding reference sharing in story vars)
- `either()` - random selection from arguments/arrays
- `forget()` / `memorize()` / `recall()` - persistent metadata (survives restarts,
  not saves; ideal for achievements, NG+ data)
- `hasVisited()` / `lastVisited()` - passage history queries
- `passage()` / `previous()` - current/previous passage name
- `random()` / `randomFloat()` - random numbers (seedable PRNG via State.prng)
- `tags()` - get passage tags
- `time()` - ms since passage rendered
- `turns()` - turns elapsed
- `visited()` - visit count for current passage
- `setPageElement()` - render passage into DOM element
- `importScripts()` / `importStyles()` - load external resources

### 1.5 Special Names

**Code passages (not navigated to):**
- `StoryInit` - pre-story initialization (variable defaults)
- `PassageReady` / `PassageDone` - pre/post passage display tasks
- `PassageHeader` / `PassageFooter` - prepended/appended to each passage
- `StoryCaption` - UI bar caption content
- `StoryMenu` - UI bar menu items (links only)
- `StoryDisplayTitle` - dynamic title (v2.31.0)
- `StoryInterface` - replace default UI (must contain `#passages` element)
- `StoryTitle` - story title (used for storage ID, no markup)
- `StoryAuthor`, `StoryBanner`, `StorySubtitle` - UI bar sections

**Code tags (passages not navigated to):**
- `init` - initialization passage (v2.36.0, for add-ons)
- `widget` - widget definitions passage
- `script` - JavaScript (Twine 1/Twee only)
- `stylesheet` - CSS (Twine 1/Twee only)
- `Twine.audio` / `Twine.image` / `Twine.video` / `Twine.vtt` - media passages

**Special tags:**
- `nobr` - collapse newlines in passage
- `bookmark` - DEPRECATED v2.37.0

### 1.6 Events (Navigation Lifecycle)

In processing order:
1. `:passageinit` - before state history modification
2. `PassageReady` special passage
3. `:passagestart` event - before rendering
4. `PassageHeader` special passage
5. Passage renders
6. `PassageFooter` special passage
7. `:passagerender` event - after rendering
8. `PassageDone` special passage
9. `:passagedisplay` event - after display
10. `:uiupdate` event - UI bar update
11. `:passageend` event - end of navigation

Dialog events: `:dialogopening`, `:dialogopened`, `:dialogclosing`, `:dialogclosed`

### 1.7 APIs

- **State API:** `State.variables`, `State.temporary`, `State.history`,
  `State.active`, `State.passage`, `State.turns()`, `State.prng` (seedable PRNG)
- **Story API:** `Story.get(name)`, `Story.has(name)`, `Story.passages`
- **Passage API:** `Passage.name`, `Passage.tags`, `Passage.text`, `Passage.domId`
- **Save API:** `Save.autosave`, `Save.browser`, `Save.index`, `Save.save()`, `Save.load()`
- **Setting API:** `Setting.add()`, `Setting.save()`, `Setting.load()` - player settings UI
- **Config API:** extensive configuration (navigation, macros, passages, audio, UI)
- **Dialog API:** `Dialog.create()`, `Dialog.open()`, `Dialog.close()`
- **UI API:** `UI.updateBar()`, `UI.alert()`, `UI.restart()`, `UI.saves()`, `UI.settings()`
- **UIBar API:** `UIBar.destroy()`, `UIBar.stow()`, `UIBar.unstow()`
- **Engine API:** `Engine.play()`, `Engine.backward()`, `Engine.forward()`,
  `Engine.restart()`, `Engine.restore()`
- **Macro API:** `Macro.add()`, `Macro.delete()`, `Macro.get()`, `Macro.has()`
- **Template API:** `Template.add()` - custom `?name` text templates (v2.29.0)

---

## 2. Current Harness SugarCube Awareness

### 2.1 What the harness does well

- **Twee format:** Correct `:: passage_name [tags]` syntax
- **State variables:** Uses `<<set $var to value>>` with proper `to` operator
- **Link conventions:** Three-tier rendering (wikilink / `<<link>>` with state /
  `<<link>>` with skill check) matches SugarCube idioms
- **State scoping:** Story variables (`$`) for persistent state, properly initialized
  in StoryInit passage
- **Special passages:** Generates StoryInit (variable defaults), StoryData (IFID,
  format, start), StoryTitle
- **Macro pairing validation:** Quote-aware stack-based nesting checker for
  container macros
- **State variable validation:** Forward-reachability analysis for undeclared vars
- **Passage types:** Maps internal types (normal, hub, room, dialogue, conditional,
  random, event, random_event, ending) to SugarCube macro patterns
- **Event guards:** Uses `visited()` for one-shot events, `random(1,100)` for
  random events, `<<goto>>` for routing

### 2.2 Macro container set currently validated

```
if, for, switch, widget, link, button, capture, silently, nobr,
append, prepend, replace, linkappend, linkprepend, linkreplace,
timed, repeat, type, createplaylist, createaudiogroup
```

---

## 3. Gaps and Improvement Opportunities

### Priority 1 (High) - Correctness and Compatibility

#### 3.1 `<<actions>>` macro is DEPRECATED (v2.37.0)

**Location:** `passage.py` `_render_actions_block()` and hub passage rendering

**Issue:** The harness uses `<<actions>>` for hub passages. SugarCube v2.37.0
deprecated this macro. The config targets v2.36.1 so it currently works, but
any version bump will break hub rendering silently.

**Recommendation:** Replace `<<actions>>` with per-choice `<<link>>` rendering
using `<<if hasVisited("target")>>` to hide visited links, or use the newer
`<<do>>`/`<<redo>>` pattern (v2.37.0). Alternatively, use `<<linkreplace>>`
for single-use hub options.

#### 3.2 `<<silently>>` macro is DEPRECATED (v2.37.0)

**Location:** `validation.py` MACRO_CONTAINERS

**Issue:** `<<silently>>` is in the container set but deprecated. `<<silent>>`
(replacement) is NOT in the container set.

**Recommendation:** Add `silent` to MACRO_CONTAINERS. Keep `silently` for
backward compatibility but mark it as deprecated in any generated content.

#### 3.3 Missing container macros in validation

**Location:** `validation.py` MACRO_CONTAINERS

**Issue:** Several container macros are missing from the validation set:
- `do` / `redo` (v2.37.0) - `<<do>>` is container, `<<redo>>` is not
- `script` (v2.0.0) - `<<script>>...<</script>>` is a container
- `done` (v2.35.0) - `<<done>>...<</done>>` is a container
- `silent` (v2.37.0) - replacement for `<<silently>>`
- `checkbox`, `cycle`, `listbox`, `radiobutton`, `textarea`, `textbox`,
  `numberbox` - these are NOT containers (self-closing), so correctly absent
- `createaudiogroup` - present, correct
- `optionsfrom` - NOT a container (child of cycle/listbox), correctly absent

**Recommendation:** Add `do`, `script`, `done`, `silent` to MACRO_CONTAINERS.

#### 3.4 `<<choice>>` macro is DEPRECATED (v2.37.0)

**Location:** Not used by harness, but if the LLM generates it, no warning.

**Recommendation:** Add a validation check for deprecated macros in generated
passages: `<<actions>>`, `<<choice>>`, `<<silently>>`, `<<bookmark>>` tag.

#### 3.5 Variable scoping in prompts

**Location:** `prompts.py` - all prompt builders

**Issue:** Prompts never mention temporary variables (`_` sigil). The LLM
generates state as `$variable = value` but has no guidance on when to use
temporary variables for loop counters, intermediate calculations, or
turn-local state. This leads to story variable bloat.

**Recommendation:** Add SugarCube variable guidance to prompts:
- Use `$` variables for persistent story state (flags, inventory, relationships)
- Use `_` variables for transient values (loop counters, temp calculations)
- Use `setup` object for static data (item definitions, NPC templates)
- Use `memorize()`/`recall()` for cross-playthrough data (achievements, NG+)

### Priority 2 (Medium) - Generation Quality

#### 3.6 No SugarCube markup guidance in prompts

**Location:** `prompts.py`

**Issue:** Prompts ask for PROSE/CHOICES but never mention SugarCube markup
conventions. The LLM might:
- Use markdown `**bold**` instead of `''bold''`
- Use markdown `*italic*` instead of `//italic//`
- Not know about naked variable interpolation (`$name` in prose)
- Not know about `<<print>>` for complex expressions
- Not use `<<if>>` for conditional text within prose

**Recommendation:** Add a compact SugarCube markup cheat sheet to prompts,
especially the full prompt mode. Key points:
- `''bold''` for emphasis, `//italic//` for emphasis
- `$variable` auto-interpolates in prose
- `<<if $var>>text<</if>>` for conditional prose
- `<<print $obj.property>>` for complex expressions
- `<<include "passage">>` for shared content

#### 3.7 No `<<widget>>` awareness

**Location:** No support anywhere in harness

**Issue:** Widgets are SugarCube's custom macro system. They let authors
define reusable content macros using only markup (no JS). The harness
generates no widget passages and prompts don't mention them. Widgets are
ideal for:
- Repeated NPC dialogue patterns (`<<say "NPC">>text<</say>>`)
- Status display (`<<stats>>`)
- Repeated UI elements (`<<inventory>>`)
- Conditional pronouns (`<<he>>`/`<<she>>`)

**Recommendation:**
1. Add `widget` as a passage type or tag the harness recognizes
2. Generate a widget passage for repeated patterns the LLM identifies
3. Add widget guidance to prompts for the full prompt mode
4. Add `widget`-tagged passage detection to compile pipeline

#### 3.8 No `<<include>>` usage for shared content

**Location:** `passage.py`

**Issue:** The harness generates every passage as a standalone block.
`<<include>>` is SugarCube's passage embedding macro. It's ideal for:
- Shared location descriptions
- Repeated UI elements (stat bars, inventory)
- Common narrative beats
- Header/footer content per passage type

**Recommendation:** Consider an "include" passage type or auto-generate
shared description passages that can be `<<include>>`d by multiple passages.

#### 3.9 No `<<capture>>` awareness for async macros

**Location:** `passage.py` dialogue/random rendering

**Issue:** When `<<link>>` body uses loop variables or variables that change
between creation and click, `<<capture>>` is needed. The harness generates
`<<link>>` with `<<set>>` inside but never wraps in `<<capture>>`. This is
fine for the current simple patterns but will break if the LLM generates
links inside `<<for>>` loops.

**Recommendation:** Add `<<capture>>` wrapping when generating links inside
loops or when state writes reference variables that may change.

#### 3.10 No `<<type>>` (typewriter) macro support

**Issue:** The `<<type>>` macro (v2.32.0) creates a typewriter effect. It's
a popular narrative technique. The harness doesn't expose this as a passage
type option or prompt suggestion.

**Recommendation:** Add an optional "typing effect" flag to passage generation
that wraps prose in `<<type 40ms>>...<</type>>`.

#### 3.11 No `<<timed>>`/`<<repeat>>` narrative patterns

**Issue:** These macros enable time-based narrative (delayed reveals,
countdowns, recurring events). The harness doesn't model time-based
passage behavior.

**Recommendation:** Consider a "timed" passage attribute that generates
`<<timed>>` blocks for delayed content reveals.

### Priority 3 (Medium) - Validation Improvements

#### 3.12 No `<<print>>` / naked variable expression validation

**Location:** `validation.py`

**Issue:** The validator checks macro pairing and state variable reachability
but doesn't validate:
- Naked variable references in prose (`$undefined_var` in passage text)
- `<<print $expression>>` references to undefined variables
- `<<if $undefined_var>>` conditions

**Recommendation:** Extend `scan_state_reads()` to also scan for naked
`$variable` patterns in passage prose (outside macro tags and HTML comments).

#### 3.13 No setter expression validation

**Location:** `validation.py`

**Issue:** Link setters (`[[Target][$var to value]]`) and `<<link>>` body
`<<set>>` expressions are not validated for:
- Valid variable names (matching sigil rules)
- Type consistency with declared variable types
- Reference to undefined variables in compound expressions

**Recommendation:** Parse setter expressions and validate against
`state_variables` declarations.

#### 3.14 No `<<if>>` condition expression validation

**Issue:** `<<if $var gt 5>>` conditions reference variables that may be
undefined. The current `scan_state_reads` only looks at `$` prefixed tokens
but may miss them inside `<<if>>` conditionals if they use complex expressions.

**Recommendation:** Ensure `scan_state_reads` covers all expression contexts:
`<<if>>`, `<<elseif>>`, `<<switch>>`, `<<set>>` right-hand side, `<<print>>`,
link setters, and `@` attribute directives.

#### 3.15 No deprecated macro/feature detection

**Issue:** No check for deprecated features that may break on version upgrade:
- `<<actions>>` (deprecated v2.37.0)
- `<<choice>>` (deprecated v2.37.0)
- `<<silently>>` (deprecated v2.37.0)
- `bookmark` tag (deprecated v2.37.0)
- `StoryShare` passage (deprecated v2.37.0)
- `postdisplay`/`postrender`/`predisplay`/`prehistory`/`prerender` task objects
  (deprecated v2.31.0)

**Recommendation:** Add a `check_deprecated_features()` validation check that
warns when deprecated macros, tags, or special passages appear in generated
content.

### Priority 4 (Low) - Advanced Features

#### 3.16 No Template API awareness

**Issue:** SugarCube's `Template` API (v2.29.0) lets authors define `?name`
text templates that auto-expand in passage text. Useful for:
- Random flavor text (`?weather` expands to a random weather description)
- Character speech patterns (`?greeting_npc1`)
- Repeated descriptions

**Recommendation:** Document this as a future enhancement. The harness could
auto-generate templates for recurring descriptive patterns.

#### 3.17 No `<<textbox>>`/`<<checkbox>>` input macro support

**Issue:** SugarCube has rich input macros for player input. The harness
doesn't model passages that collect player input (character creation,
name entry, preference selection). These use quoted variable name syntax:
`<<textbox "$name" "default">>`.

**Recommendation:** Add a "form" or "input" passage type that generates
input macros and a submit `<<link>>` that captures the values and navigates.

#### 3.18 No `Setting` API integration

**Issue:** SugarCube's Setting API creates player options in the settings
menu (difficulty, text speed, content warnings). The harness doesn't expose
this. For AI-generated stories, content warning settings could gate mature
content.

**Recommendation:** Add a settings generation step that creates a
StorySettings passage with `Setting.add()` calls for configurable options.

#### 3.19 No `StoryInterface` / custom UI support

**Issue:** `StoryInterface` special passage replaces SugarCube's default UI.
The harness always uses the default UI bar. For some story types (VN-style,
RPG with stats panel), a custom UI would be better.

**Recommendation:** Add an optional `story_interface` config field that
generates a `StoryInterface` passage with a custom layout.

#### 3.20 No `State.prng` seedable PRNG awareness

**Issue:** SugarCube supports seedable deterministic PRNG via `State.prng.init()`.
The harness uses `random()` and `either()` which become deterministic when
seeded. This could enable reproducible playthroughs for testing.

**Recommendation:** Add an optional PRNG seed config that initializes the
PRNG in StoryInit, enabling deterministic playthrough validation.

#### 3.21 No `memorize()`/`recall()` metadata store usage

**Issue:** The persistent metadata store (survives browser restarts, not in
saves) is ideal for tracking achievements, playthrough stats, or NG+ data.
The harness doesn't use this.

**Recommendation:** Add achievement/metadata tracking to StoryInit and
passage generation for cross-playthrough persistence.

#### 3.22 No passage tag awareness beyond arc routing

**Issue:** The harness tags passages with `[arc_name passage_type]`. SugarCube
uses tags for:
- CSS styling (`body.tag-forest` applies styles when a `forest`-tagged passage
  is active)
- Passage filtering via `Story.lookup()` and `tags()`
- `nobr` special tag for newline collapsing

**Recommendation:**
1. Add optional mood/atmosphere tags that the LLM suggests
2. Generate CSS classes for tagged passages
3. Add `nobr` tag option to config for compact prose passages

---

## 4. Prioritized Recommendation Summary

| Priority | Area | Recommendation | Effort |
|----------|------|----------------|--------|
| P1-Critical | Compatibility | Replace `<<actions>>` with link-based hub rendering (deprecated v2.37.0) | Medium |
| P1-Critical | Validation | Add `silent`, `do`, `script`, `done` to MACRO_CONTAINERS | Trivial |
| P1-Critical | Validation | Add deprecated macro/feature detection check | Small |
| P1-High | Generation | Add SugarCube variable scoping guidance to prompts ($ vs _ vs setup) | Small |
| P1-High | Generation | Add SugarCube markup cheat sheet to full/JSON prompts | Small |
| P2-Medium | Generation | Add `<<widget>>` support (widget-tagged passages, prompt guidance) | Medium |
| P2-Medium | Generation | Add `<<capture>>` wrapping for links inside loops | Small |
| P2-Medium | Validation | Extend state-read scanning to naked variables in prose | Small |
| P2-Medium | Validation | Validate setter expressions and `<<if>>` conditions | Medium |
| P2-Medium | Generation | Add `<<include>>` passage type for shared content | Medium |
| P3-Low | Generation | Add `<<type>>` typewriter effect option | Small |
| P3-Low | Generation | Add `<<timed>>`/`<<repeat>>` time-based narrative patterns | Medium |
| P3-Low | Generation | Add input macro support (`<<textbox>>`, `<<checkbox>>`) | Medium |
| P3-Low | Generation | Add `Setting` API for player-configurable options | Medium |
| P3-Low | Generation | Add `StoryInterface` custom UI option | Medium |
| P3-Low | Generation | Add PRNG seeding for deterministic playthroughs | Small |
| P3-Low | Generation | Add `memorize()`/`recall()` achievement tracking | Small |
| P3-Low | Generation | Add passage tag awareness (mood tags, nobr, CSS) | Small |
| P3-Low | Generation | Add Template API (?name) support | Medium |

---

## 5. Key Patterns the Harness Should Teach the LLM

### 5.1 Variable conventions
```
// Persistent story state
<<set $has_met_king to true>>
<<set $gold to $gold + 50>>

// Temporary (per-turn only, not saved)
<<set _i to 0>>
<<set _result to random(1, 20)>>

// Static data (not saved, not history)
<<run setup.items["sword"] = { name: "Sword", damage: 5 }>>
```

### 5.2 Link patterns
```
// Plain navigation
[[Go north|north_passage]]

// State-setting navigation
[[Take the key|key_room][$has_key to true]]

// Macro link with code execution
<<link "Open door" "next_room">><<set $door_open to true>><</link>>

// One-shot link (deactivates after click)
<<linkreplace "Look closer">>You see scratch marks.<</linkreplace>>

// Append-on-click (expands text)
<<linkappend "The letter reads">> "Beware the rabbit."<</linkappend>>
```

### 5.3 Conditional text in prose
```
The door is <<if $door_open>>open, letting in a cold draft<<else>>firmly shut<</if>>.

<<switch visited()>>
<<case 1>>You enter the tavern for the first time.
<<case 2>>You return to the familiar tavern.
<<default>>Yet again, the tavern.
<</switch>>
```

### 5.4 Naked variable interpolation
```
"Hello, $player_name," the innkeeper says.
You have $gold coins.
$npc_name looks at you with $npc_eyes_color eyes.
// Complex expressions need <<print>>:
You weigh <<print $weight.toFixed(1)>> kg.
```

### 5.5 Widget definition (for repeated patterns)
```
:: Widget Definitions [widget]
<<widget "pronoun">>
<<if $pc_sex eq "male">>he<<elseif $pc_sex eq "female">>she<<else>>they<</if>>
<</widget>>

// Usage in any passage:
"Is <<pronoun>> coming?"
```

### 5.6 History-aware passages
```
<<if hasVisited("Castle")>>
You remember the castle's cold stone walls.
<</if>>

<<if not hasVisited("Tavern")>>
You've never been to a tavern before.
<</if>>

<<if visited() gt 1>>
You've been here <<print visited()>> times now.
<</if>>
```

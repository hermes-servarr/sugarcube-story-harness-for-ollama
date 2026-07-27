# HTML Template Verification Report & Feature Catalog

**Task:** t_1d39efd8
**Date:** 2026-07-27
**Repo:** /opt/data/sugarcube-story-harness-for-ollama (branch: feat/templates-and-docs-integration)
**Upstream:** github.com/manonamora/Twine-Template (commit 3f8fa40, 2026-01-24)
**License:** CC-BY (by manonamora)
**Target format:** SugarCube v2.37.3

---

## 1. Verification Summary

All 7 compiled HTML template files match the upstream repository **byte-for-byte**. Source files (.tw, .js, .css) have LF line endings locally vs CRLF upstream (cosmetic, content-identical after normalization), with two minor content differences in source-only files that do not affect the compiled HTML.

### File Size Verification

| Template | HTML (local) | HTML (upstream) | Match |
|---|---|---|---|
| Character Creator | 841,357 | 841,357 | YES |
| One Page | 652,077 | 652,077 | YES |
| Settings | 645,616 | 645,616 | YES |
| Simple Book | 656,911 | 656,911 | YES |
| Space-Tech UI | 658,079 | 658,079 | YES |
| Title Page | 632,339 | 632,339 | YES |
| VN-lite RPG | 638,452 | 638,452 | YES |

All 7 HTML files: **VERIFIED CURRENT**.

### Source File Differences

Source files are consistently ~2-4% smaller locally due to LF vs CRLF line endings. After normalizing line endings, content is identical **except**:

1. **One Page Template.tw**: Missing one comment line (`<!-- The container for everything is #story -->`). HTML unaffected.
2. **Settings.tw**: Three minor differences:
   - Font type list says "Monospace" locally vs "OpenDyslexic" upstream (the JS and HTML both use "Monospace", so the .tw is consistent with the compiled HTML locally)
   - Extra `[[About Twine and SugarCube|About]]` link locally
   - `<hr>` vs `<hr>\` line-continuation difference

**Assessment:** These source-only differences are cosmetic and do not affect the compiled HTML output. The HTML files (the actual usable artifacts) are current.

### Upstream Files Not Present Locally (by design)

- All `.zip` archive copies (redundant with HTML)
- All `2.36 Version/` archived older versions
- `Minimalist (WIP)` template (incomplete upstream, not yet released)
- `Unofficial Templates/Phone Retro MailBox.tw` (community contribution, not part of the itch.io pack)
- `SugarCube/README.md`, top-level `README.md`, `ChangeIFID.md`, `TODO and notes.txt`

These omissions are appropriate for a curated template collection.

---

## 2. Feature Catalog

### 2.1 Template Overview

| # | Template | Category | Upstream Path | Passages | Key Feature |
|---|---|---|---|---|---|
| 1 | Character Creator | Code Template | SugarCube/Code Template/Character Creator | 7+ source files | Multi-page character creation flow with widgets |
| 2 | Settings | Code Template | SugarCube/Code Template/Settings | 8 passages | Settings API showcase (range, toggle, list) |
| 3 | One Page | UI Template | SugarCube/UI Templates/One Page | 10 passages | Single-page UI with dropdown menu |
| 4 | Simple Book | UI Template | SugarCube/UI Templates/Simple Book | 11 passages | Book-like UI with side menus + FontAwesome |
| 5 | Space-Tech UI | UI Template | SugarCube/UI Templates/Space-Tech-UI | 13 passages | Dual-theme (Space/Tech) with stats bars + widgets |
| 6 | Title Page | UI Template | SugarCube/UI Templates/Title Page | 10 passages | Multiple title page layout variants |
| 7 | VN-lite RPG | UI Template | SugarCube/UI Templates/VN-lite RPG | 11 passages | Visual-novel layout with character images |

### 2.2 SugarCube StoryData Metadata

All templates use:
- `format: "SugarCube"`
- `format-version: "2.37.3"` (Settings .tw source says 2.36.1 but compiled HTML targets 2.37.3)
- `ifid: "C15CE33F-61F6-4909-BB59-73EE7A3D57B1"` (shared placeholder IFID; each game must change this)
- `start: "Start"`

**Harness generation consideration:** The IFID must be regenerated for each new story. The format-version should be set to the SugarCube version bundled in the harness.

### 2.3 Per-Template Feature Catalog

---

#### 2.3.1 Character Creator Template

**Structure:** Multi-file Twee source (7 .tw files + 1 .js + 1 .css) compiled into a single HTML.

**Passages (from source files):**
- `StoryInit` - Initializes complex object/array variables ($mc, $hair, $face, $skin, $body, $scars, $aid, $family, $stat, $statusStat, $pages)
- `StoryCaption` - Sidebar with Lexicon, Credits, Statistics buttons (conditional)
- `Start` - Welcome page with link to Index-CC
- `About` - General guidance
- `Lexicon` - IF/PC/NPC/RO glossary
- `Statistics` - Progress bars for personality and wealth stats
- `Credits` - Attribution
- `Index-CC` - Main trait selection grid (name, nickname, surname, gender, pronouns, age, eyes, hair, facial features, skin, build, scars, procedures, body mods, makeup, personality, class, background, RO gender, family, pets)
- `CC-Check` - Confirmation/review page with change-option popups
- `CC-Confirm` - Final confirmation with timed restart

**SugarCube-specific elements:**
- **Macros:** `<<widget>>` (extensive: Randomiser, PreSet, CheckIfDone, PersoBars, PopupNameChange, PopupGenderChange, etc.), `<<button>>`, `<<link>>`, `<<if>>/<<elseif>>/<<else>>`, `<<set>>`, `<<unset>>`, `<<timed>>`, `<<run>>`, `<<include>>`, `<<print>>`, `<<back>>`, `<<return>>`
- **Functions/APIs:** `State.getVar()`, `State.setVar()`, `Engine.restart()`, `passage()`, `tags()`, `ndef` operator, `isnot` operator
- **Custom JS:** `window.SugarCubeInput()` function for slider-to-variable binding (from HiEv's sample code), `:passagerender` event handler
- **Data structures:** Heavy use of SugarCube objects ($mc.name, $mc.gender, $hair.length, $hair.colour, $skin.undertone, $body.height, etc.)
- **CSS hooks:** `#passages`, `.index-flex`, element IDs for each trait section

**Harness considerations:**
- Most complex template (47KB Widget.tw alone)
- Uses base SugarCube only (no custom macros in JS except slider helper)
- Pattern: Multi-step character creation with review/confirm flow
- Variables: Deeply nested objects for character data
- Passage tags: `nobr` for widget passages

---

#### 2.3.2 Settings Template

**Structure:** Single .tw + JavaScript.js + CSS.css. Uses standard SugarCube UI (no custom StoryInterface).

**Passages:**
- `Start` - Overview of all settings with links to demo pages
- `StoryMenu` - Standard SugarCube menu (Credits link)
- `Animation` - Demo: `<<type>>` macro + CSS class toggle
- `Volume` - Demo: `<<audio>>` macro with play/stop
- `Theme` - Demo: heading/list/table styling showcase
- `Basic Macros` - Demo: all SugarCube input macros
- `Credits` - Attribution

**SugarCube-specific elements:**
- **Settings API (JavaScript.js):**
  - `Setting.addHeader()` - 3 headers: "Text Display", "Mode and Volume", "Accessibility", "Save Settings"
  - `Setting.addList()` - fontFamily (Serif/Sans Serif/Monospace), fontSize (75%/100%/125%/150%), lineheight (75%/100%/125%/150%), theme (Light/Dark)
  - `Setting.addRange()` - masterVolume (0-10, step 1)
  - `Setting.addToggle()` - textalign, textanim, notif, autosave, autoname
- **Config API:** `Config.saves.isAllowed` (with `Save.Type.Auto` check + `noreturn` tag restriction), `Config.saves.maxAutoSaves`, `Config.saves.descriptions` (autoname with `State.getVar()` + `passage()`)
- **Save API:** `Save.Type.Auto`
- **Macros:** `<<type>>`, `<<audio>>`, `<<button>>`, `<<link>>`, `<<if>>`, `<<cacheaudio>>`, `<<notify>>` (Chapel's custom macro), `<<timed>>`
- **Custom macros (JS):** Chapel's `notify` macro (v1.1.1), inline in JavaScript.js
- **Audio:** `<<cacheaudio "song" "assets/song.wav">>` in StoryInit, `SimpleAudio.volume()` in volume handler
- **CSS hooks:** `.serif`, `.sansserif`, `.monospace`, `.lh-small/.lh-medium/.lh-large/.lh-biggest`, `.justified`, `.rev` (theme), `.nogif` (animation), `.nonotif`
- **jQuery:** `$(document).on(":passagedisplay", ...)`, `$("html").addClass()/removeClass()`
- **Assets:** image.gif, image.png, song.wav (in assets/ folder)

**Harness considerations:**
- No custom StoryInterface (uses default SugarCube sidebar UI)
- Settings .tw says `format-version: "2.36.1"` but compiled HTML uses 2.37.3
- Pattern: Reference implementation for the Settings API
- All Setting callbacks use `onInit` + `onChange` pattern
- `settings.*` object accessed in both JS and passage code

---

#### 2.3.3 One Page Template

**Structure:** Single .tw + Script.js + StyleSheet.css. Custom StoryInterface.

**Passages:**
- `StoryInterface` [AVOID-EDIT] - Custom UI: `#passages` + `#menu` (data-passage="menu")
- `StoryDisplayTitle` [EDIT] - Title display
- `Start` [noreturn cover] - Title page with Resume/New/Load/Settings links
- `menu` [SOME] - Includes StoryDisplayTitle, navigation, sidemenu
- `sidemenu` [SOME nobr] - Dropdown menu with popup links (stats, achievement, credits, saves, settings, restart)
- `navigation` [SOME] - Undo/redo buttons (Engine.backward/forward)
- `stats` [CODEX] - Stats bars demo
- `achievement` [CODEX] - Achievements placeholder
- `credit` [Credits] - Attribution
- `Next` [noreturn] - Sample story passage
- `Styling` - Headings, lists, tables, links showcase
- `Basic Macros` - All SugarCube input macros
- `End` [cover] - End page with restart/back

**SugarCube-specific elements:**
- **StoryInterface:** Custom HTML layout with `data-passage` attributes
- **Macros:** `<<link>>` (with passage navigation + `<<run>>` actions), `<<run>>` (UI.saves(), UI.settings(), UI.restart(), Engine.backward(), Engine.forward(), Save.browser.continue(), Engine.show()), `<<include>>`, `<<if>>`, `<<popup>>` (Chapel's custom macro), `<<nobr>>`, `<<set>>`, `<<unset>>`, `<<print>>`, `<<button>>`
- **Functions/APIs:** `Save.browser.size`, `Save.browser.continue()`, `State.length`, `State.size`, `Engine.backward()`, `Engine.forward()`, `UI.saves()`, `UI.settings()`, `UI.restart()`
- **Custom macros (JS):** Chapel's Dialog API macro set (v1.3.0): `<<dialog>>`, `<<popup>>`, `<<dialogclose>>`
- **Custom JS:** `$(document).on(":passagedisplay", ...)` for scroll reset, Settings API (font, autosave, autoname, theme)
- **Passage tags:** `noreturn` (no saving), `cover` (title/end pages), `CODEX` (info pages), `SOME`, `nobr`, `AVOID-EDIT`, `EDIT`, `Credits`
- **CSS hooks:** `#passages`, `#menu`, `#title`, `#dropmenu`, `.dropbtn`, `.dropup-content`, `.statBarContainer`, `.statSingle`, `.statBack`, `.statFront`, `.statText`, `.choice`
- **Inline JS:** `myFunction()` for dropdown toggle in StoryInterface passage
- **Attribute directives:** `@style` for dynamic inline styles

**Harness considerations:**
- Pattern: Single-page layout with dropdown menu and popup dialogs
- Uses Chapel's Dialog API for popups (must be included in JS)
- `noreturn` tag prevents saving on title/end/info pages
- `cover` tag for special title/end page styling
- Inline JavaScript in StoryInterface passage

---

#### 2.3.4 Simple Book Template

**Structure:** Single .tw + Script.js + StyleSheet.css. Custom StoryInterface.

**Passages:**
- `StoryInterface` [AVOID-EDIT] - Book layout: `#title`, `#middle` (with `#left-menu`, `#cover`/`#passages`, `#right-menu`), `#navig`
- `StoryDisplayTitle` [EDIT] - Title
- `Start` [noreturn cover-start] - Title page
- `Navigation` [SOME] - Forward/backward icons (FontAwesome)
- `LeftMenu` [SOME nobr] - Toggleable left menu (Credits, Saves, Settings, Restart)
- `RightMenu` [SOME nobr] - Toggleable right menu (Player, Stats, Codex, Achievements)
- `player` [CODEX], `achievements` [CODEX], `codex` [CODEX], `stats` [CODEX] - Info pages
- `credits` [Credits] - Attribution
- `Next` [noreturn] - Sample story with `<<notify>>` demo
- `Styling`, `Basic Macros` - Showcase passages
- `End` [cover-start cover-end] - End page

**SugarCube-specific elements:**
- **StoryInterface:** Book-like layout with left/right side menus and cover
- **Macros:** `<<link>>` (with FontAwesome icons), `<<toggleclass>>` (built-in), `<<popup>>` (Chapel's), `<<run>>` (UI.saves/settings/restart, Engine.backward/forward, Save.browser.continue), `<<include>>`, `<<if>>`, `<<nobr>>`, `<<set>>`, `<<unset>>`, `<<print>>`, `<<notify>>` (Chapel's, with `<<timed>>`), `<<button>>`
- **Functions/APIs:** Same as One Page (Save.browser, State, Engine, UI)
- **Custom macros (JS):** Chapel's Dialog API (dialog, popup, dialogclose) + Chapel's Notify macro
- **Settings API:** Font size, font type, autosave, autoname, notification toggle, theme (Purple/Green/Orange)
- **Config:** `Config.saves.isAllowed` with `noreturn` tag check, `Config.saves.maxSlotSaves = 6`
- **FontAwesome:** Icons via `<i class="fa-solid fa-*">` classes
- **Passage tags:** `noreturn`, `cover-start`, `cover-end`, `CODEX`, `SOME`, `nobr`, `AVOID-EDIT`, `EDIT`, `Credits`
- **CSS hooks:** `#title`, `#middle`, `#left-menu`, `#cover`, `#right-menu`, `#navig`, `.show` (toggle), `.statBarContainer`, `.statSingle`, `.statBack`, `.statFront`, `.statText`, `.choice`

**Harness considerations:**
- Pattern: Book metaphor with toggleable side menus
- Uses `<<toggleclass>>` built-in macro for menu show/hide
- Dual custom macro dependencies: Dialog API + Notify
- `cover-start`/`cover-end` tags for book cover styling
- `title` attribute on `<p>` for hover tooltips

---

#### 2.3.5 Space-Tech UI Template

**Structure:** Single .tw + Script.js + StyleSheet.css. Custom StoryInterface. Most feature-rich UI template.

**Passages:**
- `StoryInterface` - Complex layout: `#topcontainer` (left-menu, center-block, right-menu), `#mobile-top-menu`, `#passages`, `#mobile-btm-menu`
- `first-menu` - Left/bottom menu (Credits, Saves, Settings, Restart) with Unicode icons
- `center-block` [nobr] - Dynamic header (game title / "Codex" / `$chapter`) based on passage tags
- `second-menu` - Right/top menu: either stat bars (`<<statsformat>>`) or navigation icons, depending on `stats-visible` tag
- `second-menu-mobile` - Mobile variant of right menu
- `StatWidget` [widget nobr] - Widget definitions for stats bars
- `StoryInit` - Sets $fuel, $oxygen, $cargo, $chapter
- `Start` [title noreturn] - Title page
- `Next` [stats-visible] - Sample passage (shows stats bars)
- `Styling`, `Basic Macros` [stats-visible] - Showcase
- `Codex` [codex] - "Tech" UI demo
- `Styling Codex` [codex], `Basic Macros Codex` [codex] - Tech-themed showcases
- `END` [title] - End page
- `credits` - Attribution

**SugarCube-specific elements:**
- **StoryInterface:** Responsive layout with separate mobile/desktop menu elements
- **Widgets:** `<<widget "statsformat">>` (dispatches to web/mobile variants), `<<widget "percent_stat_web">>` (vertical bars), `<<widget "percent_stat_mobile">>` (horizontal bars)
- **Dynamic macro generation:** `<<= `<<percent_stat` + _args[0] + ` "stat1" $fuel "Bar">>` >>` (nested macro generation via string concatenation)
- **Macros:** `<<widget>>`, `<<link>>`, `<<run>>` (UI.saves/settings/restart, Dialog.create/wikiPassage/open), `<<if>>/<<elseif>>/<<else>>`, `<<nobr>>`, `<<set>>`, `<<button>>`
- **Functions/APIs:** `tags()` (for tag-conditional rendering), `Save.browser`, `Engine`, `UI`, `Dialog.create().wikiPassage().open()`, `Story.get().processText()`
- **Passage tags:** `title`, `noreturn`, `stats-visible` (triggers stats bar display), `codex` (switches to "Tech" UI theme), `nobr`, `widget`
- **Tag-based CSS:** `[data-tags~="codex"]` selectors for theme switching
- **CSS hooks:** `#topcontainer`, `#left-menu`, `#center-block`, `#right-menu`, `#mobile-top-menu`, `#mobile-btm-menu`, `.stat`, `.stat1/.stat2/.stat3`, `.skills`, `.text`, `.choice`
- **Settings:** Font, autosave, autoname (simpler than Settings Template)
- **Unicode icons:** Uses Unicode characters (copyright, floppy, gear, arrow) instead of FontAwesome

**Harness considerations:**
- Pattern: Dual-theme UI with tag-driven CSS theming
- Widget-based stat bars with mobile/desktop variants
- Dynamic nested macro generation (advanced pattern)
- `stats-visible` tag controls UI element visibility per-passage
- `codex` tag switches entire visual theme
- Mobile-responsive StoryInterface with separate mobile elements

---

#### 2.3.6 Title Page Template

**Structure:** Single .tw + Stylesheet.css. No custom StoryInterface (uses default SugarCube UI). No Script.js.

**Passages:**
- `Bar` [title bar] - Top-center title variant
- `Basic` [basic] - Side-menu title variant
- `Bottom Left` [title bottom-left] - Mixed alignment left
- `Bottom Right` [title bottom-right] - Mixed alignment right
- `Credits` - Attribution (opened via Dialog)
- `Menu Elements` - Shared include for title+links
- `Middle Page` [title centered] - Center-aligned title
- `Notes` [basic] - Coding notes with `<<return>>`
- `Start` [basic] - Welcome/menu page with links to all variants
- `Top Left` [title top-left] - Left-aligned title
- `Top Right` [title top-right] - Right-aligned title

**SugarCube-specific elements:**
- **StoryData:** Includes `tag-colors` mapping (title=basic=green, etc.) and `zoom: 1`
- **Macros:** `<<link>>` (passage navigation + `<<run>>` for UI/Dialog), `<<run>>` (UI.saves, UI.settings, Dialog.create().wikiPassage().open(), Dialog.setup/wiki/open), `<<include>>`, `<<return>>`, `<<script>>`
- **Functions/APIs:** `Dialog.create()`, `Dialog.wikiPassage()`, `Dialog.open()`, `Dialog.setup()`, `Dialog.wiki()`, `Story.get().processText()`, `UI.saves()`, `UI.settings()`
- **Passage tags:** `title` (with position modifiers: `bar`, `top-left`, `top-right`, `centered`, `bottom-left`, `bottom-right`), `basic`
- **Tag-based CSS:** `[data-tags~="title"]`, `[data-tags~="top-left"]`, etc.
- **CSS hooks:** `#game-title`, `#title-links`, inline `<style>` blocks per-passage for link colors
- **No custom JS:** No Script.js file, no custom macros, no Settings API
- **Inline CSS:** Per-passage `<style>` blocks for link color customization

**Harness considerations:**
- Simplest template (no JS, no custom macros)
- Pattern: Multiple title page layout variants using passage tags + CSS positioning
- `<<include "Menu Elements">>` for shared title content
- `tag-colors` in StoryData for visual distinction in Twine editor
- Good reference for tag-based CSS theming without JavaScript

---

#### 2.3.7 VN-lite RPG Template

**Structure:** Single .tw + Script.js + StyleSheet.css. Custom StoryInterface. Includes image assets (img1.jpg, img2.jpg, img3.jpg, subtle-prism.png).

**Passages:**
- `StoryInterface` - VN layout: `#header` (title), `#container` (`#passages` + `#perso` for character image), `#footer` (`#side-image` for party image + `#menu`)
- `StoryDisplayTitle` - Title
- `Start` [title noreturn] - Main menu (NEW GAME, RESUME, SAVES, SETTINGS, CREDITS)
- `Next` - Sample story passage
- `Styling`, `Basic Macros` - Showcase
- `ImgPerso` - Character image display (conditional by passage name and `side` tag)
- `SidePerso` - Party/companion images (conditional by `side` tag)
- `Menu` [nobr] - Bottom menu bar with FontAwesome icons (restart, settings, saves, inventory, codex, player)
- `Inventory` [noreturn side] - Inventory page
- `Codex` [noreturn side] - Codex page
- `Player` [noreturn side] - Player character page
- `credits` - Attribution (opened via Dialog)

**SugarCube-specific elements:**
- **StoryInterface:** VN-style layout with dedicated image areas and bottom menu bar
- **Macros:** `<<link>>` (FontAwesome icons, passage navigation, `<<run>>` actions), `<<run>>` (UI.saves/settings/restart, Dialog.create/wikiPassage/open, Save.browser.continue, Engine.show), `<<if>>/<<elseif>>/<<else>>`, `<<nobr>>`, `<<button>>`, `<<back>>`
- **Functions/APIs:** `Save.browser.size`, `Save.browser.continue()`, `Engine.show()`, `passage()` (for image selection), `tags()` (for `side` tag check), `isnot` operator, `Dialog.create().wikiPassage().open()`
- **Passage tags:** `title`, `noreturn`, `side` (hides party images, prevents saving), `nobr`
- **Image conditionals:** `<<if tags().includes("side")>>` + `<<elseif passage() isnot "Next">>` for dynamic image selection
- **FontAwesome:** `fa-solid fa-backward-fast`, `fa-gear`, `fa-floppy-disk`, `fa-box-open`, `fa-book`, `fa-user`
- **CSS hooks:** `#header`, `#container`, `#passages`, `#perso`, `#footer`, `#side-image`, `#menu`, `.choice`
- **Settings:** Only autosave toggle (minimal settings)
- **Config:** `Config.saves.isAllowed` with `noreturn` tag check

**Harness considerations:**
- Pattern: Visual-novel layout with character/party image areas
- `side` tag for "non-story" pages (no party images, no saving)
- Image selection based on passage name and tags
- Bottom icon-only menu bar (no text labels)
- Minimal settings (autosave only)
- Requires image assets for full functionality

---

## 3. Cross-Template Pattern Catalog

### 3.1 StoryInterface Patterns

| Pattern | Used In | Description |
|---|---|---|
| Custom StoryInterface | One Page, Simple Book, Space-Tech, VN-lite | HTML layout in special passage with `data-passage` attributes |
| Default UI | Character Creator, Settings, Title Page | No custom StoryInterface, uses SugarCube default sidebar |
| `data-passage` elements | All custom UI templates | Passage names in HTML attributes for dynamic content areas |
| `#passages` container | All custom UI templates | Required comment `<!--DO NOT REMOVE-->` in passages div |

### 3.2 Passage Tag System

| Tag | Used In | Purpose |
|---|---|---|
| `noreturn` | All templates | Prevents saving (via `Config.saves.isAllowed`), used on title/info pages |
| `cover` | One Page, Simple Book | Special title/end page styling |
| `cover-start`/`cover-end` | Simple Book | Book cover front/back styling |
| `title` | Space-Tech, Title Page, VN-lite | Title page styling |
| `codex` | Space-Tech | Switches to alternate "Tech" UI theme via tag-based CSS |
| `stats-visible` | Space-Tech | Triggers stats bar display in side menu |
| `side` | VN-lite | Marks non-story pages (no party images, no saving) |
| `CODEX` | One Page, Simple Book | Info/reference pages |
| `SOME` | One Page, Simple Book | Internal marker for interface passages |
| `nobr` | Multiple | Suppresses line break rendering |
| `widget` | Space-Tech, Character Creator | Marks widget definition passages |
| `AVOID-EDIT` | One Page, Simple Book | Marks StoryInterface as not to be edited |
| `EDIT` | One Page, Simple Book | Marks editable interface passages |
| `Credits` | Multiple | Credits page marker |
| `basic` | Title Page | Default SugarCube UI variant |

### 3.3 Custom Macro Dependencies

| Macro | Source | Used In | Version |
|---|---|---|---|
| `<<popup>>` | Chapel's Dialog API | One Page, Simple Book | v1.3.0 (2022-07-21) |
| `<<dialog>>` | Chapel's Dialog API | One Page, Simple Book | v1.3.0 |
| `<<dialogclose>>` | Chapel's Dialog API | One Page, Simple Book | v1.3.0 |
| `<<notify>>` | Chapel's Notify | Settings, Simple Book | v1.1.1 (2022-07-21) |

**Harness consideration:** Templates using Chapel's macros require the minified JS to be included in the story's JavaScript section. The JS is embedded in each template's Script.js.

### 3.4 SugarCube API Usage

| API | Function | Used In |
|---|---|---|
| `Save.browser.size` | Check if saves exist | One Page, Simple Book, Space-Tech, VN-lite |
| `Save.browser.continue()` | Resume game | One Page, Simple Book, Space-Tech, VN-lite |
| `Save.Type.Auto` | Save type check | Settings, One Page, Simple Book, Space-Tech, VN-lite |
| `State.length` / `State.size` | Undo/redo availability | One Page, Simple Book |
| `State.getVar()` / `State.setVar()` | Variable access in JS | Settings, Character Creator, Simple Book, Space-Tech |
| `Engine.backward()` / `Engine.forward()` | Undo/redo | One Page, Simple Book |
| `Engine.show()` | Render passage | One Page, Simple Book, VN-lite |
| `Engine.restart()` | Restart game | Character Creator |
| `UI.saves()` / `UI.settings()` / `UI.restart()` | Built-in dialogs | All templates |
| `Dialog.create()` / `Dialog.wikiPassage()` / `Dialog.open()` | Custom dialogs | Title Page, Space-Tech, VN-lite |
| `Dialog.setup()` / `Dialog.wiki()` | Custom dialogs (alt API) | Title Page |
| `Story.get()` / `.processText()` | Passage text access | Title Page, Space-Tech |
| `SimpleAudio.volume()` | Audio volume | Settings |
| `tags()` | Current passage tags | Space-Tech, Settings, Character Creator, VN-lite |
| `passage()` | Current passage name | Settings, VN-lite, Character Creator |

### 3.5 Settings API Patterns

| Pattern | Templates |
|---|---|
| `Setting.addHeader()` | Settings, One Page, Simple Book, Space-Tech |
| `Setting.addList()` (dropdown) | Settings (font, size, lineheight, theme), One Page/Simple Book/Space-Tech (font, theme) |
| `Setting.addRange()` (slider) | Settings (volume) |
| `Setting.addToggle()` (checkbox) | Settings (textalign, textanim, notif, autosave, autoname), all UI templates (autosave, autoname) |
| `onInit` + `onChange` callbacks | All templates with settings |
| `Config.saves.isAllowed` with `noreturn` tag | All templates except Title Page |
| `Config.saves.descriptions` (autoname) | Settings, One Page, Simple Book, Space-Tech |

### 3.6 Common Passage Structure

All templates follow a similar passage flow:
1. `StoryTitle` - Game title
2. `StoryData` - Metadata (ifid, format, format-version, start)
3. `StoryInterface` (optional) - Custom UI layout
4. `StoryInit` (optional) - Variable/audio initialization
5. `StoryDisplayTitle` (optional) - UI title display
6. `Start` - Title/main menu page (usually `[noreturn]` tagged)
7. `Next` - First story passage (sample content)
8. `Styling` - Text styling showcase
9. `Basic Macros` - Input macro showcase
10. `End` - End page (usually `[noreturn]` or `[cover]` tagged)
11. `Credits` - Attribution (required by CC-BY license)

### 3.7 Reusable Showcase Passages

Every template includes identical `Styling` and `Basic Macros` passages demonstrating:
- **Styling:** h1-h6 headings, `<hr>`, lists, tables, basic/link list/div-wrapped links
- **Basic Macros:** `<<textbox>>`, `<<textarea>>`, `<<radiobutton>>` (with `autocheck`), `<<numberbox>>`, `<<listbox>>` (with `autoselect` + `<<option>>`), `<<cycle>>` (with `autoselect` + `<<option>>`), `<<checkbox>>` (with `autocheck`), `<<button>>`

**Harness consideration:** These showcase passages are template demonstrations, not story content. The harness should generate equivalent passages or omit them.

---

## 4. Harness Generation Considerations

### 4.1 Must Preserve

1. **StoryData passage:** Correct `ifid` (unique per story), `format: "SugarCube"`, `format-version` matching bundled SugarCube, `start` passage name
2. **StoryInterface passage:** When using custom UI templates, preserve the HTML structure and `data-passage` attributes exactly
3. **`#passages` container:** Must exist in StoryInterface with `<!--DO NOT REMOVE-->` comment
4. **Chapel's macro JS:** If using `<<popup>>`, `<<dialog>>`, or `<<notify>>`, include the minified JS from the template's Script.js
5. **`noreturn` tag system:** Apply to title/info/end pages to prevent saving
6. **Config.saves.isAllowed:** Include the `noreturn` tag check for save restrictions
7. **Credits passage:** Required by CC-BY license (credit manonamora + link to itch.io page)
8. **FontAwesome:** Include FontAwesome 6 CSS if using templates with `fa-solid` icons (Simple Book, VN-lite)

### 4.2 Should Adapt

1. **IFID:** Generate a new UUID for each story (do not reuse the placeholder)
2. **StoryTitle/StoryDisplayTitle:** Set to the actual story title
3. **Start passage:** Replace template title page with story-specific menu
4. **Styling/Basic Macros passages:** Optional; include only if showcasing SugarCube features
5. **Settings:** Adapt to story needs (font, theme, autosave are universally useful)
6. **Stats widgets:** Adapt variable names and display to story-specific stats
7. **Image assets:** VN-lite requires character/party images; replace placeholder images

### 4.3 Template Selection Guide

| Story Type | Recommended Template | Rationale |
|---|---|---|
| Character-driven RPG | Character Creator + Space-Tech | Character creation + stats bars + dual theme |
| Visual novel | VN-lite RPG | Image areas + bottom menu + minimal UI |
| Interactive fiction (book-style) | Simple Book | Book metaphor + side menus + notifications |
| Minimalist IF | One Page | Single page + dropdown menu |
| Title/menu focused | Title Page | Multiple layout variants |
| Settings-heavy project | Settings | Full Settings API reference |
| Sci-fi/tech themed | Space-Tech | Space/Tech dual theme + Unicode icons |

### 4.4 Key Technical Constraints

1. **SugarCube v2.37.3:** All templates target this version. Using older SugarCube will cause errors (API changes between 2.36.1 and 2.37.3)
2. **jQuery dependency:** SugarCube bundles jQuery; all templates use `$(document).on()` event handlers
3. **`@style` directive:** Used for dynamic inline styles (stat bars) — SugarCube-specific attribute directive
4. **`<<nobr>>` macro:** Suppresses line breaks in passages with heavy HTML/macros
5. **Widget passages:** Must be tagged `[widget]` and use `<<widget "name">>...<</widget>>` syntax
6. **Nested macro generation:** Space-Tech uses `<<=`<<macro` + string + `>>`` pattern — advanced, fragile
7. **`data-tags~="tag"` CSS:** Tag-based CSS selectors for per-passage theming

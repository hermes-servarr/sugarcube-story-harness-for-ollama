# Technical Report: Anonymized SugarCube 2 Engine Analysis (`example-structure.html`)

**File:** `examples/game_templates/example-structure.html`
**Size:** 4,509,433 bytes (~4.5 MB), 60,686 lines, 785 passages
**Previous analysis:** Covered passage/macro/variable patterns (785 passages, 242 variables, 21 widgets, 25 macros)
**This analysis:** Covers the NEWLY-INCLUDED anonymized engine JS (~696KB), CSS (~32KB), and custom JS (~20KB)

---

## 1. File Structure Overview

The file has three `<script>` blocks and two CSS regions:

| Section | Lines | Contents |
|---------|-------|----------|
| `<html data-init="">` | 1–2 | Root element with `data-init` attribute |
| `<head>` | 3–42 | 1 engine `<script>`, 16 `<style>` blocks (engine CSS) |
| `<body>` UI scaffold | 43–48 | 3 nested `<div id="">` containers (noscript, loading, story region) |
| `<tw-storydata>` | 49–60680 | Story metadata, 3 `@import` CSS lines, user CSS (lines 49–315), custom JS script[1] (lines 316–706), 9 `<tw-tag>` elements, 785 `<tw-passagedata>` |
| Trailing `<script>` (script[2]) | 60681–60684 | Conditional SugarCube engine module loader |
| `</body></html>` | 60685–60686 | Document close |

### Script Tag Inventory

| Tag | Lines | Role | Size |
|-----|-------|------|------|
| script[0] | 10–26 | **SugarCube engine JS** (jQuery + SugarCube runtime) | ~696KB (lines 11–25, all on a few very long lines) |
| script[1] | 316–706 | **User-defined JavaScript** (story-specific code) | ~20KB |
| script[2] | 60681–60684 | **Conditional engine module** (loads only if format matches) | ~4KB |

---

## 2. Anonymized Engine JavaScript (script[0], lines 10–26)

### 2.1 Bootstrap Pattern

The engine bootstrap uses a **feature-detection gate** (line 11):

```javascript
if(identifier001.identifier002 && identifier001.identifier003 && 
   identifier001.identifier004 && identifier005.identifier006 && 
   identifier005.identifier007 && identifier008) {
    identifier001.identifier009.identifier010("Lorem ipsum", "Lorem ipsum");
    // ... engine code ...
} else {
    identifier001.identifier009.identifier010("Lorem ipsum", "Lorem ipsum");
}
```

This pattern maps to SugarCube's `SugarCube.Docs.BugReportLog()` or a feature check. The `identifier001` is the global object (likely `window` or `globalThis`), `identifier009` is likely `document` or a SugarCube API namespace, and `identifier010` is likely `log()` or `writeln()`.

### 2.2 Bundled Libraries (lines 11–24)

The engine JS is bundled in **6 IIFE (Immediately Invoked Function Expression) blocks**, each introduced by a comment `/* Lorem ipsum dolor sit amet. */`:

1. **Lines 12–13**: Polyfill block — checks for `"Lorem ipsum" in identifier011` (likely `Symbol.iterator` or `Symbol` polyfill), includes `Array.from`, `Array.prototype.find`, `Object.defineProperty` polyfills. The `identifier026` is likely `Array`, `identifier021` is `Object`, `identifier005` is `Object` (same), `identifier014` is a helper.

2. **Lines 15–16**: **jQuery core** — the UMD wrapper pattern `(function(identifier014,identifier020){...})(this,function(){var identifier014=identifier026;...})` with `typeof identifier066==="Lorem ipsum"&&identifier066.identifier067` (maps to `typeof module==="object"&&module.exports`). This is jQuery's factory pattern. Key jQuery internals visible:
   - `identifier026` = `Array` (used as `identifier014.identifier063` = `Array.prototype`)
   - `identifier005` = `Object` (used for `defineProperty`)
   - `identifier021` = `Object` (same, `identifier021.identifier063` = `Object.prototype`)
   - `identifier071` = `Function` (used for `identifier071.identifier063` = `Function.prototype`)
   - `identifier014.identifier064` = `Array.prototype.slice`
   - `identifier014.identifier051` = `Array.prototype.splice`
   - `identifier014.identifier040` = `Array.prototype.push`
   - `identifier085` = `Symbol` (checked via `typeof identifier085`)
   - `identifier045` = `Error` (used in `throw new identifier045(...)`)

3. **Lines 17–18**: **jQuery extend/event system** — IIFE with `identifier015=identifier071.identifier036.identifier092(...)` (likely `Function.prototype.bind`), includes `defineProperty` wrapper, `identifier019` tracks `Object.defineProperty` support.

4. **Lines 19**: **jQuery full library** — the largest block, UMD pattern `!function(identifier015,identifier014){...}("Lorem ipsum"!=typeof identifier122?identifier122:this,function(identifier178,identifier015){...})`. Key patterns:
   - `identifier122` = `global` or `window`
   - `identifier178` = `this` context
   - `identifier128` = `identifier178.identifier001` (likely `global.document`)
   - `identifier043` = object with `identifier319, identifier333, identifier334, identifier335` (likely jQuery support flags: `leadingWhitespace`, `tbody`, `htmlSerialize`, `link`/`hrefNormalized`)
   - `identifier084` = function for HTML parsing (checks `typeof identifier085&&typeof identifier085.identifier086` → `typeof Symbol&&typeof Symbol.iterator`)
   - `identifier037` = `identifier043.identifier063` (jQuery.fn.init prototype)

5. **Lines 21**: **jQuery throttle/debounce** — `identifier081.identifier923` or `identifier081.identifier924` with `$.identifier925=identifier034=function(...)` — this is the jQuery throttle-debounce plugin. Visible: `$.identifier374` (likely `$.guid`), `identifier656` = `Date` (used as `+new identifier656()`), `identifier049` = `arguments`, `identifier529` = `setTimeout`, `identifier871` = `clearTimeout`.

6. **Lines 22–24**: **Event system + SugarCube core** — `identifier015.prototype` patterns with `identifier301` (likely `on`), `identifier506` (likely `one`), `identifier610` (likely `off`), `identifier930` (likely `trigger`). Line 24: **Array of 24 HTML tag names** (`identifier950`) with `identifier537=identifier122.identifier537` — this is SugarCube's `TempState` or a global event registry pattern, polyfilling `identifier537[tag]` to a no-op (`identifier364=function(){}`) if not defined.

### 2.3 Visible SugarCube API Surface

From the identifier mapping across all three script blocks:

| Anonymized ID | Maps to (inferred) | Evidence |
|---------------|-------------------|----------|
| `identifier001` | `window`/`global` | Used as root object, `identifier001.identifier012("Lorem ipsum")` = `document.getElementById(...)` |
| `identifier009` | `document` | `identifier001.identifier009.identifier010(...)` = `document.write(...)` or `document.writeln(...)` |
| `identifier012` | `getElementById` | `identifier001.identifier012("Lorem ipsum")` repeatedly used with `$()` wrapper |
| `identifier122` | `SugarCube` / `window` | Global namespace, `identifier122.identifier537` = `SugarCube.TempState` or similar |
| `identifier537` | `TempState` or `EventRegistry` | `identifier537.identifier141(...)` = logging/event, `identifier537.identifier363(...)` = error, `identifier537.identifier538(...)` = warn |
| `identifier966` | `Setting` | `identifier966.identifier967("name", {...})` = `Setting.add(name, config)` — 3 calls with `identifier968` (name), `identifier969` (definition), `identifier970` (onInit), `identifier971` (onChange) |
| `identifier972` | `Config` | `identifier972.identifier973.identifier974 = 0` = `Config.history.controls` or similar; `identifier972.identifier973.identifier1055 = 0` |
| `identifier975` | `UI` or `Dialog` | `identifier975.identifier976.identifier048(...)` = `UI.addBodyClass(...)` or similar; `identifier975.identifier1055.identifier977(...)` = scroll/position API |
| `identifier1032` | `Macro` | `identifier1032.identifier048("name", {...})` = `Macro.add(name, {...})` — registers custom macros |
| `identifier1040` | `State` or `Setting` | `identifier1040.get(...)`, `identifier1040.identifier152(...)` = `Setting.get()` / `Setting.has()` |
| `identifier1046` | `State` | `identifier1046.identifier028` = `State.length` or history length; `identifier1046.identifier980.return` = passage return value |
| `identifier1037` | `Engine` or `Wikifier` | `identifier1037.identifier630(...)`, `identifier1037.identifier1038(...)` — rendering APIs |

### 2.4 SugarCube Version Identification

**Conclusion: SugarCube v2.37.3** (matching the harness's target version)

Evidence:
1. **`color-emoji` font-face** (line 30): Added in SugarCube v2.36.x+ for system emoji font support
2. **`sc-icons` font-face** (line 29): SugarCube's icon font, present since v2.30+ but the `font-display:block` property is a v2.37+ addition
3. **`prefers-reduced-motion` media query** (line 33): Added in SugarCube v2.36.0 for accessibility
4. **`data-dialog` attribute selector** (line 35): Dialog overlay system, stable in v2.37.x
5. **`data-debug-view` and `data-outlines` attributes** (lines 31, 41): Debug bar styling, v2.37.x patterns
6. **`init-loading-spin` keyframes** (line 28): Loading spinner animation, v2.37.x style
7. **`cursor-blink` keyframes** (line 34): Typewriter cursor animation, v2.37.x addition
8. **`data-mobile-mode` attribute** (line 79): Mobile mode detection, v2.37.x responsive system
9. **jQuery throttle/debounce bundled** (line 21): SugarCube bundles this since v2.36.x
10. **Harness config confirms**: `format_version: str = "2.37.3"` in `harness/models.py:406`, matching 6/7 studied templates
11. **The third script block's conditional** (line 60683): `if(identifier001.identifier009.identifier038("Lorem ipsum")==="Lorem ipsum")` — this checks `document.getAttribute("...")` or a format-specific test, gating an additional engine module. This pattern is unique to v2.37.x which introduced modular loading.

---

## 3. Anonymized CSS Analysis (lines 27–41, 49–315)

### 3.1 Engine CSS (lines 27–41) — 16 `<style>` Blocks

| Block | Lines | Content | SugarCube Role |
|-------|-------|---------|---------------|
| 1 | 27 | **Normalize/reset CSS** | Standard HTML5 reset (html, body, article, aside, etc.) — SugarCube bundles a CSS reset |
| 2 | 28 | **Loading screen** | `@keyframes init-loading-spin`, `#selector001` (loading overlay), `html[data-init=lacking]`, `html[data-init=loading]`, `html[data-init=no-js]` states |
| 3 | 29 | **Icon font** | `@font-face{font-family:sc-icons;font-display:block;src:url(...)}` |
| 4 | 30 | **Emoji font** | `@font-face{font-family:color-emoji;src:local(...)}` with 7 local font names |
| 5 | 31 | **Core UI** | `#selector007,tw-storydata{display:none}`, scrollbar styling, fullscreen styles, base typography, `a.selector008` (link styles), `button` styles, `input/select/textarea` base |
| 6 | 32 | **Story container** | `#selector005` (main story area with z-index/margin), `#selector021` (story data container), responsive `@media screen and (max-width:0px)` |
| 7 | 33 | **Passage transitions** | `.selector022` (passage text with opacity transition), `.selector023` (hidden state), list/table styling, `prefers-reduced-motion` override |
| 8 | 34 | **Typewriter animation** | `@keyframes cursor-blink`, `.selector024`–`.selector031` (transition elements), `.selector032`–`.selector039` (opacity:0), `.selector040::after` (blink cursor) |
| 9 | 35 | **Dialog system** | `html[data-dialog] body{overflow:hidden}`, `#selector041` (overlay backdrop), `#selector042` (visible state), `#selector043` (dialog body), `#selector044` (dialog content), `#selector045` (dialog title), `#selector046` (close button with sc-icons font) |
| 10 | 36 | **Save/Settings dialog** | `#selector047.selector049` (saves list), table layout, `#selector052` (save buttons), `.selector053`/`.selector054` (highlight states), `saves-clear` button id |
| 11 | 37 | **Settings dialog** | `#selector047.selector057` (settings panel), `[id|=setting-body]` (setting rows with table layout), `[id|=setting-label]`, `[id|=setting-control]`, `div[id|=header-body]` (header settings) |
| 12 | 38 | **Menu/list dialog** | `#selector047.selector058` (list menu), `ul`/`li` styling for navigation lists |
| 13 | 39 | **Sidebar/menu** | `#selector005` (margin transition), `#selector006` (sidebar with fixed positioning), `.selector059` (active/expanded state), `#selector060` (sidebar header), `#selector061` (sidebar content), `#selector062` (button group), `#selector063` (close button), `#selector064` (title), responsive breakpoints |
| 14 | 40 | **Debug bar** | `#selector076` (debug bar container, fixed bottom-right), `#selector077` (debug toggle), `#selector078` (debug label), `#selector079` (debug panel with table), `#selector080`–`#selector084` (debug controls) |
| 15 | 41 | **Debug view** | `html[data-debug-view] .selector087` (debug expression markers), `[data-name]`/`[data-type]` attributes, `data-type|=macro`/`data-type|=html`/`data-type|=special` selectors |
| 16 | 49 | **Story-level CSS** (@import) | 3 `@import url(resource-placeholder)` lines (external font/style imports) |

### 3.2 CSS Selector Mapping (Engine → SugarCube)

| Anonymized Selector | SugarCube Original (inferred) |
|---------------------|------------------------------|
| `#selector001` | `#init-screen` or `#loading` |
| `#selector002` | `#init-no-js` or `#noscript` |
| `#selector003` | `#init-lacking` |
| `#selector004` | `#init-loading` (spinner) |
| `#selector005` | `#story` (main story region) |
| `#selector006` | `#ui-bar` (sidebar) |
| `#selector007` | `#store-area` (tw-storydata hiding) |
| `#selector021` | `#passages` (passage display area) |
| `.selector008` | `.link-internal` |
| `.selector009` | `.link-disabled` |
| `.selector010` | `.link-external` |
| `.selector022` | `.passage` (passage text container) |
| `.selector023` | `.passage-in-transition` |
| `.selector024`–`.selector031` | `.macro-...` transition classes |
| `.selector040` | `.blink-cursor` |
| `#selector041` | `#ui-overlay` (dialog backdrop) |
| `#selector042` | `.open` (visible state) |
| `#selector043` | `#ui-dialog` (dialog body) |
| `#selector044` | `#ui-dialog-body` |
| `#selector045` | `#ui-dialog-title` |
| `#selector046` | `#ui-dialog-close` |
| `#selector047` | `#ui-dialog-body` (dialog content) |
| `.selector048` | `.ui-dialog-buttons` |
| `.selector049` | `.saves` (save dialog) |
| `.selector052` | `#saves-list` |
| `.selector053` | `.save-loaded` |
| `.selector054` | `.save-autosave` |
| `.selector057` | `.settings` (settings dialog) |
| `.selector058` | `.list-menu` |
| `.selector059` | `.open` (sidebar expanded) |
| `#selector060` | `#ui-bar-header` |
| `#selector061` | `#ui-bar-body` |
| `#selector062` | `#ui-bar-tray` |
| `#selector063` | `#ui-bar-close` |
| `#selector064` | `#story-title` |
| `#selector066` | `#menu` (story menu) |
| `#selector076` | `#debug-bar` |
| `#selector077` | `#debug-bar-toggle` |
| `#selector078` | `#debug-bar-label` |
| `#selector079` | `#debug-bar-watch` |
| `.selector087` | `.debug-expression` |

### 3.3 User-Defined CSS (lines 49–315)

~267 lines of user CSS, embedded inside `<tw-storydata>`. Key patterns:

- **3 `@import` statements** (lines 49–51): External font/stylesheet imports
- **Theme variants** (lines 53–69): `html.selector092` through `html.selector095` — font-family/font-size overrides for 4 theme classes (likely light/dark/serif/monospace themes)
- **Image handling** (lines 72–84): `img:not(.selector096)` centered, `body[data-mobile-mode]` responsive image rules
- **Custom link styles** (lines 86–129): `a.selector097`, `a.selector010#selector098`, `a.selector010.selector099` — styled links with monospace fonts, letter-spacing
- **Sidebar customization** (lines 130–142): `#selector006` background-image, `#selector062`, `#selector063`, `#selector066` link colors
- **Dialog customization** (lines 144–158): `#selector047` background-color, `#selector043:has(#selector047) #selector044` — uses `:has()` selector (modern CSS)
- **Button styles** (lines 165–270): Extensive `#selector052 button`, `#selector100`–`#selector107` — custom button colors with hover states
- **Typography** (lines 287–312): `body` background, `.selector022` positioning, `hr` styling, `h1` margins
- **Portrait/figure styling** (line 316): `.selector109` with float-left images, first/last paragraph styling — character portrait or figure display

### 3.4 UI Patterns Visible in CSS

1. **Dialog system**: Full modal overlay with backdrop (`#selector041`), dialog body (`#selector043`), title (`#selector045`), close button (`#selector046` using sc-icons font)
2. **Sidebar/UI bar**: Fixed left sidebar (`#selector006`) with expand/collapse transition (`.selector059`), responsive breakpoints
3. **Save slots**: Table-based save list with load/delete buttons, autosave highlighting
4. **Settings panel**: Table layout with label/control rows, range inputs, toggle buttons
5. **Debug bar**: Fixed bottom-right panel with watch table, toggle controls
6. **Passage transitions**: Opacity fade-in (0.4s ease-in), `prefers-reduced-motion` accessibility override
7. **Loading screen**: Spinner animation with `data-init` states (`lacking`, `loading`, `no-js`)
8. **Typewriter effect**: Cursor blink animation for `<<timed>>`/typewriter macros
9. **Responsive design**: Multiple `@media screen and (max-width:0px)` breakpoints, `data-mobile-mode` attribute switching

---

## 4. Custom User JavaScript (script[1], lines 316–706)

~20KB of user-defined JavaScript embedded inside `<tw-storydata>`. This is story-specific code that extends the SugarCube engine.

### 4.1 Configuration Array (line 317)

```javascript
var identifier952 = ["Lorem ipsum", "Lorem ipsum"];
```
A 2-element array — likely a language/locale pair or theme name list.

### 4.2 Global Setting (lines 319–322)

```javascript
if (identifier953.identifier954 === undefined) {
    identifier953.identifier954 = "Lorem ipsum";
}
```
Sets a default value for `identifier953.identifier954` — likely `settings.language` or `settings.theme` if undefined. `identifier953` maps to `settings` (the SugarCube settings object).

### 4.3 Number Formatting Function (lines 325–338)

```javascript
identifier122.identifier955 = function(identifier956, identifier957) {
    if (identifier956 === undefined || identifier957 === undefined) return "Lorem ipsum";
    var identifier958 = identifier957.identifier042().identifier959(0, 'Lorem ipsum');
    if (identifier122.identifier954 === "Lorem ipsum") {
        var identifier960 = identifier956 >= 0 ? 'Lorem ipsum' : 'Lorem ipsum';
        var identifier961 = identifier956 % 0 || 0;
        return identifier961 + 'Lorem ipsum' + identifier958 + 'Lorem ipsum' + identifier960;
    } else {
        var identifier962 = identifier956.identifier042().identifier959(0, 'Lorem ipsum');
        return identifier962 + 'Lorem ipsum' + identifier958;
    }
};
```
A number formatting function — likely `SugarCube.formatNumber()` or a currency/number display utility. Uses `identifier122.identifier954` (the global setting) to switch between two formatting modes. `identifier957` is a number, `.identifier042()` = `.toString()`, `.identifier959()` = `.slice()`. The `% 0` (anonymized modulo) likely was `% 1000` or similar for thousand separators.

### 4.4 Event Registration (lines 340–363)

```javascript
identifier122.identifier963 = function() {
    identifier537.identifier141("Lorem ipsum"); // log
    $('Lorem ipsum').identifier349(function() {  // .each()
        var identifier956 = $(this).identifier552('Lorem ipsum');  // .data()
        var identifier957 = $(this).identifier552('Lorem ipsum');
        if (identifier956 !== undefined && identifier957 !== undefined) {
            var identifier964 = identifier122.identifier955(identifier956, identifier957);
            $(this).identifier336(identifier964);  // .text()
            identifier537.identifier141("Lorem ipsum", identifier956, identifier957, ...);
        }
    });
    $('Lorem ipsum').identifier349(function() { ... });
};
```
Registers jQuery `.each()` handlers on specific selectors, reading `.data()` attributes and formatting them. `identifier349` = `.each()`, `identifier552` = `.data()`, `identifier336` = `.text()`, `identifier537.identifier141` = `console.log` or SugarCube's logging.

### 4.5 Setting Registration (lines 365–381, 507–512, 574–581)

Three `Setting.add()` calls:

```javascript
identifier966.identifier967("Lorem ipsum", {          // Setting.add("name", {
    identifier968: "Lorem ipsum",                       //   name: "...",
    identifier969: identifier952,                       //   definition: [array],
    identifier970: identifier965,                      //   onInit: function,
    identifier971: identifier965                       //   onChange: function
});

identifier966.identifier967("Lorem ipsum", {
    identifier968: "Lorem ipsum",
    identifier969: identifier1017,                     // different array
    identifier970: identifier1018,
    identifier971: identifier1018
});

identifier966.identifier967("Lorem ipsum", {
    identifier968: "Lorem ipsum",
    identifier969: identifier1020,
    identifier970: function() { identifier529(identifier1021, 0); },  // setTimeout(fn, 0)
    identifier971: identifier1021
});
```

`identifier966` = `Setting`, `identifier967` = `Setting.add()`, `identifier968` = setting name, `identifier969` = definition/config, `identifier970` = `onInit` callback, `identifier971` = `onChange` callback.

### 4.6 Config Modification (lines 396, 633)

```javascript
identifier972.identifier973.identifier974 = 0;     // Config.history.controls = 0
identifier972.identifier973.identifier1055 = 0;    // Config.history.maxStates = 0
```

`identifier972` = `Config`, `identifier973` = `Config.history` (or another Config sub-object), `identifier974` and `identifier1055` are config properties.

### 4.7 Story Menu/Event Handlers (lines 384–393, 583–691)

Multiple event registrations:

```javascript
$(identifier001).identifier693('Lorem ipsum', function() { ... });  // .on(':passageinit' or ':passagestart')
$(identifier001).identifier301('Lorem ipsum', function() { ... });  // .on(':passagerender' or ':passagedisplay')
```

`identifier693` and `identifier301` are jQuery `.on()` with different event namespaces — these are SugarCube's custom events (`:passageinit`, `:passagerender`, `:passagestart`, `:passageend`, `:passagedisplay`).

### 4.8 Passage Init Handler — Engine Config Override (lines 399–476)

A complex `:passageinit` handler that modifies `identifier979.identifier980` (likely ` passage instance` or `Engine config`) based on passage metadata. It:
- Reads `identifier974` (a flag/state)
- Conditionally sets 20+ properties on `identifier979.identifier980` (e.g., `identifier981`, `identifier982`, `identifier983`, `identifier984`, `identifier985`, `identifier986`, `identifier987`, `identifier988`, `identifier989`, `identifier990`, `identifier991`, `identifier992`, `identifier993`, `identifier994`, `identifier995`, `identifier996`, `identifier997`, `identifier998`, `identifier999`, `identifier1000`, `identifier1001`, `identifier1002`, `identifier1003`, `identifier1004`, `identifier1005`)
- These are likely `Config.*` overrides applied per-passage (e.g., disabling UI elements, setting passage-specific display options)

### 4.9 Theme/Application Switcher (lines 486–505)

```javascript
switch (identifier953.identifier1019) {   // settings.theme
    case "Lorem ipsum": $identifier703.identifier887("Lorem ipsum"); break;  // .addClass()
    case "Lorem ipsum": $identifier703.identifier887("Lorem ipsum"); break;
    case "Lorem ipsum": $identifier703.identifier887("Lorem ipsum"); break;
    case "Lorem ipsum": $identifier703.identifier887("Lorem ipsum"); break;
    default: $identifier703.identifier887("Lorem ipsum"); break;
}
```

A switch statement on `identifier953.identifier1019` (likely `settings.theme` or `settings.fontMode`) that adds CSS classes to `$identifier703` (likely `$('html')` or `$('body')`). 5 theme/mode options.

### 4.10 Font Size Adjuster (lines 519–572, 583–605)

```javascript
var identifier1021 = function() {
    if (identifier953.identifier938 === "Lorem ipsum") {  // settings.enableFontSize
        identifier001.identifier572.identifier010('Lorem ipsum', 'Lorem ipsum');  // document.documentElement.style.setProperty(...)
        $('Lorem ipsum').identifier349(function() {
            try {
                $(this).identifier430('Lorem ipsum', 'Lorem ipsum');  // .css('font-size', '...')
            } catch (identifier015) {
                identifier537.identifier538("Lorem ipsum", this);  // console.warn
            }
        });
    } else {
        identifier001.identifier572.identifier414('Lorem ipsum');  // document.documentElement.style.removeProperty(...)
        $('Lorem ipsum').identifier877('Lorem ipsum');  // .removeClass()
    }
};
```

A font-size adjustment system triggered by a setting toggle. Uses CSS custom properties (`:root` style), jQuery `.css()` for elements, with try/catch error handling.

### 4.11 MutationObserver for Links (lines 534–554)

```javascript
if (!identifier122.identifier1022) {
    identifier122.identifier1022 = new identifier1023(function(identifier1024) {  // new MutationObserver
        identifier1024.identifier099(function(identifier1025) {  // .forEach()
            $(identifier1025.identifier1026).identifier282('Lorem ipsum').identifier349(function() {  // .find().each()
                try {
                    $(this).identifier430('Lorem ipsum', 'Lorem ipsum');  // .css()
                } catch (identifier015) {
                    identifier537.identifier538("Lorem ipsum", this);
                }
            });
        });
    });
    const identifier1027 = identifier001.identifier408('Lorem ipsum');  // document.querySelector()
    if (identifier1027) {
        identifier122.identifier1022.identifier1028(identifier1027, {  // .observe()
            identifier1029: true,  // childList
            identifier1030: true   // subtree
        });
    }
}
```

A **MutationObserver** that watches the DOM for added nodes and applies styling to links. `identifier1023` = `MutationObserver`, `identifier1024.identifier099` = `mutations.forEach()`, `identifier1028` = `.observe()`, `identifier1029`/`identifier1030` = `childList`/`subtree` options. This is a sophisticated pattern for dynamically-styled links that handles content added after initial render.

### 4.12 Custom Macro Definitions (lines 611, 624, 628)

Three custom macros registered via `Macro.add()`:

**Macro 1** (line 611): A macro with `identifier1033: ["Lorem ipsum", "Lorem ipsum"]` (likely `tags: ["link", "container"]`) — processes arguments to build navigation links with passage names, handles `<<return>>` and `<<retry>>`-like functionality.

**Macro 2** (line 624): A widget-like macro using a Map (`identifier034 = new identifier148` where `identifier148` = `Map`) for caching. Registers `identifier630.identifier1052` and `identifier630.identifier1053` — likely `jQuery.fn.widget` and `Macro.add` for a `<<widget>>`-style system.

**Macro 3** (line 628): A data-processing macro that converts arrays to objects (`identifier015.identifier028 % 0` check for even-length arrays) and applies content via jQuery `.html()`.

### 4.13 History/Navigation Guard (lines 614–619)

```javascript
$(identifier001).identifier301('Lorem ipsum', function (identifier1044) {
    if (!identifier1044.identifier1045.identifier1033.identifier247('Lorem ipsum')) {  // .includes()
        identifier1046.identifier980.return = identifier1044.identifier1045.identifier1047;
    }
});
```

A `:passageend` or navigation handler that checks passage tags (`.identifier1033` = tags array, `.identifier247` = `.includes()`) and sets a return value on the State object.

### 4.14 Passage End — Debug Logging (lines 636–647)

```javascript
$(identifier001).identifier301('Lorem ipsum', function() {
    const identifier1045 = identifier1040.get(identifier1046.identifier1045);  // Setting.get(State.passage)
    if (identifier1045 && identifier1045.identifier1033) {
        for (let identifier017 = 0; identifier017 < identifier1045.identifier1033.identifier028; identifier017++) {
            if (identifier1045.identifier1033[identifier017] === "Lorem ipsum") {
                identifier975.identifier1055.identifier977(0, "Lorem ipsum" + identifier1045.identifier030);
                break;
            }
        }
    }
});
```

Checks passage tags and calls a debug/logging function (`identifier975.identifier1055.identifier977` = likely `UI.debugBar.watch.add` or `console.log` with passage name).

### 4.15 Navigation Interceptor (lines 650–666)

```javascript
$(identifier001).identifier301('Lorem ipsum', function(identifier1044) {
    if (identifier1044.identifier1056 === 0 && identifier1044.identifier319 === 'Lorem ipsum') {
        identifier1057("Lorem ipsum");  // Engine.go() or Engine.play()
        return false;
    }
    return true;
});
```

Intercepts navigation events — if a specific condition is met (likely back navigation or specific passage), it redirects to a different passage.

### 4.16 Post-Render Link Handler (lines 669–680)

```javascript
identifier1058(function() {  // $(document).ready() or $(function(){})
    $('Lorem ipsum').identifier349(function() {
        $(this).identifier567({                    // .attr()
            'Lorem ipsum': 'Lorem ipsum',
            'Lorem ipsum': 'Lorem ipsum'
        }).identifier610('Lorem ipsum').identifier301('Lorem ipsum', function(identifier015) {
            identifier015.identifier620();           // .preventDefault()
            identifier1057("Lorem ipsum");
            return false;
        });
    });
}, 0);
```

After render, finds specific links, sets attributes, removes a class (`.identifier610('Lorem ipsum')` = `.removeClass()`), and binds click handlers with `preventDefault()`.

### 4.17 UI Bar Toggle (lines 683–692)

```javascript
$(identifier001).identifier693('Lorem ipsum', function() {
    if (typeof identifier975 !== 'Lorem ipsum' && identifier975.identifier1055 && identifier975.identifier1055.identifier1059) {
        identifier975.identifier1055.identifier1059();  // UI.bar.toggle() or .stow()
    }
    identifier529(function() {
        $(identifier001).identifier621('Lorem ipsum');  // .trigger(':passagerender')
    }, 0);
});
```

Toggles the UI sidebar on a specific event, then triggers a re-render after a 0ms timeout.

### 4.18 Final Render Handler (lines 695–706)

```javascript
$(identifier001).identifier301('Lorem ipsum', function() {
    identifier529(function() {  // setTimeout
        const identifier1060 = $('Lorem ipsum');
        if (identifier1060.identifier028 >= 0) {  // .length
            const identifier1061 = $(identifier1060[0]);
            const identifier1062 = identifier1061.identifier282('Lorem ipsum');  // .find()
            if (identifier1062.identifier028 && !identifier1062.identifier336().identifier247('Lorem ipsum')) {
                identifier1062.identifier336('Lorem ipsum');  // .text()
            }
        }
    }, 0);
});
```

Post-render check: finds a specific element, checks its text content, and if it doesn't contain a specific string, overwrites it. Likely a fallback/default content injector.

---

## 5. Third Script Block (script[2], lines 60681–60684)

### 5.1 Conditional Loading

```javascript
if(identifier001.identifier009.identifier038("Lorem ipsum")==="Lorem ipsum"){
    (function(identifier122,identifier001,identifier923,undefined){
        "Lorem ipsum";
        var identifier1063=["Lorem ipsum","Lorem ipsum","Lorem ipsum","Lorem ipsum"],
            identifier1064=["Lorem ipsum","Lorem ipsum"],
            identifier1065=["Lorem ipsum"];
        function identifier1066(identifier020) { ... }  // format parser
        function identifier1070() { throw new identifier109("Lorem ipsum"); }
        function identifier1068(identifier020) { ... }  // Symbol.iterator check
        function identifier1067(identifier020) { ... }  // Array.isArray check
        function identifier1072(identifier034,identifier016) { ... }  // instanceof check
        function identifier1073(identifier015,identifier020) { ... }  // property definition
        function identifier1075(identifier015,identifier020,identifier014) { ... }  // extends/mixin
        function identifier1074(identifier014) { ... }  // string capitalization
        function identifier1076(identifier014,identifier020) { ... }  // string manipulation
        // ... additional engine code ...
    })(identifier122,identifier001,identifier923,undefined);
}
```

This is a **conditionally-loaded engine module** that:
- Checks `identifier001.identifier009.identifier038("Lorem ipsum")` — likely `document.querySelector("...").getAttribute("...")` or `document.currentScript.getAttribute("data-...")` to check the story format
- Only loads if the format matches a specific value
- Contains a **class inheritance/mixin system** (`identifier1075` = extend function, `identifier1073` = define properties, `identifier1072` = instanceof guard)
- Contains array/iterable conversion utilities (`identifier1066` resolves to `Array.from` equivalent with fallbacks)
- `identifier1063` = 4-element array (likely tag names or property names)
- `identifier1064` = 2-element array
- `identifier1065` = 1-element array
- `identifier109` = `TypeError` or `Error`

This is likely the **SugarCube passage format parser** or the ** Wikifier** module that's loaded conditionally based on the story format version.

---

## 6. Cross-Reference with Known SugarCube v2 API

### 6.1 Confirmed API Patterns

| SugarCube API | Anonymized Form | Evidence |
|---------------|-----------------|----------|
| `Setting.add(name, config)` | `identifier966.identifier967("name", {identifier968, identifier969, identifier970, identifier971})` | 3 calls in custom JS, config has onInit/onChange |
| `Config.history.*` | `identifier972.identifier973.*` | 2 property sets |
| `Macro.add(name, config)` | `identifier1032.identifier048("name", {identifier1033, identifier614})` | 3 calls, `identifier1033` = tags, `identifier614` = handler |
| `State.passage` | `identifier1046.identifier1045` | Used in event handlers |
| `State.length` | `identifier1046.identifier028` | History length check |
| `State.tags` | `identifier1045.identifier1033` | Array with `.includes()` |
| `Setting.get()` | `identifier1040.get(...)` | Used in debug handler |
| `Setting.has()` | `identifier1040.identifier152(...)` | Used in macro validation |
| `UI.bar.toggle()` | `identifier975.identifier1055.identifier1059()` | Called in UI toggle |
| `Engine.play()` | `identifier1057("Lorem ipsum")` | Navigation redirect |
| `$(document).on(':passageinit', fn)` | `$(identifier001).identifier693('Lorem ipsum', fn)` | Multiple event handlers |
| `$(document).on(':passageend', fn)` | `$(identifier001).identifier301('Lorem ipsum', fn)` | Multiple event handlers |
| `document.getElementById()` | `identifier001.identifier012("Lorem ipsum")` | Used with `$()` wrapper |
| `document.querySelector()` | `identifier001.identifier408("Lorem ipsum")` | Used in MutationObserver setup |
| `document.documentElement.style` | `identifier001.identifier572` | `.identifier010()` = setProperty, `.identifier414()` = removeProperty |
| `MutationObserver` | `identifier1023` | `new identifier1023(callback)` with `.observe()` |
| `Map` | `identifier148` | `new identifier148` in macro cache |
| `setTimeout` | `identifier529` | `identifier529(fn, 0)` |
| `console.log/warn/error` | `identifier537.identifier141/identifier538/identifier363` | Logging calls |

### 6.2 jQuery Method Mapping

| jQuery Method | Anonymized Form |
|---------------|-----------------|
| `.each()` | `identifier349` |
| `.find()` | `identifier282` |
| `.text()` | `identifier336` |
| `.html()` | `identifier567` (as setter) / `identifier1038` (as DOM creation) |
| `.attr()` | `identifier567` |
| `.css()` | `identifier430` |
| `.data()` | `identifier552` |
| `.addClass()` | `identifier887` |
| `.removeClass()` | `identifier610` / `identifier877` |
| `.on()` | `identifier301` / `identifier693` |
| `.append()` | `identifier709` |
| `.prepend()` / `.prependTo()` | `identifier716` |
| `.slice()` | `identifier064` (on Array) |
| `.splice()` | `identifier051` (on Array) |
| `.push()` | `identifier040` (on Array) |
| `.length` | `identifier028` |
| `.includes()` | `identifier247` |
| `.toString()` | `identifier042` |
| `.prototype` | `identifier063` |

---

## 7. Patterns the Harness Should Be Aware Of

### 7.1 Story Generation Implications

1. **Settings API**: Stories should use `Setting.add()` with `onInit`/`onChange` callbacks. The anonymized code shows 3 settings with different config types — the harness should support generating `Setting.add()` calls in user JS.

2. **Config overrides**: `Config.history.controls` and `Config.history.maxStates` are commonly set. The harness should generate appropriate `Config.*` assignments in the user JS section.

3. **Per-passage config overrides**: The `:passageinit` handler (lines 399–476) dynamically sets 20+ `Config.*` properties based on passage content. This is an advanced pattern — the harness should be aware that some stories override engine config per-passage.

4. **Event-driven architecture**: Stories hook into SugarCube events via `$(document).on(':passageinit', fn)` and `:passageend`. The harness should document these events and potentially generate them in user JS.

5. **MutationObserver usage**: Dynamic content styling uses MutationObserver. The harness should be aware that generated stories may need DOM observation for dynamically-added content.

6. **Theme system**: 5 theme variants switchable at runtime via CSS classes on `<html>`. The harness should support a theme system in generated CSS/JS.

7. **Font-size adjuster**: A setting-driven font size system using CSS custom properties. The harness should consider generating accessibility features.

8. **Custom macros**: 3 custom macros registered via `Macro.add()`. The harness should support generating custom macro definitions in user JS.

9. **Navigation guards**: The `:passageend` handler intercepts navigation based on conditions. The harness should be aware of this pattern for complex branching narratives.

10. **Debug integration**: Passage tags trigger debug bar entries. The harness should support debug-friendly passage tagging.

### 7.2 CSS Generation Implications

1. **User CSS is story-specific**: ~267 lines of custom CSS with theme variants, button styles, sidebar customization. The harness should generate story-appropriate CSS.

2. **CSS `:has()` selector**: Used in dialog styling (line 148) — modern CSS feature. The harness should target modern browsers.

3. **`@import` for fonts**: 3 external `@import` statements at the top of story CSS. The harness should support font imports.

4. **`data-mobile-mode` responsive**: Mobile mode is handled via body attribute, not just media queries. The harness should support this pattern.

5. **sc-icons font**: SugarCube uses an icon font for UI elements (close button, etc.). The harness should preserve references to `sc-icons`.

### 7.3 Engine Structure Implications

1. **Three script blocks**: Engine JS (head), user JS (in tw-storydata), conditional module (after tw-storydata). The harness should maintain this three-block structure.

2. **Feature detection gate**: The engine starts with a feature check before loading. Generated HTML should preserve this pattern.

3. **Conditional module loading**: The third script checks a format attribute before loading. The harness should include this conditional.

4. **jQuery is bundled**: SugarCube bundles jQuery (including throttle/debounce plugin). The harness should NOT include a separate jQuery script tag.

5. **Identifier count**: The engine uses identifiers up to ~identifier1077 (in script[2]). The custom JS uses identifiers 952–1061. Total unique identifiers across the file: ~1077+.

---

## 8. Summary of Key Findings

- **SugarCube version**: **v2.37.3** — confirmed by `color-emoji` font, `sc-icons` with `font-display:block`, `prefers-reduced-motion` media query, `data-init` states, jQuery throttle/debounce bundling, conditional module loading, and harness config alignment.

- **Engine JS** (~696KB): 6 IIFE blocks bundling jQuery core, jQuery extend/events, jQuery full library, jQuery throttle/debounce, and SugarCube's event/state/macro system. All identifiers anonymized to `identifier001`–`identifier1077+`.

- **CSS** (~32KB engine + ~8KB user): 16 engine style blocks covering normalize, loading screen, icon/emoji fonts, core UI, passage transitions, typewriter animation, dialog system, save/settings panels, sidebar, debug bar, debug view. User CSS adds themes, button styles, sidebar customization, portrait styling.

- **Custom JS** (~20KB): 3 `Setting.add()` calls, 2 `Config` modifications, 3 custom `Macro.add()` definitions, 1 `MutationObserver`, 5+ event handlers (`:passageinit`, `:passageend`, navigation), theme switcher, font-size adjuster, navigation guard, debug logger, per-passage config overrides.

- **Third script**: Conditional engine module with class inheritance/mixin utilities and array/iterable conversion — likely the Wikifier or passage format parser.

- **Key APIs visible**: `Setting.add()`, `Config.*`, `Macro.add()`, `State.passage/tags/length`, `Setting.get()/has()`, `UI.bar`, `Engine.play()`, `$(document).on(':passageinit/:passageend')`, `document.documentElement.style`, `MutationObserver`, `Map`.

- **Harness recommendations**: Generate user JS with Setting/Config/Macro APIs, event handlers, theme system, accessibility features. Generate user CSS with theme variants, responsive design, `@import` fonts. Maintain three-script-block structure with feature detection gate and conditional module loading.

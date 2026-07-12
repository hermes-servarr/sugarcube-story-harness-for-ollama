# Executive Summary  
SugarCube is a powerful Twine story format (TwineScript on top of JavaScript/jQuery) that provides a rich macro library, built‑in UI and saving APIs, and broad browser compatibility【14†L439-L447】【17†L127-L131】.  It is open-source (BSD-2-Clause) and actively maintained (current v2.37.x as of 2025)【6†L407-L410】, with version milestones adding support for images (v2.0.0), audio/video (v2.24.0), enhanced APIs, and polyfills for ES5/6 so games run even on ancient browsers【38†L17-L21】【17†L127-L131】.  SugarCube targets both Twine 2 (as “SugarCube 2”) and Twine 1 (legacy “SugarCube 1”), continuing Twine‑1’s feel while expanding features【14†L439-L447】【6†L407-L410】.  

TweeGo is a command‑line tool (free BSD-2-Clause, written in Go) that compiles Twine/Twee projects into playable HTML (or archives)【28†L4-L5】【31†L441-L444】.  It uses a plain-text Twee notation (official Twee v3) so you can write or split passages in code files and then build your game via `tweego`.  By default it targets SugarCube 2 (story format ID `sugarcube-2`) but supports all Twine formats (Twine 2 and Twine 1 ≥v1.4.0)【19†L94-L100】【35†L148-L157】.  TweeGo bundles story passages with external assets (CSS/JS/fonts/images/audio/video) automatically, supports decompiling back to Twee, and offers options for archives and test builds【33†L300-L308】【35†L212-L221】.  

Together, SugarCube and TweeGo enable a modern, text‑based Twine workflow: write and version control your game in text files, use TweeGo to compile to HTML, and deploy to the web.  This report covers the architecture, usage, and integration of SugarCube and TweeGo; example code snippets and project structures; best practices (debugging, optimizing, accessibility); and tooling/hosting resources.  We also include tables of key commands and output formats, a Mermaid build-flow chart, and a step-by-step build checklist.  All information is drawn from official docs and community sources 【6†L407-L410】【19†L94-L100】【21†L591-L597】【39†L41-L49】.

## SugarCube Story Format – Overview and Features  
SugarCube is a **Twine story format** that extends TwineScript (a simplified JS) with many macros and APIs.  It is **designed for advanced projects**, offering features such as built‑in save/load, UI menus, history/jumps, debugging tools, and full control over HTML/CSS/JS.  SugarCube continues the Twine‐1 tradition (rich macros) and goes beyond Twine‑2’s default Harlowe format in functionality【14†L439-L447】.  Key highlights:  

- **Rich macro library** – Includes conditional macros (`<<if>>`, `<<for>>`, `<<switch>>`, etc.), input/output (`<<prompt>>`, `<<textbox>>`), data manipulation (`<<array>>`, `<<set>>`, `<<alert>>`), and media (`<<image>>`, `<<audio>>`, `<<video>>`) among many others.  e.g. `<<if $flag>>…<</if>>` lets you branch on story variables in passages (see examples below).  
- **Full JavaScript integration** – SugarCube story code is essentially JavaScript with added conveniences【17†L72-L79】.  You can call JS methods, use libraries (it ships with jQuery and polyfills【17†L127-L131】), and define custom APIs.  Passages can include `<script>` content via the `script` tag in Twee or external `.js` files.  
- **Interface and UI** – SugarCube provides optional UI elements (history, bookmarks, settings) through its API.  You can customize `Config.ui` and `UI`/`UIBar` objects, or replace the entire story `<div>` with your own HTML【17†L151-L154】.  It handles link navigation via ARIA‑enhanced click handlers, improving accessibility【43†L161-L164】.  
- **Saving and history** – A robust save system (slots, auto-saves) is built‑in. SugarCube records a playthrough history of states to allow “undo”/“restart.”  It also stores story variables to browser storage or disk (even on mobile) and will **resume** a session if a page reload interrupts play【44†L31-L35】.  
- **Media passages** – Starting in v2.0.0 SugarCube supports *image passages* (treat images as passages you can reference)【38†L17-L21】.  From v2.24.0 it also adds audio and video passages, allowing embedding media with `<audio>`/`<video>` via macros or passage references.  
- **Story variables** – Supports two types: *story* (persistent in history/save) and *temporary* (per turn).  SugarCube serializes variables intelligently, auto-interpolates them in text (naked `$variable` syntax)【16†L739-L748】, and provides array/object helper methods.  
- **Architecture/compatibility** – SugarCube outputs a single HTML+JS that runs in the browser.  It is compatible with Twine 2 (as JSON‑P format) and Twine 1 (via a Python formatter).  The SugarCube distribution includes both Twine‑1 and Twine‑2 versions of the format.  It bundles jQuery and polyfills (ES5/6 shims) to support older browsers【17†L127-L131】.  
- **Version history** – SugarCube is continuously updated.  Major changes include image passages (v2.0.0), audio/video/VTT (v2.24.0), numerous new macros/APIs each release, and UI improvements.  The latest v2.37.x (Jan 2025) includes fixes for event handling, debugging, and TwineScript enhancements.  (For full changelogs, see its [GitHub releases](https://github.com/tmedwards/sugarcube-2/releases) and upgrade guides.)  
- **Licensing** – SugarCube is free/libre under the BSD-2-Clause license【6†L407-L410】.  It may be used and modified in commercial or open games without restrictions.  

SugarCube’s documentation (Motoslave.net) is comprehensive: see its **Features and Macros** guide for details on every macro and API.  In practice, authors praise SugarCube’s power (e.g. advanced math, collections, UI) though it may have a steeper learning curve than simpler formats【14†L439-L447】【43†L161-L164】.  For example, it automatically uses ARIA-enabled links and roles for better accessibility【43†L161-L164】【43†L170-L173】.  In summary, SugarCube is ideal for developers needing full control over their Twine game’s logic and presentation, especially on web platforms.

## TweeGo CLI – Purpose and Usage  
TweeGo is a **command-line compiler for Twine/Twee projects**【28†L4-L5】.  Instead of using the Twine GUI, you write your story in text files (Twee v3 format) and then run `tweego` to compile to a playable HTML (or archive).  This enables version control, multi-file organization, and automated builds.  

- **Installation**: Download the appropriate binary from the [official site](https://www.motoslave.net/tweego/) (v2.1.1, 2020) or build from source.  It’s distributed as executables for Windows, macOS, and Linux【28†L38-L47】.  (On macOS/Linux, ensure the binary is executable and on your PATH.)  Story formats (like SugarCube) should be placed in `storyformats/` directories alongside the binary or in home/current folder【35†L148-L157】.  In VSCode setups, you can simply copy a `sugarcube-2` folder into your project.  
- **Basic command**: `tweego [options] <sources…>`【35†L203-L212】.  Sources can be files or directories.  For example, `tweego -o game.html src/` compiles all `.twee`, `.html`, `.js`, etc. in `src/` into `game.html`.  By default, the output goes to standard output (`-`), so always specify `-o file.html`.  The default story format is **SugarCube 2** (ID `sugarcube-2`)【19†L94-L100】.  
- **Key options**:  
  - `-o FILE` (`--output`): set output HTML file【35†L272-L279】.  
  - `-f NAME` (`--format`): override story format (e.g. `-f snowman`)【20†L31-L39】【35†L235-L243】.  The ID typically matches the format’s directory name.  
  - `-s NAME` (`--start`): set starting passage name (default from StoryData or “Start”)【35†L273-L279】.  
  - `-m PATH` (`--module`): specify a *module* directory whose .css/.js files are wrapped and injected into the HTML `<head>`【35†L258-L264】.  (Useful for external scripts or styles.)  
  - `--head=FILE`: append a file’s contents into the `<head>` unmodified【35†L239-L247】.  
  - `-w` (`--watch`): rebuild automatically when sources change (for live editing).  
  - `-t` (`--test`): enable story-format *test mode* (works for Twine-2 formats only).  
  - `-a/--archive-twine2`, `--archive-twine1`: output a Twine 2 or Twine 1 archive instead of HTML【35†L212-L221】.  
  - `-d/--decompile`: output raw Twee source (Twee v3 or v1) from an HTML story【35†L222-L231】.  
  - `--list-formats`, `--list-charsets`: list installed story formats or charsets.  
  - `-l` (`--log-stats`): print story stats (passage/word count).  
  - `-h` (`--help`): show all options.  

  Table: **Tweego Output Modes** (file types)【35†L212-L221】【35†L224-L233】:

  | Output Type       | Description                                            | Option                    |
  |-------------------|--------------------------------------------------------|---------------------------|
  | **Compiled HTML** | Single HTML file with all passages & assets (default)  | *(no flag)*               |
  | **Twine2 Archive** (`.tws`)  | Twine 2 story archive (JSON-P) instead of HTML  | `--archive-twine2`        |
  | **Twine1 Archive/HTML**      | Twine 1 story (.html or .tws)            | `--archive-twine1`        |
  | **Twee3 Text**    | Decompile to Twee v3 source text (.twee)              | `-d` (`--decompile-twee3`) |
  | **Twee1 Text**    | Decompile to Twee v1 source                           | `--decompile-twee1`       |

- **Supported source files**: Tweego recognizes files by extension【33†L300-L308】.  It will recurse directories given as sources【33†L357-L362】.  Supported extensions include: passages in `.tw`, `.twee`, `.html` (embedded), `.css`, `.js` (bundled into output), fonts (`.otf .ttf .woff` etc), images (`.png .jpg .gif .svg` bundled as *image passages*), audio/video files (bundled as special passages)【33†L300-L308】.  (For example, `rainboom.jpg` becomes an image passage named “rainboom”【33†L318-L324】.)  Non-code assets (fonts, images, audio, video) are automatically included by Tweego: CSS/JS are injected into `<head>`; images/audio/video become in-game media passages (SugarCube natively supports these)【33†L318-L326】【33†L327-L335】.

- **Story configuration (StoryData)**: In Twee, a `StoryData` passage (JSON) can set global settings.  For Twine 2 formats, you typically include at least an `"ifid"` (Interactive Fiction ID), and can specify `"format"` (story format name) and `"format-version"` (semantic version).  Example:  

  ```twee
  :: StoryData
  {
    "ifid": "D674C58C-DEFA-4F70-B7A2-27742230C0FC",
    "format": "SugarCube",
    "format-version": "2.30.0",
    "start": "Entry"
  }
  ```  

  If absent, Tweego will auto-generate an IFID on first compile and prompt you to copy it in【39†L69-L73】.  The `"format"` property tells Tweego which story format ID to use (e.g. `"SugarCube"` or `"Harlowe"`), and `"format-version"` can pin a major version.  Tweego will then pick the highest installed version matching that major release【21†L562-L570】【21†L574-L582】.  (If you omit these, Tweego defaults to `sugarcube-2`.)  

In summary, TweeGo’s purpose is to **build and package Twine games from text**.  It replaces the Twine GUI by letting you author in any editor and compile via script.  Using `tweego` you can easily integrate Twine into version control and automated workflows (see Tooling & CI below).  

## Workflow: Building a SugarCube Game with TweeGo  
A typical development workflow is: **write** passages/assets → **build** with TweeGo → **test/deploy**.  Below is a practical step-by-step outline, illustrated with commands and a flowchart:

```mermaid
flowchart LR
    A[Edit source files (Twee, .js, .css, assets)] -->|tweego -o game.html src/| B[Compiled HTML]
    B --> C[Test in browser]
    C -->|Iterate| A
    B --> D[Deploy (GitHub Pages, itch.io, etc.)]
    D --> U[Players access game]
```

1. **Set up project structure**.  Organize your files, e.g.:  
   - `/src/` – contains your `.twee` passages (Twine content), plus any `.js`, `.css`, `.html` partials.  
   - `/assets/` (optional) – images, audio, video to include. Tweego will pick these up from inside `src/` or any folders you list.  
   - `StoryData` – include a passage (in a .twee file) with JSON config (IFID, format, start passage) as shown above.  
   - **(Optional)** `storyformats/sugarcube-2/` – copy the SugarCube format folder here if you want the project to carry its own format.  
   - You might have a build or output directory (or specify output path).  

   **Example project tree** (see code block below) might look like:  

   ```
   MyGameProject/
   ├─ storyformats/
   │    └─ sugarcube-2/          (optional local copy of SugarCube format files)
   ├─ src/
   │    ├─ game.twee            (passages and macros)
   │    ├─ StoryData.twee       (IFID, format, start)
   │    ├─ styles.css           (CSS to include)
   │    ├─ app.js               (JS to include)
   │    └─ images/
   │         └─ background.jpg   (image asset)
   └─ game.html                (generated by TweeGo)
   ```

2. **Write passages in Twee**.  Use an editor (e.g. VSCode with “Twee” extension【39†L52-L59】) to create passages:  

   - **Passage syntax**: Start each passage with `:: PassageName [tags] {metadata}`.  In Twee v3, you usually do `:: Start` (no tags) for your first passage.  Then below it write the content and TwineScript macros.  
   - **Macros**: Use SugarCube macros like `<<if>>`, `<<set>>`, etc.  Example passage:  
     ```twee
     :: Entry
     <<set $score = 0>>
     Welcome, adventurer.
     <<if $score == 0>>
       You have no points yet.
     <</if>>
     [[Start Game|GameStart]]
     ```  
     This sets a story variable, prints text conditionally, and creates a link to another passage.  
   - **Assets and code**: Put your CSS/JS in files. Tweego will bundle any `.css` or `.js` it finds by default【33†L300-L308】. (Alternatively, you can create passages tagged `script` or `stylesheet` to include code, but external files are easier for larger projects.)  

3. **Compile with TweeGo**.  In a shell/command prompt, run a Tweego command pointing at your source.  E.g.:  
   ```bash
   tweego -o game.html src/
   ```  
   This tells Tweego to take everything under `src/` and build `game.html`.  It will recursively find `.twee` passages, and auto-bundle `styles.css`, `app.js`, images, etc. You can also add flags: e.g. `-w` to watch for live builds, or `-s Entry` to set a non-default start passage.  If you have a StoryData passage with `"format": "SugarCube"`, Tweego will use SugarCube; otherwise it defaults to sugarcube-2【19†L94-L100】.  

4. **Test the output**.  Open the generated `game.html` in a browser.  The compiled HTML includes SugarCube’s engine, your passages, and assets.  If using `-w`, Tweego will auto-rebuild on changes; otherwise rebuild manually after edits.  The browser console may show build or macro errors.  Common flags for testing: `--log-stats` to see word counts, `--log-files` to list included files【35†L244-L253】.  

5. **Iterate and debug**.  SugarCube offers debug tools: enable *Test Mode* (`-t`) to see all passages or use its debug bar.  Check the Tweego help (`tweego -h`) for tips on errors.  If something breaks, check for JSON errors in `StoryData`, unmatched macro tags, or missing assets.  

6. **Package the game**.  Once satisfied, you have a standalone `game.html` that can be hosted anywhere (see Tools/Hosting below).  All assets are embedded by default, except images/audio/video which remain as separate files referenced by the HTML.  (For offline packaging, you could zip the HTML plus media.)  

**Build Checklist:**  

- [ ] Install Tweego and SugarCube format (or copy into project)【28†L38-L47】【35†L148-L157】.  
- [ ] Create `StoryData` passage with a unique IFID (Tweego can auto-generate)【39†L69-L73】【21†L591-L597】.  
- [ ] Write passages in `.twee` with correct syntax (`:: PassageName`) and SugarCube macros.  
- [ ] Place CSS/JS/fonts/images in project; verify Tweego picks them (extensions `.css`, `.js`, images: `.jpg/.png/.svg`, audio `.mp3/.ogg`, video `.mp4/.webm`, etc【33†L300-L308】).  
- [ ] Run `tweego -o output.html src/` (and add flags as needed).  
- [ ] Test HTML in browser; use `--watch` during dev for live reloading.  
- [ ] (Optional) Create a build script or VSCode task as in [39], or set up CI to run tweego on pushes.  

## Integration: SugarCube + TweeGo Details  
TweeGo seamlessly integrates SugarCube content and assets into the compiled HTML.  Key points:  

- **Story format files**: SugarCube’s JavaScript engine (and its HTML template) is included based on the chosen format.  With SugarCube-2 installed, Tweego injects the SugarCube runtime and any bundled macros into the `<head>` of the output HTML.  You do **not** need to manually include SugarCube scripts; they come from the format directory.  If multiple versions of SugarCube are installed, specify `StoryData.format-version` or use `-f sugarcube-2` to choose.  

- **Macros and passages**: TweeGo does *not* interpret SugarCube macros itself – it simply wraps your Twee content into the SugarCube framework.  For example, your `<<if>>` or `<<cycle>>` macros appear as-is in the compiled HTML and are executed by SugarCube’s engine in the browser.  (However, Tweego will validate Twee syntax.)  All passage text (including `<nowiki>`/triple-quote escapes) is preserved.  

- **Assets and modules**:  
  - **JavaScript/CSS**: Any `.js` or `.css` file in your source is automatically inlined or linked.  By default, Tweego bundles them by wrapping in `<script>` or `<style>` in the `<head>`【33†L300-L308】.  You can also use `:: SomePassage [script]` or `[stylesheet]` to inject code via passages, but using external files is common.  Use `-m` to include an entire folder of JS/CSS if you want modular code in head【35†L258-L264】.  
  - **Images/Audio/Video**: Files like `.jpg/.png/.mp3/.ogg/.mp4` in your project are turned into special *media passages*【33†L318-L326】【38†L17-L21】.  For example, `background.jpg` yields an image passage named “background”; you can refer to it in SugarCube by its passage name.  These files remain separate in the output bundle (not base64-embedded), so they are loaded at runtime by the browser.  Ensure their paths are correct relative to the HTML.  
  - **Fonts**: Font files (`.otf/.ttf/.woff`) are bundled as `@font-face` rules【33†L314-L322】.  Tweego generates CSS to import them, naming the font by filename.  

- **StoryData and metadata**: If you include `StoryTitle` or `StorySubtitle` passages, Tweego uses them (e.g., inserting the title into `<title>`).  Special Twee tags (`script`, `stylesheet`) signal code content【21†L606-L614】, but as noted, external files often replace these needs.  Tweego will also generate missing passage metadata (positions/sizes) for compiled HTML; you typically ignore these in source.  

- **Twee notations**: By default Tweego uses the **Twee v3** notation.  You should avoid the obsolete Twee v1/v2 forms unless needed for legacy.  (If you do need Twee2 .tw2 files, use `--twee2-compat`.)  You can mix multiple `.twee` files – the order doesn’t matter as long as all are passed or in the source directory.  

In essence, TweeGo treats your SugarCube content as the *payload* of the compilation, and its job is to assemble it with the right SugarCube runtime and HTML template.  You rarely see the HTML template itself, but it includes a `<div id="story" role="main">` container where your passage output will appear【17†L151-L154】.  

## Examples and Sample Project Structure  

Below are example snippets illustrating Twee notation, SugarCube macros, and StoryData configuration.  These are minimal examples; in practice passages can be as complex as you need.  **(Note:** lines starting with `::` mark passage headers in Twee syntax.)  

```twee
:: StoryData
{
    "ifid": "D674C58C-DEFA-4F70-B7A2-27742230C0FC",
    "format": "SugarCube",
    "format-version": "2.30.0",
    "start": "Entry"
}
```
*Example StoryData passage (JSON): sets the IFID and tells TweeGo to use SugarCube 2.30.0. The starting passage is "Entry".*【21†L591-L597】

```twee
:: Entry
<<set $score = 0>>
Welcome, adventurer.
<<if $score == 0>>
  You have no points yet.
<</if>>
[[Start Game|GameStart]]
```
*Example game passage: initializes a story variable `$score`, prints a message, uses an `<<if>>` macro to show conditional text, and creates a link (`[[text|PassageName]]`) to another passage "GameStart".*  

```twee
:: StoryInit [script]
console.log("Initializing story...");
setup.message = "Ready!";
```
*Example passage tagged `script`: this JavaScript code runs on story start. It will be placed inside a `<script>` element. (Alternatively, you could put this JS in an external `.js` file in the source.)*  

```twee
:: Styles [stylesheet]
body { font-family: Arial, sans-serif; background-color: #f0f0f0; }
```
*Example passage tagged `stylesheet`: CSS rules injected into the page’s `<head>`. (Or use an external `.css` file in the project.)*  

Finally, a **sample project directory tree** might look like:  
```
MyGameProject/
├─ storyformats/
│    └─ sugarcube-2/          (copy of SugarCube format files; Tweego will load from here)
├─ src/
│    ├─ Entry.twee           (Twee file with one or more passages, including StoryData)
│    ├─ styles.css           (custom CSS – TweeGo will bundle this)
│    ├─ app.js               (custom JS – will be bundled)
│    └─ images/
│         └─ background.jpg   (image asset, appears as an image passage)
└─ game.html                (output of `tweego -o game.html src/`, not under src)
```  
This shows a common layout.  In VSCode (see [39]), one often puts sources in a `src` folder and tells Tweego to compile that folder.

## Best Practices, Pitfalls, and Debugging  

- **Use UTF-8 encoding**. Ensure all your `.twee`, `.js`, `.css` files are saved in UTF-8.  Tweego defaults to UTF-8【19†L87-L95】 and may misinterpret others.  
- **Keep passages manageable**. A very large passage (lots of content or heavy logic) can slow down editing.  Consider splitting content into smaller passages linked by `[[ ]]`.  Community advice suggests grouping linear text to reduce Twine editor lag【24†L158-L167】, though Tweego itself can handle many passages.  
- **Watch mode**. During development, use `tweego -w` to auto-rebuild on file changes.  This can be integrated into a text editor or build task for instant feedback【39†L117-L125】.  
- **IFID**. If your StoryData lacks an `"ifid"`, Tweego will generate one the first build【39†L69-L73】.  For consistency (and to preserve save files), copy that IFID into StoryData so it stays stable.  
- **Logging**. Use `--log-stats` to print passage and word counts after build; this can help spot unexpected additional passages. Use `--log-files` to list exactly which files were processed.  
- **Test Mode**. SugarCube’s *Test Mode* (enable with `-t`) shows hidden passages (tagged `script`/`stylesheet`, story interface controls) and is useful for debugging story flow.  Refer to SugarCube docs “Test Mode” guide for details.  
- **Asset paths**. Ensure image/audio paths in your story (e.g. `<<audio "track.mp3">>`) match the file names.  Tweego will bundle `track.mp3` only if it’s in the source or module path.  If something is missing in the output, check filename typos.  
- **Whitespace & formatting**. By default, Tweego trims whitespace between passages. Normally this is fine, but if you need precise spacing, you can disable trimming with `--no-trim`【35†L264-L272】.  Extra blank lines or indent in `<<if>>` may be significant.  
- **JSON syntax**. In StoryData JSON, use double quotes around property names and no trailing commas.  Invalid JSON here will break compilation.  (Tweego will report JSON errors in the console.)  
- **Story formats loading**. Tweego finds story format directories in certain paths【35†L170-L179】.  If it says “format not found”, ensure you have the SugarCube format folder (`sugarcube-2`) in one of the `storyformats` directories (current dir, home, or Tweego binary folder).  You can also use `--list-formats` to debug format availability.  
- **Common pitfalls**:  
  - Mixing Twee notations: stick to Twee v3 unless you have legacy `.tw2` files.  
  - Editing compiled HTML: do *not* modify the generated HTML by hand; always change the source `.twee`.  
  - Version mismatches: if you specify `"format-version": "2.30.0"` but only have SugarCube 2.25 installed, TweeGo will pick 2.25 or error. Use `--list-formats` to see installed versions.  

For debugging: check the console output of Tweego for errors.  If Tweego fails silently, try `tweego -v` (verbose) or inspect the generated HTML in a text editor.  You can also decompile a working `game.html` with `tweego -d` to see its Twee3, which helps verify correct story data.  

## Performance & Web Optimization  

Because SugarCube games run in the browser, you should optimize like any web project: minimize file sizes and resource usage. Tips:  

- **Media optimization**: Compress images and audio before including them.  Large PNG/JPEG can bloat the game; consider WebP or lower-resolution images for mobile.  SugarCube does not auto-compress assets.  Use tools like TinyPNG or `image` libraries to batch-optimize.  
- **Minify CSS/JS**: Tweego bundles your CSS/JS as given.  If you have large libraries, consider minifying or only including needed parts.  (For example, you can remove large unused code from your scripts, since SugarCube already includes jQuery.)  
- **Limit polyfills**: SugarCube includes ES5/ES6 shims by default【17†L127-L131】 for compatibility with old browsers.  If you’re certain your audience uses modern browsers, you might customize SugarCube to drop some polyfills (advanced users) to reduce size.  Otherwise, this overhead is usually acceptable.  
- **Story size**: Very long word counts will slow down initial load and autosaving.  SugarCube’s recent versions improved performance for large histories (see 2.37 notes【8†L312-L321】).  Store only necessary variables in story-state (avoid huge arrays if possible).  
- **Testing on devices**: Test the final HTML on target devices/browsers.  SugarCube is broadly compatible (desktop, mobile browsers) out of the box.  It even persists state when mobile browsers unload tabs【44†L31-L35】.  Audio/video uses HTML5 media (volume control on mobile is hardware-governed【44†L24-L30】).  

In general, treat the compiled HTML as a web page: use browser dev tools to audit performance, and implement lazy-loading or smaller assets as needed.  The goal is a smooth play experience, especially on slower connections or phones.

## Tooling, Extensions, and Hosting  

A modern Twine+Twee development setup often includes:  

- **Editors**: While Twine’s GUI editor (Twine 2 app or twinery.org) can import/export JSON, many developers prefer code editors.  Visual Studio Code is popular; it has extensions for Twee syntax (e.g. “Twee Language Tools”)【39†L54-L58】 and SugarCube highlighting【41†L96-L100】.  Other text editors (Sublime, Atom, Vim) can also handle simple text.  Use git for version control of your text files.  
- **Tweego integration**: You can configure VSCode (tasks.json) or other IDEs to run `tweego` automatically.  As [39] shows, you might set the build command to `"tweego -w -o index.html src"` so VSCode auto-builds on save, and mark it as a background task【39†L119-L127】.  
- **Project templates**: The community offers starter kits.  For example, ChapelR’s [SugarCube Starter](https://github.com/chaper/sugarcube-starter) and tiny-qbn’s [minimal template](https://joshuagrams.github.io/tiny-qbn/doc/tweego.html) automate folder structure and tasks.  On itch.io, manonamora’s “Ready-to-Use Tweego Folder” provides a preconfigured setup.  
- **CI/CD and Hosting**: It’s common to use **GitHub Actions** to build and deploy Twine games.  For instance, Emilia Lazer-Walker’s workflow (Dev.to) shows how pushing to GitHub can auto-run TweeGo and publish on **GitHub Pages**【41†L67-L70】.  This makes your game instantly playable at a GitHub Pages URL.  Similarly, you can use Netlify or other static hosts (itch.io, Surge.sh, etc.) to serve the single HTML.  
- **Debugging tools**: Besides SugarCube’s debug bar, browser devtools are invaluable (JS console, network inspector to check asset loads, etc.).  For Twine-specific debugging, community plugins (like Ron the Rat’s Debug Bar) can help.  
- **Community resources**: The [Twine Cookbook](https://twinery.org/cookbook/) and SugarCube docs are primary references.  The Twine Forum and IF community (intfiction.org) have many Q&As and tutorials (including accessibility guides).  For SugarCube specifics, see Markus “tmedwards” Mikulic’s [SugarCube documentation](https://www.motoslave.net/sugarcube/2/docs/) and [Tweego docs](https://www.motoslave.net/tweego/docs/) (official).  Reddit r/twinegames and the Twinery Discord are also active places to ask questions.  

## Browser/Mobile/Accessibility Notes  

SugarCube games compile to standard HTML/JS, so they run on all modern browsers (Chrome, Firefox, Safari, Edge) on desktop and mobile.  Thanks to jQuery and shims, even older browsers (IE11+) will typically work.  Mobile support: SugarCube has special handling for mobile quirks.  For example, modern mobile browsers may unload background tabs; SugarCube auto‑saves and restores playthroughs on reload【44†L31-L35】.  Audio controls rely on device defaults (volume sliders)【44†L24-L30】.  

Accessibility: SugarCube was designed with ARIA and screen-readers in mind.  It uses `role="main"` for the story container and ARIA-enabled links【43†L161-L164】.  Community feedback notes that SugarCube (and “Snowman” story format) are quite screen-reader-friendly【43†L161-L164】【43†L170-L173】, whereas Harlowe has some known issues.  As a developer, you should still use good practices: include alt text in images, make menus navigable by keyboard, and structure content semantically.  The built-in SugarCube UI and wiki links are typically accessible, but always test with a screen reader if accessibility is a priority.  

## Tables of Commands and Tips  

**Common Tweego Commands** (compare to GUI Twine actions):

| Task                          | TweeGo CLI Example                                                |
|-------------------------------|-------------------------------------------------------------------|
| **Build HTML**                | `tweego -o game.html src/` (default SugarCube format)            |
| **Specify format**            | `-f SugarCube` or `--format=sugarcube-2`                         |
| **Set start passage**         | `-s Entry` or `"--start=Entry"`                                  |
| **Include module files**      | `-m modules/` (bundles CSS/JS in `modules/` into `<head>`)       |
| **Watch mode**                | `-w` (auto-rebuild on file changes)                               |
| **Logging stats**             | `-l` (counts passages, words)                                    |
| **List installed formats**    | `--list-formats` (to confirm SugarCube is found)                 |
| **Decompile to Twee**         | `-d -o story.twee game.html` (extracts source from HTML)         |
| **Build Twine2 archive**      | `--archive-twine2` (outputs a `.tws` file instead of HTML)       |

**Supported Source File Types** (Tweego recognizes and bundles these):

| Extension(s)                   | Treatment in build                                               |
|-------------------------------|-------------------------------------------------------------------|
| `.twee`, `.tw`                | Twee passage files (Twee v3) – compiled into the story.           |
| `.html`, `.htm`               | Twine/Twee HTML archives – passages extracted and merged.         |
| `.css`                        | CSS files – wrapped into `<style>` in `<head>`.                   |
| `.js`                         | JavaScript files – wrapped into `<script>` in `<head>`.          |
| `.png`, `.jpg`, `.gif`, `.svg`| Image files – bundled as SugarCube *image passages*.             |
| `.mp3`, `.ogg`                | Audio files – bundled as *audio passages* (SugarCube ≥v2.24.0).   |
| `.mp4`, `.webm`               | Video files – bundled as *video passages* (SugarCube ≥v2.24.0).   |
| `.otf`, `.ttf`, `.woff`       | Font files – bundled via `@font-face` rules.                      |

## Further Reading and Resources  

- **SugarCube Documentation** – Complete reference and guides: [motoslave.net/sugarcube/2/docs](https://www.motoslave.net/sugarcube/2/docs/) (e.g. *Guide: Macros*, *Installation*, *Code Updates*, *API*).  
- **TweeGo Documentation** – Official manual: [motoslave.net/tweego/docs](https://www.motoslave.net/tweego/docs/) (contains usage, examples, FAQ).  
- **Twine Wiki/Cookbook** – Story format comparisons and tutorials: [twinery.org/cookbook](https://twinery.org/cookbook/story-formats.html).  
- **Twine Community** – Help forum and Discord: [Twine Forum](https://twinery.org/forum) and [r/twinegames](https://www.reddit.com/r/twinegames/) (users often share tips and troubleshooting).  
- **Developer Blogs**: *A Modern Developer’s Workflow for Twine* (Em Lazer-Walker) covers text-based Twine with GitHub Actions【41†L64-L72】【41†L147-L154】; *Tweego & VSCode* (tiny-qbn by Joshua Grams) has setup examples【39†L41-L49】【39†L119-L127】; *Idrelle Games Tweego Guide* (idrellegames blog) outlines using Tweego for a real game【24†L158-L167】【39†L43-L49】.  
- **Story Format Repos**: SugarCube on GitHub ([tmedwards/sugarcube-2](https://github.com/tmedwards/sugarcube-2)) – see README, releases and issues for technical details; Tweego on GitHub ([tmedwards/tweego](https://github.com/tmedwards/tweego)) – for source and release notes.  

By combining SugarCube’s powerful in-game features with TweeGo’s flexible build system, developers can create rich HTML story games in a modern, code-centric workflow. 


# SugarCube Agentic Story Harness

A local, single-user harness for co-authoring branching SugarCube stories with a human author and an Ollama model.

The harness owns the mechanical work: passage files, links, graph metadata, state variables, media slots, snapshots, validation, and Tweego compilation. The model is treated as a prose and beat generator, not a filesystem actor.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Ollama](https://ollama.com) running locally with at least one model pulled (e.g. `ollama pull llama3.2`)
- [Tweego](https://www.motoslave.net/tweego/) on your PATH (only needed for `compile`)
- [Playwright](https://playwright.dev) browsers (only needed for `playtest`)

## Quick Start

```bash
# Clone and install dependencies
git clone https://github.com/hermes-servarr/sugarcube-story-harness-for-ollama.git
cd sugarcube-story-harness-for-ollama
uv sync
uv run playwright install --with-deps chromium

# Create a new story project
uv run harness init my-story --title "My Story"

# Start the web UI
uv run harness serve my-story
```

Then open `http://127.0.0.1:8765`.

Useful commands:

```bash
uv run harness validate my-story       # Run validation checks
uv run harness compile my-story        # Compile to HTML via Tweego
uv run harness rebuild my-story        # Rebuild story.json from .tw files
uv run harness rag-reindex my-story    # Build inspiration vector index
uv run harness rag-status my-story     # Show index stats
uv run harness generations my-story    # List persisted model generations
```

## Headless Playtester

The harness includes an automated playtester that drives compiled SugarCube HTML games in a headless Chromium browser. It explores all branches, detects issues (broken links, dead ends, JS errors, rendering problems), and generates a structured report.

```bash
# Compile a story, then playtest it
uv run harness compile my-story
uv run python scripts/playtest_game.py my-story/build/story.html

# Run the full E2E test (generates a story, compiles, and playtests)
uv run python scripts/e2e_test.py
```

The playtester uses:
- `harness/playtest/browser.py` - Playwright-based headless browser driver
- `harness/playtest/explorer.py` - Branch-coverage exploration engine
- `harness/playtest/detector.py` - Issue detection (broken links, dead ends, JS errors)
- `harness/playtest/report.py` - Structured report generation
- `harness/playtest/runner.py` - Orchestrates the full playtest pipeline
- `harness/playtest/task_creator.py` - Creates kanban tasks for detected issues

## Snapshot Deltas

Each passage records a SnapshotDelta (diff from parent snapshot) alongside its full snapshot, so you can trace how the story state changes across choices without storing redundant copies.

## Example Story: The Cartographer's Dilemma

The `examples/the-cartographers-dilemma/` directory contains a fully generated multi-arc story with 5 arcs and 20 passages, produced entirely by the harness using Ollama's llama3.2 model:

- `premise.md` - Story premise
- `story.json` - Story graph manifest
- `story_points.md` - Story beats and planning
- `arcs/` - Twee source files organized by arc (awakening, the_guild, the_frontier, the_betrayal, the_choice)
- `the-cartographers-dilemma.html` - Compiled standalone HTML game (502KB, SugarCube v2.30.0)

To play it, just open the HTML file in any browser. No server needed.

## Running Tests

```bash
uv run pytest
```

Test coverage includes:
- Core harness tests (models, parsers, validation, compile)
- Snapshot delta tests
- Playtester tests (detector, report, task creator, E2E)
- Playwright smoke and E2E playtest tests
- Golden path and P7 invariant tests

## Project Shape

- `my-story/story.json` is the graph manifest.
- `my-story/arcs/<arc>/*.tw` contains one Twee passage per file.
- `my-story/premise.md` and `my-story/story_points.md` guide generation.
- `my-story/characters/` and `my-story/lore/` store approved world facts.
- `my-story/media/_slots.json` tracks media placeholders; the harness never moves media files.
- `my-story/build/story.html` is the compiled output and should be treated as disposable.
- `examples/html_templates/` contains 7 curated SugarCube HTML templates (CC-BY by manonamora) for reference and reuse.
- `docs/` contains the SugarCube 2 documentation (from tmedwards/sugarcube-2) and the harness improvement analysis.

## HTML Templates (examples/html_templates/)

The `examples/html_templates/` directory contains 7 curated SugarCube HTML templates by **manonamora**, licensed under **CC-BY**. These templates target **SugarCube v2.37.3** and were verified byte-for-byte against the upstream repository (github.com/manonamora/Twine-Template, commit 3f8fa40, January 2026).

**Attribution:** Template made by manonamora on Twine 2/Tweego with SugarCube (v2.37.3). The CC-BY license requires crediting the author. Each template includes a `READ ME.txt` with usage notes and an `IFID CHANGE.txt` file (a new IFID must be generated before use).

### Template Catalog

| Template | Category | Key Feature |
|---|---|---|
| Character Creator | Code Template | Multi-page character creation with widgets and stat bars |
| Settings | Code Template | Settings API showcase (range, toggle, list, dialog) |
| One Page | UI Template | Single-page UI with dropdown menu, accessibility options |
| Simple Book | UI Template | Book metaphor with toggleable sides, FontAwesome |
| Space-Tech UI | UI Template | Dual-theme (Space/Tech) with stats widgets, tag-driven CSS |
| Title Page | UI Template | Multiple title page layout variants |
| VN-lite RPG | UI Template | Visual-novel layout with character image areas |

### Using the Templates

Each template directory contains:
- A ready-to-use compiled HTML file
- Source files (`.tw`, `.js`, `.css`) for Tweego
- Annotated passages, JavaScript, and stylesheets

To use a template as a starting point for your own story, copy the source files into your story's `arcs/` directory and modify them. The harness generation pipeline can produce passages that follow the SugarCube macro patterns demonstrated in these templates (see the SugarCube 2 documentation analysis below for details).

### Custom Macro Dependencies

Two templates use Chapel's custom macro packages (not included):
- **Chapel's Dialog API v1.3.0** (`<<popup>>`, `<<dialog>>`, `dialogclose`): One Page, Simple Book
- **Chapel's Notify v1.1.1** (`<<notify>>`): Settings, Simple Book

If you use these templates, install the corresponding macro packages in your Tweego modules directory (configured via `tweego_module_dirs` in your story config).

### FontAwesome

Simple Book and VN-lite RPG templates require FontAwesome 6 for their icon sets. Include the FontAwesome CSS via `tweego_head_file` or a module directory.

### Verification Report

`examples/html_templates/TEMPLATE_VERIFICATION_REPORT.md` contains a detailed verification report and feature catalog. It documents each template's passages, SugarCube macros, functions, API calls, CSS hooks, passage tags, custom macro dependencies, and reusable patterns mapped to harness generation considerations.

## SugarCube 2 Documentation (docs/)

The `docs/` directory contains the SugarCube 2 documentation sourced from the **tmedwards/sugarcube-2** repository (develop branch). The documentation is organized into:

- `introduction.md`, `table-of-contents.md`
- `core/` - markup, macros, functions, methods, twinescript, events, html, css, special-names
- `api/` - config, setting, state, passage, story, engine, save, dialog, fullscreen, loadscreen, ui, uibar, template, macro, macrocontext, simpleaudio
- `guides/` - installation, code-updates, harlowe-to-sugarcube, icon-font, localization, media-passages, non-generic-object-types, state-sessions-and-saving, test-mode, tips, typescript
- `templates/` - html, css, js (build tooling)

These 42 markdown files are the authoritative reference for SugarCube 2 capabilities and were used as the basis for the harness improvement analysis.

### SugarCube 2 Analysis (docs/sugarcube2-analysis.md)

`docs/sugarcube2-analysis.md` is a structured analysis of all 40 SugarCube 2 documentation files against the harness codebase. It identifies 22 harness improvement opportunities across 4 priority levels:

**P1-Critical (compatibility and validation):**
- Replace `<<actions>>` macro (deprecated v2.37.0) with link-based hub rendering
- Add missing container macros (`silent`, `do`, `script`, `done`) to validation
- Add deprecated macro/feature detection to validation checks

**P1-High (generation quality):**
- Add SugarCube variable scoping guidance to prompts (`$` vs `_` vs `setup`)
- Add SugarCube markup cheat sheet to full/JSON prompts

**P2-Medium (generation and validation):**
- Add `<<widget>>` support (widget-tagged passages, prompt guidance)
- Add `<<capture>>` wrapping for links inside loops
- Extend state-read scanning to naked variables in prose
- Validate setter expressions and `<<if>>` conditions
- Add `<<include>>` passage type for shared content

**P3-Low (advanced features):**
- Typewriter (`<<type>>`) and timed (`<<timed>>`/`<<repeat>>`) narrative effects
- Input macros (`<<textbox>>`, `<<checkbox>>`) for player input passages
- Setting API integration for player-configurable options
- StoryInterface custom UI support
- PRNG seeding for deterministic playthroughs
- Achievement tracking via `memorize()`/`recall()`
- Passage tag awareness (mood tags, nobr, CSS theming)
- Template API (`?name`) support

The analysis also includes a key patterns reference covering variable conventions, link patterns, conditional text in prose, naked variable interpolation, widget definitions, and history-aware passages. This serves as a roadmap for implementing template-aware generation improvements in the harness.

## Current Strengths

- Git-friendly plain files.
- Local Ollama generation with delimited-output parsing and repair.
- Passage graph metadata and validation (including SugarCube container-macro nesting checks).
- Media-slot tracking.
- Inspiration corpus indexing through Ollama embeddings.
- A local FastAPI single-page UI.
- Headless playtester with branch coverage and issue detection.
- Snapshot deltas for efficient story state tracking.
- Curated HTML template collection (7 templates, CC-BY by manonamora).
- SugarCube 2 documentation bundled for offline reference.
- Structured analysis of SugarCube 2 capabilities and harness improvement roadmap.

## Current Limits

- The authoring workflow still needs a stronger review queue for proposed facts.
- Snapshot updates are intentionally simple and do not yet model characters entering or leaving scenes.
- Validation is useful, but not a full SugarCube parser. Missing: naked variable expression validation, setter expression validation, `<<if>>` condition validation, and deprecated macro detection.
- Generation prompts lack SugarCube-specific guidance (variable scoping, markup conventions, widget patterns).
- No `<<widget>>`, `<<include>>`, or `<<capture>>` support in the generation pipeline.
- Tweego and SugarCube are external dependencies.

See [plan.md](plan.md) for the original design, [future.md](future.md) for a suggested next-version path, and [docs/sugarcube2-analysis.md](docs/sugarcube2-analysis.md) for the full SugarCube 2 improvement roadmap.

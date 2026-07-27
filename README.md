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

## Current Strengths

- Git-friendly plain files.
- Local Ollama generation with delimited-output parsing and repair.
- Passage graph metadata and validation.
- Media-slot tracking.
- Inspiration corpus indexing through Ollama embeddings.
- A local FastAPI single-page UI.
- Headless playtester with branch coverage and issue detection.
- Snapshot deltas for efficient story state tracking.

## Current Limits

- The authoring workflow still needs a stronger review queue for proposed facts.
- Snapshot updates are intentionally simple and do not yet model characters entering or leaving scenes.
- Validation is useful, but not a full SugarCube parser.
- Tweego and SugarCube are external dependencies.

See [plan.md](plan.md) for the original design and [future.md](future.md) for a suggested next-version path.

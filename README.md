# SugarCube Agentic Story Harness

A local, single-user harness for co-authoring branching SugarCube stories with a human author and an Ollama model.

The harness owns the mechanical work: passage files, links, graph metadata, state variables, media slots, snapshots, validation, and Tweego compilation. The model is treated as a prose and beat generator, not a filesystem actor.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Ollama](https://ollama.com) running locally with at least one model pulled (e.g. `ollama pull llama3.2`)
- [Tweego](https://www.motoslave.net/tweego/) on your PATH (only needed for `compile`)

## Quick Start

```bash
# Clone and install dependencies
git clone https://github.com/hermes-servarr/sugarcube-story-harness-for-ollama.git
cd sugarcube-story-harness-for-ollama
uv sync

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

## Running Tests

```bash
uv run pytest
```

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

## Current Limits

- The authoring workflow still needs a stronger review queue for proposed facts.
- Snapshot updates are intentionally simple and do not yet model characters entering or leaving scenes.
- Validation is useful, but not a full SugarCube parser.
- Tweego and SugarCube are external dependencies.

See [plan.md](plan.md) for the original design and [future.md](future.md) for a suggested next-version path.

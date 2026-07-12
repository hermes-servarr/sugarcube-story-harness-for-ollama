# SugarCube Agentic Story Harness

A local, single-user harness for co-authoring branching SugarCube stories with a human author and an Ollama model.

The harness owns the mechanical work: passage files, links, graph metadata, state variables, media slots, snapshots, validation, and Tweego compilation. The model is treated as a prose and beat generator, not a filesystem actor.

## Quick Start

```bash
python3 -m harness.cli init my-story --title "My Story"
python3 -m harness.cli serve my-story
```

Then open `http://127.0.0.1:8765`.

Useful commands:

```bash
python3 -m harness.cli validate my-story
python3 -m harness.cli compile my-story
python3 -m harness.cli rag-reindex my-story
python3 -m harness.cli rag-status my-story
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

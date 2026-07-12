# Project Prompt: Agentic Harness for SugarCube Story Creation

## Goal
Build a local, single-user harness that lets a human and a local LLM (via Ollama) co-author a wide branching interactive fiction story, compiled to a playable SugarCube HTML game via Tweego. The harness owns all mechanical work — file structure, passage linking, state variables, media slots, continuity memory — so the model focuses only on prose, dialogue, and proposing new facts.

---

## Roles

**Human author** — switches freely between three modes per turn:
- *Director*: high-level prompts ("now they reach the city, three factions in tension")
- *Co-author*: approves/edits each beat the bot proposes before commit
- *Editor*: lets the bot draft a whole arc, revises after

**LLM agent (local, via Ollama)** — responsible for:
- Passage prose the player reads
- In-world dialogue and messages between characters
- Holding the overarching story in mind when proposing beats
- Proposing media slots as keyword tags — does not generate, fetch, or organize media
- Proposing new characters, locations, and lore inline — human approves at commit

**Harness** — owns everything mechanical:
- Creating passage files with stable IDs
- Wiring SugarCube links between passages
- Maintaining the passage graph, no orphans or dead links
- Managing SugarCube state variables (declare, track reads/writes across all paths)
- Recording media slot placeholders and embedding resolved paths at compile time
- Continuity memory via per-node snapshots
- Compiling via Tweego

---

## Story Shape
Wide branching graph. Cheap to spawn parallel branches or leave them divergent. Not a tree. There is one game state — branches are different routes through the same world, not parallel timelines. The player is always on one path; state accumulates along that path.

---

## Stack
- **Harness language**: Python
- **LLM**: Ollama (model configurable in `.harness/config.yaml`)
- **Compiler**: Tweego + SugarCube 2
- **UI**: local web app (Flask or FastAPI), single page, three panes
- **Storage**: plain-text files + JSON, git-friendly throughout

---

## File Layout

```
my-story/
├── story.json                    # graph, state vars, branch lineage, per-node snapshots
├── premise.md                    # human-written: premise, tone, themes
├── characters/
│   ├── _index.json
│   └── <id>.md                   # YAML frontmatter + prose sheet
├── lore/
│   ├── _index.json
│   ├── locations/<id>.md
│   └── factions/<id>.md
├── arcs/
│   ├── 01_<name>/
│   │   ├── _arc.md               # arc notes: themes, arc summary, open threads
│   │   └── NN_<slug>.tw          # one passage per file
│   └── 02_<name>/
├── media/
│   └── _slots.json               # slot tracking only; files live wherever the human wants
├── build/
│   └── story.html                # Tweego output — gitignored, treated as throwaway
└── .harness/
    ├── config.yaml               # ollama model, tweego path, options
    └── cache/
```

One passage per file. The directory tree (arc → passage) plus `story.json` plus per-arc `_arc.md` notes form the overarching navigable layer. Filesystem is the source of truth; the harness re-reads on startup rather than holding parallel state.

---

## Data Schemas

### `story.json`
Rewritten by the harness on every commit. Never hand-edited.

```json
{
  "version": 1,
  "start_passage": "01_arrival__01_train_station",
  "passages": {
    "<passage_id>": {
      "file": "arcs/01_arrival/01_train_station.tw",
      "arc": "01_arrival",
      "parents": [],
      "children": [],
      "state_writes": ["$met_alice"],
      "state_reads": [],
      "media_slots": ["slot_a8f3"],
      "location": "ravenhold/train_station",
      "summary": "Player arrives in Ravenhold and sees Alice across the platform.",
      "snapshot": {
        "characters_present": [
          {
            "id": "alice",
            "status": "alive, wary",
            "knows": ["player arrived from the north", "compact is watching"],
            "relationship_to_player": "cautious ally"
          }
        ],
        "characters_offscreen": [
          {"id": "kael", "last_known": "left for the records hall"}
        ],
        "world_state": ["rain since morning", "curfew in effect"],
        "open_threads": ["who sent the letter", "alice's debt to the compact"]
      }
    }
  },
  "state_variables": {
    "$met_alice": {"type": "bool", "default": false, "declared_in": "<passage_id>"}
  },
  "branches": {
    "main":        {"head": "<passage_id>"},
    "alice_route": {"head": "<passage_id>", "diverges_at": "<passage_id>"},
    "skip_town":   {"head": "<passage_id>", "diverges_at": "<passage_id>"}
  }
}
```

### Character and lore files
YAML frontmatter + markdown prose. Structured enough to parse, readable enough to inject directly into model context.

```markdown
---
id: alice
tags: [protagonist, ravenhold_native]
first_seen: 01_arrival__01_train_station
---
# Alice Marwen
Twenty-eight, archivist at the Compact's records hall. Sharp, guarded...
```

### Passage file format
Standard Tweego twee notation with a harness-managed metadata comment block. The harness writes these; the model proposes prose and choices only.

```
:: <passage_id> [arc-tag]
<!-- harness:meta
characters: [alice]
location: ravenhold/train_station
-->

The train hisses to a stop. Rain hammers the platform roof...

<<set $met_alice to true>>

[[Approach her|01_arrival__02_first_meeting]]
[[Walk past|01_arrival__02_skip_town]]

<!-- media:slot_a8f3 -->
```

### `media/_slots.json`
The bot tags where media should appear and describes it with keywords. The human resolves slots by providing a file path. The harness embeds the resolved path at compile time.

```json
{
  "slot_a8f3": {
    "passage": "<passage_id>",
    "keywords": ["rainy train platform at dusk", "neon reflections on wet stone", "lone figure with umbrella"],
    "type": "image",
    "status": "pending",
    "resolved_path": null
  }
}
```

The harness does not impose a folder layout for media, does not move or rename files, and does not assume any directory exists. It only validates that `resolved_path` exists at compile time and embeds it. Media file structure is entirely the human's responsibility.

---

## Continuity: Snapshots

Each passage has one snapshot representing the author's intent for what is true when the player arrives at that passage. Snapshot derivation happens **once at commit time**.

**On commit, the harness derives the new node's snapshot from:**
1. Parent's snapshot (inherited as base)
2. Plus approved `new_facts` from this turn
3. Updated by the model's snapshot delta output (status changes, thread open/close, world state delta)

The snapshot is authorial intent, not a simulation of every possible path. It answers: *given a player who reached this passage, what should the author assume is true?*

**Per-node snapshot fields — keep all entries terse, one line per fact:**
- `characters_present` — who is in this scene, their current status, what they know, relationship to player
- `characters_offscreen` — relevant characters not in scene, last known status/location
- `world_state` — active environmental or political facts that affect the scene
- `open_threads` — unresolved story questions the player or characters are aware of

Cap snapshot fields to reasonable limits (e.g. 10 open threads max). Push closed or stale threads into `_arc.md` notes rather than carrying them forward indefinitely.

**Context assembled per turn:**
1. **Always-in**: `premise.md`, current `_arc.md`, tone notes
2. **Current snapshot**: from parent node, compact
3. **Retrieved entities**: full character/lore sheets for entities named in snapshot or human's prompt
4. **Parent passage**: full prose of immediate parent

---

## Model Proposes, Human Approves

The model may propose new characters, locations, and lore inline in its output. On commit, the human sees a review queue:

- "New character: Warden Kael — proposed sheet attached. Accept / Edit / Reject"
- Accepted facts are written to `characters/` or `lore/` and added to `_index.json`
- Rejected facts are dropped; the harness flags any passage prose that depended on them for human review

---

## Ollama Prompt Template

The model outputs **plain delimited text**, not JSON. Local models are unreliable at producing valid nested JSON; delimited sections are easy to produce and easy to parse. The harness splits on section headers, validates presence of required sections (`PROSE`, `CHOICES`, `SUMMARY`), and defaults missing optional sections to empty. Garbled sections are surfaced for human correction before commit rather than blocking.

```
SYSTEM:
You are co-authoring interactive fiction with a human.
The harness handles all file structure, passage linking, and state management.
Focus on prose, character voice, and story. You may propose new characters,
locations, or lore — they will be reviewed by the human before commit.
Use the exact section headers below. Do not add commentary outside the sections.

[PREMISE]
{premise.md}

[CURRENT ARC]
{_arc.md}

[CURRENT SNAPSHOT]
Characters present: {snapshot.characters_present}
Characters offscreen: {snapshot.characters_offscreen}
World state: {snapshot.world_state}
Open threads: {snapshot.open_threads}

[ENTITIES IN CONTEXT]
{full sheets for characters/lore referenced in snapshot or prompt}

[PARENT PASSAGE]
{prose of immediate parent passage}

[HUMAN DIRECTION]
{this turn's prompt}

[MODE]
{director | co-author | editor}

[TASK]
Write the next passage using exactly these section headers:

PROSE:
{the passage text the player reads}

CHOICES:
- {choice text shown to player} | {hint: where this leads}
- {choice text shown to player} | {hint: where this leads}

STATE:
$variable_name = value
(omit section if no state changes)

MEDIA:
{type}: {keyword, keyword, keyword}
(omit section if no media)

NEW_CHARACTERS:
{id} | {one paragraph prose sheet}
(omit section if none)

NEW_LORE:
{category}/{id} | {one paragraph prose sheet}
(omit section if none)

THREADS_OPEN:
{one thread per line}
(write "(none)" if no new threads)

THREADS_CLOSE:
{one thread per line}
(write "(none)" if no threads close)

WORLD_STATE_ADD:
{one fact per line}
(omit section if nothing changes)

WORLD_STATE_REMOVE:
{one fact per line}
(omit section if nothing changes)

SUMMARY:
{one sentence describing what happens in this passage}
```

The harness parses each section, creates the passage file, wires links, updates `story.json`, derives the new snapshot, and queues new facts for human approval. The model never touches the filesystem.

---

## Validation

Runs continuously in the UI and blocks compile on errors. Warnings are surfaced but do not block.

**Errors (block compile):**
- Broken links — target passage does not exist in `story.json`
- Orphan passages — no parents and not the start passage
- Undeclared state variables — a passage reads `$var` and there exists at least one path through the graph that reaches it without a prior setter, and `$var` has no declared default
- SugarCube macro pairing — `<<if>>`/`<</if>>`, `<<for>>`/`<</for>>`, etc.
- Manifest drift — every `.tw` in `arcs/` must be in `story.json` and vice versa
- Unresolved media path — `resolved_path` is set but file does not exist at compile time

**Warnings (surface in UI, do not block):**
- Pending media slots — `status: pending` at compile time
- Snapshot bloat — any snapshot field exceeding defined caps

---

## Web UI (v1)

Single local page served by the Python process. Three panes:

- **Left**: graph view (Cytoscape.js or D3) — nodes are passages, edges are links, color-coded by arc and branch; click a node to focus it
- **Center**: focused passage — prose, choices, state reads/writes, snapshot summary, media slots with resolve button, edit button
- **Right**: chat pane with the bot, mode toggle (director / co-author / editor), commit button, pending-facts approval queue
- **Top bar**: live validation warnings, compile button, current branch indicator

---

## Output

Tweego compiles all `.tw` files to a single `build/story.html`. That file is the playable game and is gitignored — it is a build artifact. The source (one passage per file) is the canonical form. A model navigating the project later reads the source tree and `story.json`, not the compiled output.

---

## Out of Scope for v1
- Multi-user collaboration
- Image generation or media generation of any kind (define the resolver interface in `_slots.json`, do not implement)
- Sidecar manifest for compiled HTML
- Player-facing analytics or telemetry

---

## Implementation Order
1. Project init — file layout, `premise.md` template, `story.json` schema, Tweego compile pipeline
2. Passage CRUD — create, read, update; link wiring; manifest sync
3. Validation — all error and warning checks; pre-compile gate
4. Ollama integration — context assembly, prompt construction, delimited text parsing, missing-section recovery
5. Snapshot derivation — commit-time snapshot delta application
6. Pending-facts approval queue — review UI, write to character/lore files on accept
7. Media slot management — record pending slots, resolve path, embed at compile
8. Web UI — graph view, passage pane, chat pane, validation bar

---

## Implementation Notes

- **Passage ID scheme**: use `arc__NN_slug` (double underscore) rather than `arc/slug` — slashes in passage names can trip Tweego and some SugarCube tooling. Test before committing to a scheme.
- **Ollama output parsing**: split model output on capitalised section headers (`PROSE:`, `CHOICES:`, etc.). Required sections are `PROSE`, `CHOICES`, `SUMMARY`; all others are optional and default to empty if absent. Log the raw output whenever a required section is missing and surface it in the UI for human correction. Do not retry automatically — garbage output is better reviewed by the human than silently retried.
- **Ollama model choice**: prefer a recent instruct model (Llama 3.x, Qwen 2.5, Mistral Instruct). The delimited text format is robust enough that strict JSON adherence is not required.
- **Snapshot bloat**: enforce caps at commit time (suggested: 10 open threads, 20 world state entries). Summarise and archive excess into `_arc.md`.
- **Branch model**: branches are named navigation labels only — a name, a head passage ID, and optionally a `diverges_at` passage ID. There is one game state; branches are different routes through it, not parallel timelines. The harness stores branch metadata in `story.json` and the active working node in `.harness/session.json`. A branch is created when the human first writes a passage on an unwritten choice exit and names the new route. Switching branches is done by clicking a node in the graph or using the branch dropdown.
- **State variable validation**: a read of `$var` is an error if there exists any path through the passage graph that reaches the reader without a prior setter, and `$var` has no declared default. Fix by adding a default to the variable declaration or by ensuring all entry paths set the variable.
- **Media**: the human owns all media files, folder structure, and naming. The harness only stores and validates `resolved_path`. No media is moved, copied, or renamed by the harness.
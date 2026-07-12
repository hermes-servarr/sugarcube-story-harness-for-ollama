# Five Big Improvements

Reviewed the harness (Python harness, FastAPI server in `harness/server/app.py`, Ollama generation, Tweego compile). Architecture is solid. Below are the five highest-impact improvements, ranked.

## 1. Snapshot continuity is mostly inert — core value prop broken

[snapshot.py:13](harness/snapshot.py#L13) `derive_snapshot` only merges threads + world_state, and dumps *new* characters into `characters_offscreen`. It **never moves characters in/out of scene or updates their status/knows**. So `characters_present` only ever changes if hand-edited.

The harness sells itself as "continuity clerk" (README, future.md). Right now who's-in-the-scene never evolves across passages. The model emits nothing for this — the parser ([parsers.py:28](harness/parsers.py#L28)) has no `CHARACTERS_PRESENT`/`CHARACTERS_EXIT`/`CHARACTER_STATUS` sections.

**Fix:** add those delta sections to prompt + parser + `derive_snapshot`. Listed in future.md v0.2. Biggest gap.

## 2. story.json not crash-safe, not rebuildable

[project.py:21](harness/project.py#L21) `_jdump` does a direct `write_text`. story.json is the single source of truth for the whole graph. A crash or concurrent write mid-dump = corrupted graph, no recovery. Manifest drift is only *reported* ([validation.py:84](harness/validation.py#L84)), never *repaired*.

**Fix:** atomic write (temp file + `os.replace`). Add a `rebuild` command that reconstructs story.json from the `.tw` files on disk. future.md v0.2.

## 3. State-var validation is exponential on wide graphs

[validation.py:217](harness/validation.py#L217) `_path_always_sets` does a full DFS from start per `(passage, var)` pair, no memoization. The project's whole point is "wide branching graph". This blows up: O(paths) × vars × readers. Will hang on large stories.

**Fix:** memoize on `(node, var)`, or do a single reverse pass computing must-set sets. The same DFS is recomputed thousands of times now.

## 4. Model-output audit is volatile

[ollama_client.py:23](harness/ollama_client.py#L23) keeps only a 50-entry **in-memory** ring buffer. Gone on restart. Local models emit garbage often (the whole repair pipeline exists for it) — no durable record to debug or recover a lost good generation.

**Fix:** persist raw outputs to `.harness/cache/generations/` beside commits. future.md v0.2.

## 5. Macro/link validation is naive regex

[validation.py:155](harness/validation.py#L155) `check_macro_pairing` just counts `<<if` opens vs `<</if>>` closes. It miscounts on: `<<if>>` inside strings, nesting-depth errors (2 open + 2 close but wrong order passes), `<<elseif>>`, inline `<<= >>`. A false pass = broken SugarCube compile slips through. No real Twee parser.

**Fix:** small tokenizing pass tracking a macro stack (depth + order), not bare counts. future.md v0.5.

---

Priority: **#1 (snapshot deltas)** is highest-leverage but touches prompts + parser + snapshot + models. **#2 atomic write** is a small, safe quick win.

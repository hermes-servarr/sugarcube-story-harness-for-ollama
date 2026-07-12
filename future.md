# Better Future Version

This project is already pointed in a good direction: local-first, file-native, and model-constrained. The better version should make the harness feel less like a prompt box and more like an editor that understands interactive fiction structure.

## Version 0.2: Trustworthy Core

- Add tests for parsing, passage creation, link validation, state validation, and media-slot embedding.
- Make `story.json` rebuildable from disk so manifest drift can be repaired, not only reported.
- Add a migration command for damaged graphs, especially duplicate file ownership and old `UNRESOLVED_` links.
- Store raw model outputs beside commits in `.harness/cache/generations/` for audit and recovery.
- Expand snapshot deltas with explicit `CHARACTERS_PRESENT`, `CHARACTERS_EXIT`, and `CHARACTER_STATUS` sections.

## Version 0.3: Authoring Ergonomics

- Replace commit-after-generation with a draft queue: generate, edit, validate preview, then commit.
- Show unresolved exits as first-class graph stubs that can be written later.
- Add a passage diff view before commit.
- Add “continue from this choice” buttons directly on each unresolved choice.
- Add branch labels and branch history in the UI, not only graph metadata.

## Version 0.4: Story Intelligence

- Add continuity checks: character location conflicts, repeated reveals, unresolved thread age, and forgotten state variables.
- Make RAG retrieval source-aware: premise, character sheet, lore, inspiration, and prior passage should have separate budgets.
- Add a “director pass” that proposes missing routes, pacing issues, and dead-end opportunities without writing prose.
- Add story bible summaries per arc that are updated through explicit human approval.

## Version 0.5: SugarCube-Grade Safety

- Replace regex-only macro checks with a small Twee/SugarCube navigation parser.
- Validate choice visibility and state writes as path conditions rather than plain graph edges.
- Generate a report of reachable endings, dead ends, state gates, and possible loops.
- Add compile-time asset rewriting so resolved media can be copied into build output when the author wants a portable HTML bundle.

## North Star

The ideal harness should let the author think in story moves:

- “Fork this unresolved choice into a stealth route.”
- “Show me what this character knows on every path.”
- “Find branches where the player can learn the betrayal before the reveal.”
- “Draft three exits from this hub, but keep the cathedral thread alive.”

The model should stay inside bounded creative tasks. The harness should be the memory, graph mechanic, continuity clerk, and SugarCube safety rail.

# Test Stories

Comprehensive test stories for the Sugarcube Story Harness, used to validate the full pipeline: generation, compilation, browser playtest, and end-to-end player flow.

## rpg-sandbox: Shadows of Thornwood

A dark fantasy RPG sandbox built with SugarCube 2, compiled to a standalone 532KB HTML file. Tests the following harness capabilities:

- Playable story and quest system (3 quests with start/progress/complete states)
- Character creation (3 classes + Quick Start) with attributes, stats, inventory, progression
- Multiple named locations with hub-based navigation and revisit support
- Persistent world state (30+ state variables) and character state across passages
- Branching choices and consequences with 3 endings
- NPCs with dynamic dialogue based on trust, quest progress, and prior decisions
- Images integrated via media slots (5 placeholder test images)
- Save/load/resume via SugarCube built-in system
- 39 Twee passage files across 4 arcs

### Test Results

60 tests run, 58 passed, 2 failed (navigation link text variations, not game defects).

5 defects found, all fixed:
1. Media slot regex rejected named slot IDs (fixed in compile.py)
2. Forest path/lantern circular dependency
3. NPC return link inconsistency
4. Elara NPC accessibility gating
5. SugarCube Save.autoSave() with file:// protocol

### Contents

| Path | Description |
|---|---|
| `arcs/` | 39 Twee passage files across 4 arcs (main, town, forest, castle) |
| `build/story.html` | Compiled 532KB standalone HTML game |
| `media/` | Placeholder test images |
| `test_player_flow.py` | Full E2E player flow test (35KB, 60 test cases) |
| `test_endings.py` | All three endings test |
| `e2e_player_report.json` | Machine-readable test results |
| `test_screenshots/` | 18 browser screenshots from playtest |
| `ISSUE_LOG.md` | Detailed defect log with repro steps |
| `story.json` | Story metadata |
| `premise.md` | Story premise |
| `.harness/config.yaml` | Harness project config |

### Running the Tests

```bash
# Compile the story
cd test_stories/rpg-sandbox
tweego -o build/story.html arcs/

# Run the E2E player flow test
python test_player_flow.py

# Run the endings test
python test_endings.py
```

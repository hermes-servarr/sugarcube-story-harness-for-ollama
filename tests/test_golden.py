"""Golden regression tests covering prompts, parsers, and RAG metadata.

These exercise pure-Python paths that don't require a running Ollama instance.
For end-to-end model behaviour, see manual smoke tests via the /api/ollama
endpoints in the UI.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.models import (
    CharacterDelta,
    CharacterOffscreen,
    CharacterPresent,
    ExtractedEntities,
    ModelOutput,
    ParsedChoice,
    Snapshot,
)
from harness.snapshot import derive_snapshot
from harness.parsers import (
    parse_entities_json,
    parse_json_object,
    parse_keywords_json,
    parse_model_output,
    parse_model_output_json,
)
from harness.generators import _normalise_sketch_list
from harness.passage import create_passage
from harness.project import init_project
from harness.prompts import (
    PROMPT_VERSION,
    build_characters_sketch_prompt,
    build_compact_passage_prompt,
    build_entity_extraction_prompt,
    build_full_passage_prompt,
    build_json_passage_prompt,
    build_keyword_extraction_prompt,
    build_locations_sketch_prompt,
    build_opening_prompt,
    build_premise_prompt,
    build_repair_prompt,
    build_story_points_prompt,
    build_suggest_names_prompt,
    build_tone_themes_prompt,
    build_world_prompt,
)
from harness.project import (
    list_characters,
    list_lore,
    set_character_keywords,
    set_lore_keywords,
    write_character,
    write_lore_entity,
)
from harness.rag import _extract_text_metadata
from harness.validation import run_validation


# ── Prompt builders ───────────────────────────────────────────────────────────

class PromptBuilderTests(unittest.TestCase):
    def test_prompt_version_is_pinned(self):
        self.assertIsInstance(PROMPT_VERSION, int)
        self.assertGreaterEqual(PROMPT_VERSION, 1)

    def test_compact_includes_required_sections(self):
        out = build_compact_passage_prompt(
            premise="A premise.",
            story_points="Beats.",
            arc_notes="Arc.",
            entities_text="cast",
            parent_prose="Prev scene.",
            snapshot_text="situation",
            human_prompt="continue",
        )
        for header in ("PROSE:", "CHOICES:", "SUMMARY:", "BEATS:"):
            self.assertIn(header, out)

    def test_full_includes_all_section_headers(self):
        out = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a",
            snapshot_text="s", entities_text="e", inspiration="",
            parent_prose="pp", human_prompt="hp", mode="co-author",
        )
        for header in (
            "PROSE:", "CHOICES:", "STATE:", "MEDIA:",
            "NEW_CHARACTERS:", "NEW_LORE:",
            "THREADS_OPEN:", "THREADS_CLOSE:",
            "WORLD_STATE_ADD:", "WORLD_STATE_REMOVE:",
            "CHARACTERS_PRESENT:", "CHARACTER_STATUS:", "CHARACTERS_EXIT:",
            "SUMMARY:", "BEATS:",
        ):
            self.assertIn(header, out)

    def test_json_prompt_lists_required_keys(self):
        out = build_json_passage_prompt(
            premise="p", story_points="sp", arc_md="a",
            snapshot_text="s", entities_text="e", inspiration="",
            parent_prose="pp", human_prompt="hp", mode="co-author",
        )
        self.assertIn("JSON", out.upper())
        for key in ("prose", "choices", "summary", "beats"):
            self.assertIn(key, out)

    def test_story_points_acts_count(self):
        out = build_story_points_prompt(
            premise="x", tone="y", themes="z", world_overview="w", num_acts=3,
        )
        self.assertEqual(out.count("ACT 1:"), 1)
        self.assertEqual(out.count("ACT 2:"), 1)
        self.assertEqual(out.count("ACT 3:"), 1)
        self.assertIn("OPEN QUESTIONS", out)

    def test_suggest_names_includes_arc_when_requested(self):
        with_arc = build_suggest_names_prompt("a dark alley", suggest_arc=True)
        without_arc = build_suggest_names_prompt("a dark alley", suggest_arc=False)
        self.assertIn("ARC", with_arc)
        self.assertNotIn("ARC:", without_arc)

    def test_repair_includes_three_section_template(self):
        out = build_repair_prompt("draft text")
        for header in ("PROSE:", "CHOICES:", "SUMMARY:"):
            self.assertIn(header, out)

    def test_entity_prompt_lists_required_keys(self):
        out = build_entity_extraction_prompt("Scene prose.")
        for key in ("characters", "locations", "items", "themes"):
            self.assertIn(key, out)

    def test_keyword_prompt_specifies_kind(self):
        for kind in ("character", "lore", "location", "item", "faction"):
            out = build_keyword_extraction_prompt("Some sheet content.", kind=kind)
            self.assertIn(kind, out)
            self.assertIn("keywords", out)


# ── Keyword JSON parser ───────────────────────────────────────────────────────

class KeywordParserTests(unittest.TestCase):
    def test_parses_basic_keywords_array(self):
        raw = '{"keywords": ["brave", "scarred", "knight"]}'
        kws = parse_keywords_json(raw)
        self.assertEqual(kws, ["brave", "scarred", "knight"])

    def test_lowercases_and_dedupes(self):
        raw = '{"keywords": ["Brave", "brave", "  Knight  ", "knight"]}'
        kws = parse_keywords_json(raw)
        self.assertEqual(kws, ["brave", "knight"])

    def test_caps_max_keywords(self):
        many = [f"kw{i}" for i in range(30)]
        raw = '{"keywords": ' + str(many).replace("'", '"') + '}'
        kws = parse_keywords_json(raw, max_keywords=5)
        self.assertEqual(len(kws), 5)

    def test_strips_fence_and_preamble(self):
        raw = 'Here: ```json\n{"keywords": ["alpha"]}\n```'
        kws = parse_keywords_json(raw)
        self.assertEqual(kws, ["alpha"])

    def test_garbage_returns_empty(self):
        self.assertEqual(parse_keywords_json("not json"), [])
        self.assertEqual(parse_keywords_json(""), [])

    def test_wrong_shape_returns_empty(self):
        self.assertEqual(parse_keywords_json('{"keywords": "not a list"}'), [])
        self.assertEqual(parse_keywords_json('{"other": ["a"]}'), [])


# ── Delimited parser: BEATS + existing fields ─────────────────────────────────

class DelimitedParserTests(unittest.TestCase):
    def test_beats_section_parses(self):
        parsed = parse_model_output(
            """PROSE:
The door slams shut.

CHOICES:
- Run | flee the corridor
- Hide | tuck behind crates

SUMMARY:
A trap closes.

BEATS:
- Door slams.
- Footsteps approach.
- Lights flicker.
"""
        )
        self.assertEqual(len(parsed.beats), 3)
        self.assertEqual(parsed.beats[0], "Door slams.")
        self.assertEqual(parsed.beats[2], "Lights flicker.")
        self.assertEqual(len(parsed.choices), 2)

    def test_beats_omitted_yields_empty_list(self):
        parsed = parse_model_output(
            """PROSE:
A quiet moment.

CHOICES:
- Wait | listen
- Leave | go outside

SUMMARY:
A pause.
"""
        )
        self.assertEqual(parsed.beats, [])


# ── Character snapshot deltas ─────────────────────────────────────────────────

class CharacterDeltaParseTests(unittest.TestCase):
    def test_present_exit_status_sections_parse(self):
        parsed = parse_model_output(
            """PROSE:
Alice steps onto the platform. Kael is gone.

CHOICES:
- Approach | meet her
- Wait | hold back

SUMMARY:
Alice arrives.

CHARACTERS_PRESENT:
- alice | wary, soaked | player came from the north; compact is watching | cautious ally

CHARACTER_STATUS:
- alice | angry now | she saw the letter

CHARACTERS_EXIT:
- kael | left for the records hall
"""
        )
        self.assertEqual(len(parsed.characters_present), 1)
        a = parsed.characters_present[0]
        self.assertEqual(a.id, "alice")
        self.assertEqual(a.status, "wary, soaked")
        self.assertIn("compact is watching", a.knows)
        self.assertEqual(a.relationship_to_player, "cautious ally")

        self.assertEqual(len(parsed.character_status), 1)
        self.assertEqual(parsed.character_status[0].status, "angry now")

        self.assertEqual(len(parsed.characters_exit), 1)
        self.assertEqual(parsed.characters_exit[0].id, "kael")
        self.assertEqual(parsed.characters_exit[0].last_known, "left for the records hall")

    def test_id_only_present_line(self):
        parsed = parse_model_output(
            """PROSE:
x

CHOICES:
- a | b
- c | d

SUMMARY:
s

CHARACTERS_PRESENT:
- bram
"""
        )
        self.assertEqual(len(parsed.characters_present), 1)
        self.assertEqual(parsed.characters_present[0].id, "bram")

    def test_json_mode_parses_character_deltas(self):
        raw = """{
            "prose": "Scene.",
            "choices": [{"text": "Go", "hint": "on"}],
            "summary": "A scene.",
            "characters_present": [
                {"id": "alice", "status": "calm", "knows": ["the code"], "relationship_to_player": "ally"}
            ],
            "characters_exit": [{"id": "kael", "last_known": "the docks"}]
        }"""
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.characters_present[0].id, "alice")
        self.assertEqual(parsed.characters_present[0].knows, ["the code"])
        self.assertEqual(parsed.characters_exit[0].last_known, "the docks")


class DeriveSnapshotTests(unittest.TestCase):
    def test_enter_adds_present_and_clears_offscreen(self):
        parent = Snapshot(
            characters_offscreen=[CharacterOffscreen(id="alice", last_known="the north")]
        )
        out = ModelOutput(
            characters_present=[CharacterDelta(
                id="alice", status="present, wary",
                knows=["compact watches"], relationship_to_player="ally",
            )]
        )
        snap = derive_snapshot(parent, out)
        self.assertEqual([c.id for c in snap.characters_present], ["alice"])
        self.assertEqual(snap.characters_offscreen, [])
        self.assertEqual(snap.characters_present[0].status, "present, wary")
        self.assertEqual(snap.characters_present[0].knows, ["compact watches"])

    def test_status_merges_knows_without_duplicates(self):
        parent = Snapshot(characters_present=[CharacterPresent(
            id="alice", status="calm", knows=["a"], relationship_to_player="ally",
        )])
        out = ModelOutput(character_status=[CharacterDelta(
            id="alice", status="afraid", knows=["a", "b"],
        )])
        snap = derive_snapshot(parent, out)
        c = snap.characters_present[0]
        self.assertEqual(c.status, "afraid")
        self.assertEqual(c.knows, ["a", "b"])
        self.assertEqual(c.relationship_to_player, "ally")  # untouched

    def test_exit_moves_present_to_offscreen(self):
        parent = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
            CharacterPresent(id="kael", status="here"),
        ])
        out = ModelOutput(characters_exit=[CharacterDelta(id="kael", last_known="records hall")])
        snap = derive_snapshot(parent, out)
        self.assertEqual([c.id for c in snap.characters_present], ["alice"])
        self.assertEqual(snap.characters_offscreen[0].id, "kael")
        self.assertEqual(snap.characters_offscreen[0].last_known, "records hall")

    def test_enter_then_exit_same_turn_lands_offscreen(self):
        out = ModelOutput(
            characters_present=[CharacterDelta(id="ghost", status="flickering")],
            characters_exit=[CharacterDelta(id="ghost", last_known="vanished")],
        )
        snap = derive_snapshot(None, out)
        self.assertEqual(snap.characters_present, [])
        self.assertEqual(snap.characters_offscreen[0].id, "ghost")
        self.assertEqual(snap.characters_offscreen[0].last_known, "vanished")

    def test_deltas_persist_through_commit(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Alice waits.",
                choices=[ParsedChoice(text="Greet", hint="hello")],
                summary="Meeting.",
                characters_present=[CharacterDelta(id="alice", status="wary")],
            )
            pid, graph = create_passage(p, "intro", "01_meet", out, None)
            present = graph.passages[pid].snapshot.characters_present
            self.assertEqual([c.id for c in present], ["alice"])
            self.assertEqual(present[0].status, "wary")


# ── JSON parser ───────────────────────────────────────────────────────────────

class JsonParserTests(unittest.TestCase):
    def test_strict_json_parses(self):
        raw = """{
            "prose": "A scene.",
            "choices": [
                {"text": "Go", "hint": "next"},
                {"text": "Stay", "hint": "wait"}
            ],
            "summary": "A short scene.",
            "beats": ["Lit a torch.", "Heard voices."]
        }"""
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.prose, "A scene.")
        self.assertEqual(len(parsed.choices), 2)
        self.assertEqual(parsed.beats, ["Lit a torch.", "Heard voices."])
        self.assertEqual(parsed.parse_warnings, [])

    def test_json_with_code_fence(self):
        raw = '```json\n{"prose": "P", "choices": [{"text":"x","hint":"y"}], "summary": "S"}\n```'
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.prose, "P")
        self.assertEqual(parsed.summary, "S")

    def test_json_with_prose_preamble(self):
        raw = 'Here is the result:\n{"prose": "P", "choices": [{"text":"x","hint":"y"}], "summary": "S"}'
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.prose, "P")

    def test_json_summary_fallback_from_prose(self):
        raw = '{"prose": "First. Second.", "choices": [{"text":"x","hint":"y"}]}'
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.summary, "First.")
        self.assertTrue(any("missing summary" in w for w in parsed.parse_warnings))

    def test_invalid_json_falls_back_to_delimited(self):
        raw = """PROSE:
fallback prose

CHOICES:
- Yes | go
- No | stop

SUMMARY:
A line.
"""
        parsed = parse_model_output_json(raw)
        self.assertEqual(parsed.prose, "fallback prose")
        self.assertEqual(len(parsed.choices), 2)
        self.assertTrue(any("fallback" in w.lower() for w in parsed.parse_warnings))

    def test_empty_json_response_falls_back(self):
        parsed = parse_model_output_json("")
        self.assertTrue(any("Empty" in w or "fallback" in w.lower() for w in parsed.parse_warnings))


# ── Entity JSON parser ────────────────────────────────────────────────────────

class EntityParserTests(unittest.TestCase):
    def test_extracts_full_entity_struct(self):
        raw = '{"characters": ["Ada"], "locations": ["Tower"], "items": ["Key"], "themes": ["loss"]}'
        ents = parse_entities_json(raw)
        self.assertEqual(ents.characters, ["Ada"])
        self.assertEqual(ents.locations, ["Tower"])
        self.assertEqual(ents.items, ["Key"])
        self.assertEqual(ents.themes, ["loss"])

    def test_returns_empty_struct_on_garbage(self):
        ents = parse_entities_json("not json at all")
        self.assertEqual(ents, ExtractedEntities())

    def test_salvages_unknown_keys(self):
        raw = '{"characters": ["Ada"], "garbage": 42, "themes": ["fate"]}'
        ents = parse_entities_json(raw)
        self.assertEqual(ents.characters, ["Ada"])
        self.assertEqual(ents.themes, ["fate"])


# ── RAG metadata extractor ────────────────────────────────────────────────────

class RagMetadataTests(unittest.TestCase):
    def test_frontmatter_and_heading_extracted(self):
        raw = """---
title: The Vault
tags: [heist, vault]
arc: 03_vault
---
# The Vault

The doors are sealed.
"""
        body, meta, header = _extract_text_metadata(raw, "inspiration/03_vault/scene.md")
        self.assertEqual(meta["title"], "The Vault")
        self.assertEqual(meta["tags"], ["heist", "vault"])
        self.assertEqual(meta["arc"], "03_vault")
        self.assertIn("[The Vault]", header)
        self.assertIn("arc:03_vault", header)
        self.assertIn("tags:heist,vault", header)
        self.assertNotIn("---", body)

    def test_arc_inferred_from_path_when_absent(self):
        raw = "# Scene\n\nProse here.\n"
        _, meta, header = _extract_text_metadata(raw, "inspiration/02_woods/intro.md")
        self.assertEqual(meta["arc"], "02_woods")
        self.assertIn("[Scene]", header)

    def test_twee_passages_collected(self):
        raw = """:: Start [intro]
Welcome.

:: Second [intro]
Onward.
"""
        _, meta, _ = _extract_text_metadata(raw, "arcs/intro/start.tw")
        self.assertEqual(meta.get("passages"), ["Start", "Second"])
        self.assertEqual(meta["arc"], "intro")

    def test_frontmatter_without_trailing_newline(self):
        # File ends right after closing `---` with no final newline.
        raw = "---\ntitle: Edge\ntags: [a, b]\n---"
        body, meta, header = _extract_text_metadata(raw, "inspiration/foo.md")
        self.assertEqual(meta.get("title"), "Edge")
        self.assertEqual(meta.get("tags"), ["a", "b"])
        # Body should be empty after frontmatter strip.
        self.assertEqual(body, "")

    def test_bracketed_non_list_field_stays_string(self):
        # `arc: [single]` must remain a string, not a single-element list.
        raw = "---\ntitle: T\narc: [vault]\n---\n\nbody"
        _, meta, _ = _extract_text_metadata(raw, "inspiration/x.md")
        self.assertEqual(meta.get("arc"), "[vault]")

    def test_bracketed_known_list_field_parses_as_list(self):
        raw = "---\ntitle: T\nkeywords: [alpha, beta]\n---\n\nbody"
        _, meta, _ = _extract_text_metadata(raw, "inspiration/x.md")
        self.assertEqual(meta.get("keywords"), ["alpha", "beta"])


# ── Commit-time invariants ────────────────────────────────────────────────────

class CommitInvariantsTests(unittest.TestCase):
    def test_beats_persist_through_commit(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            output = ModelOutput(
                prose="Once upon a time.",
                choices=[ParsedChoice(text="Go", hint="next")],
                summary="An opening.",
                beats=["Hero stirs.", "Storm arrives."],
            )
            pid, graph = create_passage(p, "intro", "01_start", output, None)
            self.assertEqual(graph.passages[pid].beats, ["Hero stirs.", "Storm arrives."])

    def test_missing_summary_filled_from_prose(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            output = ModelOutput(
                prose="The hero strikes. The room shudders.",
                choices=[ParsedChoice(text="Press on", hint="advance")],
                summary="",
            )
            pid, graph = create_passage(p, "intro", "01_start", output, None)
            self.assertTrue(graph.passages[pid].summary.startswith("The hero strikes"))

    def test_baseline_validation_clean_after_two_chained_commits(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out1 = ModelOutput(
                prose="Scene one.",
                choices=[ParsedChoice(text="Onward", hint="continue")],
                summary="Open.",
            )
            pid1, _ = create_passage(p, "intro", "01_a", out1, None)
            out2 = ModelOutput(
                prose="Scene two.",
                choices=[],
                summary="Close.",
            )
            create_passage(
                p, "intro", "02_b", out2, pid1,
                choice_index=0, passage_type="ending",
            )
            result = run_validation(p)
            self.assertEqual(result.errors, [])


# ── Character / lore keyword persistence ──────────────────────────────────────

class KeywordPersistenceTests(unittest.TestCase):
    def test_character_keywords_roundtrip(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            sheet = "---\nid: ada\nname: Ada\ntags: [protagonist]\n---\n# Ada\n\nA wandering scribe.\n"
            write_character(p, "ada", sheet)

            ok = set_character_keywords(p, "ada", ["scribe", "wandering", "literate"])
            self.assertTrue(ok)

            chars = list_characters(p)
            ada = next(c for c in chars if c["id"] == "ada")
            self.assertEqual(ada["keywords"], ["scribe", "wandering", "literate"])
            # tags preserved
            self.assertEqual(ada["tags"], ["protagonist"])

    def test_character_keywords_missing_id_returns_false(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            self.assertFalse(set_character_keywords(p, "ghost", ["a", "b"]))

    def test_lore_keywords_roundtrip(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            sheet = "---\nid: tower\ntitle: The Tower\ncategory: locations\n---\n# The Tower\n\nA spiral of stone.\n"
            write_lore_entity(p, "locations", "tower", sheet)

            ok = set_lore_keywords(p, "locations", "tower", ["ruined", "tall", "windswept"])
            self.assertTrue(ok)

            lores = list_lore(p)
            tower = next(l for l in lores if l["id"] == "tower")
            self.assertEqual(tower["keywords"], ["ruined", "tall", "windswept"])

    def test_character_listing_defaults_empty_keywords(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            sheet = "---\nid: bob\nname: Bob\n---\n# Bob\n\nA man.\n"
            write_character(p, "bob", sheet)
            chars = list_characters(p)
            bob = next(c for c in chars if c["id"] == "bob")
            self.assertEqual(bob["keywords"], [])


# ── Story-init prompt builders + direction threading ─────────────────────────

class InitPromptTests(unittest.TestCase):
    def test_premise_prompt_includes_seed_and_required_keys(self):
        out = build_premise_prompt("dragons and accountants", direction="")
        self.assertIn("dragons and accountants", out)
        for k in ("title", "premise"):
            self.assertIn(k, out)

    def test_premise_prompt_threads_direction(self):
        out = build_premise_prompt("seed", direction="grim and slow")
        self.assertIn("DIRECTION:", out)
        self.assertIn("grim and slow", out)

    def test_premise_prompt_no_direction_omits_block(self):
        out = build_premise_prompt("seed", direction="")
        self.assertNotIn("DIRECTION:", out)
        out2 = build_premise_prompt("seed", direction="   ")
        self.assertNotIn("DIRECTION:", out2)

    def test_tone_themes_prompt(self):
        out = build_tone_themes_prompt("A grim caper.", direction="more humour")
        for k in ("tone", "themes", "PREMISE:"):
            self.assertIn(k, out)
        self.assertIn("more humour", out)

    def test_world_prompt(self):
        out = build_world_prompt("p", tone="t", themes="th", direction="forest setting")
        for k in ("world_overview", "TONE:", "THEMES:"):
            self.assertIn(k, out)
        self.assertIn("forest setting", out)

    def test_opening_prompt(self):
        out = build_opening_prompt("p", world_overview="w", direction="start in flames")
        self.assertIn("opening_situation", out)
        self.assertIn("start in flames", out)

    def test_characters_sketch_prompt_specifies_count(self):
        out = build_characters_sketch_prompt("p", world_overview="w", count=5, direction="all morally grey")
        self.assertIn("5", out)
        for k in ("characters", "id", "name", "description"):
            self.assertIn(k, out)
        self.assertIn("morally grey", out)

    def test_characters_sketch_prompt_requests_enrichment_fields(self):
        out = build_characters_sketch_prompt("p", world_overview="w", count=3)
        for field in ("physical", "personality", "motivation", "backstory", "relationships", "speech"):
            self.assertIn(field, out)

    def test_locations_sketch_prompt_specifies_count(self):
        out = build_locations_sketch_prompt("p", world_overview="w", count=4, direction="all coastal")
        self.assertIn("4", out)
        for k in ("locations", "id", "name", "description"):
            self.assertIn(k, out)
        self.assertIn("coastal", out)

    def test_story_points_threads_direction(self):
        out = build_story_points_prompt(
            premise="p", tone="t", themes="th", world_overview="w",
            num_acts=2, direction="emphasise reversals",
        )
        self.assertIn("DIRECTION:", out)
        self.assertIn("emphasise reversals", out)

    def test_suggest_names_threads_direction(self):
        out = build_suggest_names_prompt("a dark alley", suggest_arc=False, direction="prefer numbered seasons")
        self.assertIn("DIRECTION:", out)
        self.assertIn("prefer numbered seasons", out)

    def test_entity_prompt_threads_direction(self):
        out = build_entity_extraction_prompt("Scene text.", direction="ignore the narrator")
        self.assertIn("DIRECTION:", out)
        self.assertIn("ignore the narrator", out)

    def test_keyword_prompt_threads_direction(self):
        out = build_keyword_extraction_prompt("Sheet text.", kind="character", direction="focus on flaws")
        self.assertIn("DIRECTION:", out)
        self.assertIn("focus on flaws", out)


# ── Generic JSON-object salvage + sketch normaliser ──────────────────────────

class JsonSalvageTests(unittest.TestCase):
    def testparse_json_object_basic(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def testparse_json_object_with_fence(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def testparse_json_object_with_preamble(self):
        self.assertEqual(parse_json_object('Output: {"a": 1, "b": "two"}'), {"a": 1, "b": "two"})

    def testparse_json_object_garbage(self):
        self.assertIsNone(parse_json_object("not json"))
        self.assertIsNone(parse_json_object(""))

    def testparse_json_object_rejects_array(self):
        self.assertIsNone(parse_json_object('[1,2,3]'))


class NormaliseSketchListTests(unittest.TestCase):
    def test_strips_invalid_rows(self):
        items = [
            {"id": "alice", "name": "Alice", "description": "a scribe"},
            {"id": "", "name": "Bob", "description": "no id"},
            {"id": "carol", "name": "Carol"},  # missing description
            "not a dict",
        ]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "alice")

    def test_lowercases_and_slugifies_id(self):
        items = [{"id": "Warden KAEL!", "name": "Kael", "description": "Hard"}]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(out[0]["id"], "warden_kael_")

    def test_dedupes_ids(self):
        items = [
            {"id": "alice", "name": "Alice", "description": "first"},
            {"id": "alice", "name": "Alice2", "description": "dup"},
        ]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(len(out), 1)

    def test_caps_count(self):
        items = [{"id": f"c{i}", "name": f"C{i}", "description": "x"} for i in range(20)]
        out = _normalise_sketch_list(items, count=3)
        self.assertEqual(len(out), 3)


# ── Rebuild story.json from disk + atomic writes ──────────────────────────────

class RebuildStoryTests(unittest.TestCase):
    def _seed_two_chained(self, tmp):
        from harness.project import load_story
        p = init_project(Path(tmp), title="Test")
        out1 = ModelOutput(
            prose="Scene one.",
            choices=[ParsedChoice(text="Onward", hint="continue")],
            summary="Open.",
            characters_present=[CharacterDelta(id="alice", status="wary")],
        )
        pid1, _ = create_passage(p, "intro", "01_a", out1, None)
        out2 = ModelOutput(prose="Scene two.", choices=[], summary="Close.")
        pid2, _ = create_passage(
            p, "intro", "02_b", out2, pid1, choice_index=0, passage_type="ending",
        )
        return p, pid1, pid2

    def test_rebuild_roundtrips_structure(self):
        from harness.passage import rebuild_and_save
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p, pid1, pid2 = self._seed_two_chained(tmp)
            before = load_story(p)
            rebuild_and_save(p)
            after = load_story(p)
            self.assertEqual(set(after.passages), set(before.passages))
            self.assertEqual(after.start_passage, before.start_passage)
            self.assertEqual(after.passages[pid1].children, [pid2])
            self.assertEqual(after.passages[pid2].parents, [pid1])
            self.assertEqual(after.passages[pid2].passage_type, "ending")

    def test_rebuild_preserves_snapshot_and_summary(self):
        from harness.passage import rebuild_and_save
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p, pid1, _ = self._seed_two_chained(tmp)
            rebuild_and_save(p)
            after = load_story(p)
            self.assertEqual(after.passages[pid1].summary, "Open.")
            present = after.passages[pid1].snapshot.characters_present
            self.assertEqual([c.id for c in present], ["alice"])

    def test_rebuild_drops_passage_whose_file_is_gone(self):
        from harness.passage import rebuild_and_save
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p, pid1, pid2 = self._seed_two_chained(tmp)
            (p.root / load_story(p).passages[pid2].file).unlink()
            rebuild_and_save(p)
            after = load_story(p)
            self.assertNotIn(pid2, after.passages)
            self.assertIn(pid1, after.passages)

    def test_rebuild_restores_passage_missing_from_manifest(self):
        from harness.passage import rebuild_and_save
        from harness.project import load_story, save_story
        with TemporaryDirectory() as tmp:
            p, pid1, pid2 = self._seed_two_chained(tmp)
            graph = load_story(p)
            del graph.passages[pid2]  # simulate manifest drift (file still on disk)
            save_story(p, graph)
            report = rebuild_and_save(p)
            after = load_story(p)
            self.assertIn(pid2, after.passages)
            self.assertTrue(report == [] or isinstance(report, list))

    def test_state_writes_recovered_from_tw(self):
        from harness.passage import scan_state_writes
        tw = '<<set $met_alice to true>>\n<<set $gold = 5>>\nShe nods. $met_alice'
        self.assertEqual(scan_state_writes(tw), ["$gold", "$met_alice"])


class AtomicWriteTests(unittest.TestCase):
    def test_no_leftover_temp_files(self):
        from harness.project import save_story, load_story
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            save_story(p, load_story(p))
            leftovers = list(Path(tmp).glob(".*.tmp"))
            self.assertEqual(leftovers, [])

    def test_story_json_survives_rewrite(self):
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="A.", choices=[ParsedChoice(text="go", hint="h")], summary="S.")
            pid, _ = create_passage(p, "intro", "01_a", out, None)
            self.assertIn(pid, load_story(p).passages)
            self.assertTrue(p.story_json.exists())


# ── Commit concurrency ───────────────────────────────────────────────────────

class CommitConcurrencyTests(unittest.TestCase):
    def test_parallel_commits_get_unique_ids_and_files(self):
        """Two threads racing create_passage must never share id or file."""
        import threading
        from harness.passage import create_passage

        N = 8  # parallel workers
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            # Seed a root passage so each worker can hang a child off it.
            seed = ModelOutput(
                prose="Seed.",
                choices=[ParsedChoice(text="Onward", hint="continue")],
                summary="Seed.",
            )
            root_id, _ = create_passage(p, "intro", "00_root", seed, None)

            results: list[str] = []
            errors: list[Exception] = []
            barrier = threading.Barrier(N)

            def worker():
                try:
                    barrier.wait()  # release all threads at once for maximum contention
                    out = ModelOutput(
                        prose="Branch prose.",
                        choices=[],
                        summary="Branch.",
                    )
                    pid, _ = create_passage(
                        p, "intro", "01_branch", out, root_id,
                        passage_type="ending",
                    )
                    results.append(pid)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(N)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), N)
            self.assertEqual(len(set(results)), N, "passage ids collided under contention")

            # File paths must also be unique.
            from harness.project import load_story
            graph = load_story(p)
            files = [graph.passages[pid].file for pid in results]
            self.assertEqual(len(set(files)), N, "file paths collided under contention")


# ── Arc name normalization ──────────────────────────────────────────────────

class ArcNameNormalizationTests(unittest.TestCase):
    def test_plain_name_gets_number_prefix(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("atlantis", []), "01_atlantis")

    def test_existing_number_preserved(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("02_ravenhold", ["01_atlantis"]), "02_ravenhold")

    def test_nn_prefix_stripped(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("nn_01_atlantis", []), "01_atlantis")
        self.assertEqual(normalize_arc_name("nn_02_ravenhold", ["01_atlantis"]), "02_ravenhold")

    def test_auto_number_avoids_conflicts(self):
        from harness.planning import normalize_arc_name
        result = normalize_arc_name("curious_adventure", ["01_atlantis", "02_ravenhold"])
        self.assertEqual(result, "03_curious_adventure")

    def test_blank_returns_empty(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("", []), "")
        self.assertEqual(normalize_arc_name("   ", []), "")

    def test_uppercase_lowered(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("UPPER CASE", []), "01_upper_case")

    def test_double_underscore_collapsed(self):
        from harness.planning import normalize_arc_name
        self.assertEqual(normalize_arc_name("arc 4: the deep", []), "01_arc_4_the_deep")


# ── Sketch list enrichment ─────────────────────────────────────────────────────

class SketchListEnrichmentTests(unittest.TestCase):
    def test_enrichment_fields_passed_through(self):
        items = [{
            "id": "kael", "name": "Kael", "description": "A warden.",
            "physical": "Tall, scarred",
            "personality": "Stoic, loyal",
            "motivation": "Duty to the crown",
            "backstory": "Former soldier",
            "relationships": "Rival to Jack",
            "speech": "Clipped, formal",
        }]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["physical"], "Tall, scarred")
        self.assertEqual(out[0]["personality"], "Stoic, loyal")
        self.assertEqual(out[0]["motivation"], "Duty to the crown")
        self.assertEqual(out[0]["backstory"], "Former soldier")
        self.assertEqual(out[0]["relationships"], "Rival to Jack")
        self.assertEqual(out[0]["speech"], "Clipped, formal")

    def test_missing_enrichment_fields_omitted(self):
        items = [{"id": "alice", "name": "Alice", "description": "A scribe."}]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(len(out), 1)
        self.assertNotIn("physical", out[0])
        self.assertEqual(out[0]["description"], "A scribe.")

    def test_partial_enrichment(self):
        items = [{
            "id": "jack", "name": "Jack", "description": "A PI.",
            "physical": "Rugged",
        }]
        out = _normalise_sketch_list(items, count=5)
        self.assertEqual(out[0]["physical"], "Rugged")
        self.assertNotIn("personality", out[0])


# ── Lore arc-context matching ─────────────────────────────────────────────────

class LoreArcContextTests(unittest.TestCase):
    def test_arc_prefix_matching(self):
        from harness.generators import _entities_in_context
        from harness.models import Snapshot
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            write_lore_entity(p, "locations", "atlantis_ruins",
                              "---\nid: atlantis_ruins\n---\n# Atlantis Ruins\n\nUnderwater.")
            write_lore_entity(p, "locations", "ravenhold_market",
                              "---\nid: ravenhold_market\n---\n# Ravenhold Market\n\nBusy.")
            result = _entities_in_context(p, Snapshot(), "", arc_name="atlantis")
            self.assertIn("atlantis_ruins", result)
            self.assertNotIn("ravenhold_market", result)

    def test_nn_prefix_arc_still_matches(self):
        from harness.generators import _entities_in_context
        from harness.models import Snapshot
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            write_lore_entity(p, "locations", "atlantis_ruins",
                              "---\nid: atlantis_ruins\n---\n# Atlantis Ruins\n\nUnderwater.")
            result = _entities_in_context(p, Snapshot(), "", arc_name="01_atlantis")
            self.assertIn("atlantis_ruins", result)

    def test_no_arc_no_match_without_prompt(self):
        from harness.generators import _entities_in_context
        from harness.models import Snapshot
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            write_lore_entity(p, "locations", "atlantis_ruins",
                              "---\nid: atlantis_ruins\n---\n# Atlantis Ruins\n\nUnderwater.")
            result = _entities_in_context(p, Snapshot(), "", arc_name="")
            self.assertNotIn("atlantis_ruins", result)


if __name__ == "__main__":
    unittest.main()

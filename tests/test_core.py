from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.compile import (
    _build_tweego_argv,
    _storydata_twee,
    _storyinit_twee,
    collect_passage_files,
)
from harness.models import (
    HarnessConfig,
    ModelOutput,
    ParsedChoice,
    PassageEntry,
    StateVariable,
    StoryGraph,
)
from harness.ollama import parse_model_output
from harness.passage import create_passage, sync_manifest
from harness.project import ProjectPaths, init_project, load_config
from harness.validation import (
    _iter_macro_tags,
    _reachable_unset,
    check_macro_pairing,
    run_validation,
)


class ParserTests(unittest.TestCase):
    def test_ignores_template_placeholders(self):
        parsed = parse_model_output(
            """PROSE:
The corridor hums.

CHOICES:
- Listen | follow the sound
- Leave | return outside

MEDIA:
(type): (keyword, keyword, keyword)

NEW_CHARACTERS:
(id) | (one paragraph prose sheet)

SUMMARY:
The corridor hums.
"""
        )

        self.assertEqual(parsed.media, [])
        self.assertEqual(parsed.new_characters, [])
        self.assertEqual(len(parsed.choices), 2)


class PassageCreationTests(unittest.TestCase):
    def test_duplicate_slug_gets_unique_file(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            output = ModelOutput(
                prose="A beginning.",
                choices=[ParsedChoice(text="Go", hint="next")],
                summary="A beginning.",
            )

            first_id, _ = create_passage(p, "intro", "01_start", output, None)
            second_id, graph = create_passage(p, "intro", "01_start", output, first_id)

            self.assertNotEqual(first_id, second_id)
            self.assertNotEqual(graph.passages[first_id].file, graph.passages[second_id].file)

            validation = run_validation(p)
            duplicate_errors = [
                issue for issue in validation.errors
                if issue.code == "manifest_duplicate_file"
            ]
            self.assertEqual(duplicate_errors, [])


class StoryDataTests(unittest.TestCase):
    def test_init_generates_stable_ifid(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            cfg1 = load_config(p)
            cfg2 = load_config(ProjectPaths(Path(tmp)))
            self.assertTrue(cfg1.story_ifid)
            self.assertEqual(cfg1.story_ifid, cfg2.story_ifid)

    def test_storydata_twee_embeds_config(self):
        cfg = HarnessConfig(
            story_title="My Tale",
            story_format="SugarCube2",
            story_ifid="ABC-123",
            format_version="2.37.0",
        )
        out = _storydata_twee(cfg, "intro__01_start")
        self.assertIn(":: StoryData", out)
        self.assertIn('"ifid": "ABC-123"', out)
        self.assertIn('"format-version": "2.37.0"', out)
        self.assertIn('"start": "intro__01_start"', out)
        self.assertIn(":: StoryTitle\nMy Tale", out)


class TweeExtensionTests(unittest.TestCase):
    def test_collect_passage_files_picks_up_twee(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            arc_dir = p.arcs_dir / "intro"
            arc_dir.mkdir(parents=True, exist_ok=True)
            (arc_dir / "a.tw").write_text(":: a\nbody\n", encoding="utf-8")
            (arc_dir / "b.twee").write_text(":: b\nbody\n", encoding="utf-8")
            names = sorted(f.name for f in collect_passage_files(p))
            self.assertEqual(names, ["a.tw", "b.twee"])

    def test_sync_manifest_includes_twee_orphans(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            arc_dir = p.arcs_dir / "intro"
            arc_dir.mkdir(parents=True, exist_ok=True)
            orphan = arc_dir / "loose.twee"
            orphan.write_text(":: loose\nbody\n", encoding="utf-8")
            missing_from_json, _ = sync_manifest(p)
            self.assertIn("arcs/intro/loose.twee", missing_from_json)


class SugarCubeRenderTests(unittest.TestCase):
    def test_passage_type_appears_as_tag_in_header(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Final scene.", choices=[], summary="End.",
            )
            pid, graph = create_passage(
                p, "intro", "01_end", out, None, passage_type="ending",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn(f":: {pid} [intro ending]", tw)

    def test_normal_passage_header_omits_normal_tag(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Scene.", choices=[ParsedChoice(text="Go", hint="on")],
                summary="On.",
            )
            pid, graph = create_passage(p, "intro", "01_a", out, None)
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn(f":: {pid} [intro]", tw)
            self.assertNotIn("normal", tw.splitlines()[0])

    def test_state_write_choice_uses_two_arg_link(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Scene.",
                choices=[ParsedChoice(
                    text="Take it",
                    hint="grab the orb",
                    state_writes={"$has_orb": True},
                )],
                summary="Scene.",
            )
            pid, graph = create_passage(p, "intro", "01_a", out, None)
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # SugarCube two-arg <<link>> form, no inner <<goto>>
            self.assertIn('<<link "Take it" "UNRESOLVED_choice0_', tw)
            self.assertIn("<<set $has_orb to true>>", tw)
            self.assertNotIn("<<goto", tw.split('<<link "Take it"')[1].split("<</link>>")[0])

    def test_hub_choices_render_as_visited_gated_links(self):
        """Hub plain choices render as <<link>> wrapped in <<if not hasVisited>>,
        replacing the deprecated <<actions>> macro (SugarCube v2.37.0). See
        docs/sugarcube2-analysis.md §3.1."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Town square.",
                choices=[
                    ParsedChoice(text="Visit shop", hint="shop"),
                    ParsedChoice(text="Talk to king", hint="king"),
                ],
                summary="Hub.",
            )
            pid, graph = create_passage(
                p, "intro", "01_hub", out, None, passage_type="hub",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # No deprecated <<actions>> macro should appear.
            self.assertNotIn("<<actions ", tw)
            # Each plain choice is a <<link>> inside an <<if not hasVisited()>> gate.
            self.assertIn('<<if not hasVisited("UNRESOLVED_choice0_shop")>>', tw)
            self.assertIn('<<link "Visit shop" "UNRESOLVED_choice0_shop">><</link>>', tw)
            self.assertIn('<<if not hasVisited("UNRESOLVED_choice1_king")>>', tw)
            self.assertIn('<<link "Talk to king" "UNRESOLVED_choice1_king">><</link>>', tw)

    def test_hub_with_state_write_falls_back_to_per_choice_links(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Town square.",
                choices=[
                    ParsedChoice(text="Visit shop", hint="shop"),
                    ParsedChoice(
                        text="Bribe guard", hint="bribe",
                        state_writes={"$gold": 5},
                    ),
                ],
                summary="Hub.",
            )
            pid, graph = create_passage(
                p, "intro", "01_hub", out, None, passage_type="hub",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertNotIn("<<actions ", tw)
            # Plain choice still gets a visited-gated <<link>>; state-write
            # choice gets a <<link>> with the setter (no visit gate, since it
            # carries side-effects).
            self.assertIn('<<if not hasVisited("UNRESOLVED_choice0_shop")>>', tw)
            self.assertIn('<<link "Visit shop" "UNRESOLVED_choice0_shop">><</link>>', tw)
            self.assertIn('<<link "Bribe guard" "UNRESOLVED_choice1_bribe">>', tw)
            self.assertIn("<<set $gold to 5>>", tw)


class ReachableUnsetTests(unittest.TestCase):
    """Forward-reachability core of the undeclared-state-var check."""

    @staticmethod
    def _graph(edges: dict[str, list[str]], writers: dict[str, list[str]], start: str):
        g = StoryGraph(start_passage=start)
        for pid, children in edges.items():
            g.passages[pid] = PassageEntry(
                file=f"arcs/x/{pid}.tw", arc="x",
                children=children, state_writes=writers.get(pid, []),
            )
        w = {pid: set(e.state_writes) for pid, e in g.passages.items()}
        return g, w

    def test_no_writer_all_reachable_unset(self):
        g, w = self._graph({"a": ["b"], "b": ["c"], "c": []}, {}, "a")
        self.assertEqual(_reachable_unset(g, w, "$v"), {"a", "b", "c"})

    def test_writer_blocks_downstream(self):
        g, w = self._graph({"a": ["b"], "b": ["c"], "c": []}, {"a": ["$v"]}, "a")
        # a itself read-unsafe (own write doesn't satisfy own read); b,c safe.
        self.assertEqual(_reachable_unset(g, w, "$v"), {"a"})

    def test_diamond_one_branch_sets(self):
        # a -> l,r ; l,r -> m. Only l sets $v, so m still reachable unset via r.
        g, w = self._graph(
            {"a": ["l", "r"], "l": ["m"], "r": ["m"], "m": []},
            {"l": ["$v"]}, "a",
        )
        self.assertEqual(_reachable_unset(g, w, "$v"), {"a", "l", "r", "m"})

    def test_diamond_both_branches_set(self):
        g, w = self._graph(
            {"a": ["l", "r"], "l": ["m"], "r": ["m"], "m": []},
            {"l": ["$v"], "r": ["$v"]}, "a",
        )
        self.assertEqual(_reachable_unset(g, w, "$v"), {"a", "l", "r"})

    def test_cycle_terminates(self):
        g, w = self._graph({"a": ["b"], "b": ["a"]}, {}, "a")
        self.assertEqual(_reachable_unset(g, w, "$v"), {"a", "b"})


class UndeclaredStateVarValidationTests(unittest.TestCase):
    def test_read_without_setter_is_error(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="The gate reads $has_key on entry.",
                choices=[ParsedChoice(text="Go", hint="on")],
                summary="Gate.",
            )
            create_passage(p, "intro", "01_gate", out, None)
            result = run_validation(p)
            self.assertTrue(any(e.code == "undeclared_state_var" for e in result.errors))

    def test_declared_default_silences_error(self):
        from harness.project import load_story, save_story
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="The gate reads $has_key on entry.",
                choices=[ParsedChoice(text="Go", hint="on")],
                summary="Gate.",
            )
            create_passage(p, "intro", "01_gate", out, None)
            graph = load_story(p)
            graph.state_variables["$has_key"] = StateVariable(type="bool", default=False)
            save_story(p, graph)
            result = run_validation(p)
            self.assertFalse(any(e.code == "undeclared_state_var" for e in result.errors))


class MacroPairingTests(unittest.TestCase):
    @staticmethod
    def _check(tmp, body):
        p = init_project(Path(tmp), title="Test")
        f = p.arcs_dir / "x" / "01.tw"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(":: x__01 [x]\n" + body + "\n", encoding="utf-8")
        graph = StoryGraph()
        graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
        return check_macro_pairing(p, graph)

    def test_balanced_nesting_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                self._check(tmp, "<<if $x>><<for _i to 3>>hi<</for>><</if>>"), [])

    def test_wrong_order_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<if $x>><<for _a>><</if>><</for>>")
            self.assertTrue(issues)
            self.assertEqual(issues[0].code, "macro_pairing")

    def test_unclosed_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<if $x>>hi")
            self.assertTrue(any("never closed" in i.message for i in issues))

    def test_stray_close_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "hi <</if>>")
            self.assertTrue(any("stray" in i.message for i in issues))

    def test_quote_shielded_delimiter_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, '<<if $x eq "a>>b">>yes<</if>>'), [])

    def test_inline_print_macros_ignored(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<= $x>><<- $y>><<if $z>>ok<</if>>"), [])

    def test_if_elseif_else_chain_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                self._check(tmp, "<<if $x>>a<<elseif $y>>b<<else>>c<</if>>"), [])

    def test_custom_widget_close_ignored(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<myblock>>x<</myblock>>"), [])


class IterMacroTagsTests(unittest.TestCase):
    def test_quote_keeps_tag_whole(self):
        tags = list(_iter_macro_tags('<<if $x eq "a>>b">>yes<</if>>'))
        self.assertEqual(tags, [(False, "if", 1), (True, "if", 1)])

    def test_unterminated_macro_stops_cleanly(self):
        self.assertEqual(list(_iter_macro_tags("text <<if $x")), [])

    def test_line_numbers_tracked(self):
        tags = list(_iter_macro_tags("line1\n<<if $x>>\n<</if>>"))
        self.assertEqual(tags, [(False, "if", 2), (True, "if", 3)])


class GenerationAuditTests(unittest.TestCase):
    def test_record_read_roundtrip(self):
        from harness.audit import record_generation, read_generation
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            gid = record_generation(p, {
                "label": "passage", "model": "m", "raw_output": "RAW PROSE",
            }, kind="draft")
            self.assertTrue(gid)
            rec = read_generation(p, gid)
            self.assertEqual(rec["raw_output"], "RAW PROSE")
            self.assertEqual(rec["kind"], "draft")
            self.assertEqual(rec["id"], gid)

    def test_list_newest_first_with_preview(self):
        from harness.audit import record_generation, list_generations
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            record_generation(p, {"raw_output": "first " * 100}, kind="draft")
            second = record_generation(p, {"raw_output": "second"}, kind="commit")
            rows = list_generations(p, limit=10)
            self.assertEqual(rows[0]["id"], second)  # newest first
            self.assertEqual(rows[0]["kind"], "commit")
            self.assertLessEqual(len(rows[0]["raw_preview"]), 280)
            self.assertEqual(rows[-1]["raw_chars"], len("first " * 100))

    def test_prune_keeps_only_max(self):
        from harness.audit import record_generation, list_generations
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            for i in range(5):
                record_generation(p, {"raw_output": f"r{i}"}, kind="draft", max_keep=2)
            self.assertEqual(len(list_generations(p, limit=99)), 2)

    def test_read_rejects_traversal_and_missing(self):
        from harness.audit import read_generation
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            self.assertIsNone(read_generation(p, "../../etc/passwd"))
            self.assertIsNone(read_generation(p, "nope"))


class StoryInitTests(unittest.TestCase):
    def test_empty_when_no_declared_defaults(self):
        graph = StoryGraph()
        graph.state_variables["$x"] = StateVariable(type="bool", default=None)
        self.assertEqual(_storyinit_twee(graph), "")

    def test_emits_set_for_each_declared_default(self):
        graph = StoryGraph()
        graph.state_variables["$flag"] = StateVariable(type="bool", default=True)
        graph.state_variables["$gold"] = StateVariable(type="int", default=10)
        graph.state_variables["$name"] = StateVariable(type="str", default='Anna "the bold"')
        out = _storyinit_twee(graph)
        self.assertIn(":: StoryInit", out)
        self.assertIn("<<set $flag to true>>", out)
        self.assertIn("<<set $gold to 10>>", out)
        # quote escaping
        self.assertIn('<<set $name to "Anna \\"the bold\\"">>', out)


class TweegoArgvTests(unittest.TestCase):
    def test_argv_default_is_minimal(self):
        cfg = HarnessConfig()
        argv = _build_tweego_argv("tweego", cfg, Path("/src"), Path("/out.html"))
        # tweego, -o, out, src
        self.assertEqual(argv[0], "tweego")
        self.assertIn("-o", argv)
        self.assertNotIn("-l", argv)
        self.assertNotIn("-t", argv)

    def test_argv_threads_log_test_head_modules(self):
        cfg = HarnessConfig(
            tweego_log_stats=True,
            tweego_test_mode=True,
            tweego_head_file="extras/head.html",
            tweego_module_dirs=["modA", "modB"],
        )
        argv = _build_tweego_argv("tweego", cfg, Path("/src"), Path("/out.html"))
        self.assertIn("-l", argv)
        self.assertIn("-t", argv)
        self.assertIn("--head=extras/head.html", argv)
        # two -m flags with their dirs
        m_positions = [i for i, a in enumerate(argv) if a == "-m"]
        self.assertEqual(len(m_positions), 2)
        self.assertEqual(argv[m_positions[0] + 1], "modA")
        self.assertEqual(argv[m_positions[1] + 1], "modB")


class PassageDeleteTests(unittest.TestCase):
    def test_delete_cleans_references_and_file(self):
        from harness.passage import delete_passage
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(prose="Start.", choices=[ParsedChoice(text="Go", hint="next")], summary="Start.")
            root, g = create_passage(p, "intro", "01_start", out, None)
            child, g = create_passage(p, "intro", "02_next", out, root, choice_index=0)

            child_file = p.root / g.passages[child].file
            self.assertTrue(child_file.exists())

            ok, _ = delete_passage(p, child)
            self.assertTrue(ok)
            g = load_story(p)
            self.assertNotIn(child, g.passages)               # gone from manifest
            self.assertFalse(child_file.exists())             # file removed
            self.assertNotIn(child, g.passages[root].children) # parent detached
            # parent's link to the deleted child is now an UNRESOLVED marker
            parent_tw = (p.root / g.passages[root].file).read_text(encoding="utf-8")
            self.assertNotIn(f"|{child}]]", parent_tw)
            self.assertIn("UNRESOLVED_deleted_", parent_tw)

    def test_delete_missing_returns_false(self):
        from harness.passage import delete_passage
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            ok, msg = delete_passage(p, "nope__x")
            self.assertFalse(ok)


class MediaStagingTests(unittest.TestCase):
    def _project_with_media(self, tmp):
        """Project with one passage carrying one resolved image slot."""
        from harness.models import ParsedMediaSlot
        p = init_project(Path(tmp), title="Test")
        # a real source image the slot resolves to
        src = p.media_dir / "scene.png"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"\x89PNG\r\n\x1a\n")
        output = ModelOutput(
            prose="A scene.",
            choices=[ParsedChoice(text="Go", hint="next")],
            summary="A scene.",
            media=[ParsedMediaSlot(type="image", keywords=["dusk"], description="dusk platform")],
        )
        pid, graph = create_passage(p, "intro", "01_start", output, None)
        slot_id = graph.passages[pid].media_slots[0]
        return p, pid, slot_id

    def test_description_flows_to_slot(self):
        with TemporaryDirectory() as tmp:
            p, pid, slot_id = self._project_with_media(tmp)
            from harness.media import get_slot
            self.assertEqual(get_slot(p, slot_id).description, "dusk platform")

    def test_stage_copies_into_build_media_with_relative_path(self):
        with TemporaryDirectory() as tmp:
            from harness.media import resolve_slot, stage_media_for_build
            p, pid, slot_id = self._project_with_media(tmp)
            ok, _ = resolve_slot(p, slot_id, "media/scene.png")
            self.assertTrue(ok)
            rel_map = stage_media_for_build(p, p.build_dir)
            self.assertIn(slot_id, rel_map)
            self.assertEqual(rel_map[slot_id]["src"], "media/scene.png")
            # file physically copied next to where story.html lands
            self.assertTrue((p.build_dir / "media" / "scene.png").exists())

    def test_markup_uses_relative_path_alt_and_caption(self):
        with TemporaryDirectory() as tmp:
            from harness.media import media_markup, set_slot_meta, get_slot
            p, pid, slot_id = self._project_with_media(tmp)
            set_slot_meta(p, slot_id, alt="A rainy platform", caption="Ravenhold")
            html = media_markup(get_slot(p, slot_id), "media/scene.png")
            self.assertIn('src="media/scene.png"', html)
            self.assertIn('alt="A rainy platform"', html)
            self.assertIn("Ravenhold", html)
            self.assertIn("loading=\"lazy\"", html)  # default lazy on images
            self.assertNotIn(str(p.root), html)       # no absolute path leaks

    def test_embed_leaves_pending_slot_as_comment(self):
        with TemporaryDirectory() as tmp:
            from harness.compile import _embed_media
            p, pid, slot_id = self._project_with_media(tmp)
            content = f"text\n<!-- media:{slot_id} -->\n"
            # empty rel_map → pending/unstaged, comment preserved
            self.assertIn(f"<!-- media:{slot_id} -->", _embed_media(p, content, {}))


class PlanningTests(unittest.TestCase):
    def _seed(self, tmp):
        p = init_project(Path(tmp), title="Test")
        output = ModelOutput(
            prose="Start.", choices=[ParsedChoice(text="Go", hint="next")], summary="Start.",
        )
        pid, _ = create_passage(p, "intro", "01_start", output, None)
        return p, pid

    def test_add_beat_and_coverage(self):
        with TemporaryDirectory() as tmp:
            from harness import planning
            p, pid = self._seed(tmp)
            b = planning.add_beat(p, "Player reaches the city", act="Act 1")
            ov = planning.plan_overview(p)
            self.assertEqual(len(ov["beats"]), 1)
            self.assertFalse(ov["beats"][0]["covered"])
            self.assertIn(b.id, ov["gaps"]["open_beats"])

            planning.set_passage_beats(p, pid, [b.id])
            ov = planning.plan_overview(p)
            self.assertTrue(ov["beats"][0]["covered"])
            self.assertEqual(ov["beats"][0]["passages"], [pid])
            self.assertNotIn(b.id, ov["gaps"]["open_beats"])

    def test_focus_beat_prefers_arc_open_beat(self):
        with TemporaryDirectory() as tmp:
            from harness import planning
            from harness.project import load_story
            p, pid = self._seed(tmp)
            b1 = planning.add_beat(p, "First beat")
            b2 = planning.add_beat(p, "Arc-specific beat")
            planning.set_arc_plan(p, "intro", beat_ids=[b2.id], goal="Establish the city")
            focus = planning.next_focus_beat(load_story(p), "intro")
            self.assertEqual(focus.id, b2.id)
            txt = planning.plan_focus_text(p, "intro")
            self.assertIn("Arc-specific beat", txt)
            self.assertIn("Establish the city", txt)

    def test_delete_beat_scrubs_references(self):
        with TemporaryDirectory() as tmp:
            from harness import planning
            from harness.project import load_story
            p, pid = self._seed(tmp)
            b = planning.add_beat(p, "Beat")
            planning.set_passage_beats(p, pid, [b.id])
            planning.set_arc_plan(p, "intro", beat_ids=[b.id])
            self.assertTrue(planning.delete_beat(p, b.id))
            g = load_story(p)
            self.assertEqual(g.passages[pid].plan_beats, [])
            self.assertEqual(g.arcs["intro"].beat_ids, [])

    def test_scene_crud_and_bulk(self):
        from harness import planning
        from harness.project import load_story
        with TemporaryDirectory() as tmp:
            p, pid = self._seed(tmp)
            b = planning.add_beat(p, "Reach the harbor")
            sc = planning.add_scene(p, "intro", title="Docks at dusk",
                                    summary="Arrive at the harbor", keywords=["fog","rope"],
                                    characters=["alice"], beat_ids=[b.id])
            ov = planning.plan_overview(p)
            arc = next(a for a in ov["arcs"] if a["arc"] == "intro")
            self.assertEqual(len(arc["scenes"]), 1)
            self.assertEqual(arc["scenes"][0]["beat_ids"], [b.id])

            self.assertTrue(planning.update_scene(p, "intro", sc.id, passage_id=pid))
            g = load_story(p)
            scene = g.arcs["intro"].scenes[0]
            self.assertEqual(scene.passage_id, pid)
            self.assertEqual(scene.status, "drafted")

            created = planning.add_scenes_bulk(p, "intro", [
                {"title": "A", "summary": "s", "keywords": ["x"]},
                {"title": "", "summary": ""},  # skipped — no content
            ])
            self.assertEqual(len(created), 1)
            self.assertTrue(planning.delete_scene(p, "intro", sc.id))
            self.assertFalse(planning.delete_scene(p, "intro", "nope"))

    def test_import_story_points_parses_acts_and_questions(self):
        with TemporaryDirectory() as tmp:
            from harness import planning
            p, _ = self._seed(tmp)
            p.story_points_md.write_text(
                "# Story Points\n\n## Act 1\n- Arrive in town\n- Meet the warden\n\n"
                "## Open Questions\n- Who sent the letter\n",
                encoding="utf-8",
            )
            ov = planning.import_story_points(p, replace=True)
            texts = [b["text"] for b in ov["beats"]]
            self.assertIn("Arrive in town", texts)
            self.assertIn("Meet the warden", texts)
            self.assertIn("Act 1", ov["acts"])
            self.assertIn("Who sent the letter", ov["open_questions"])


class PlanFocusPromptTests(unittest.TestCase):
    def test_compact_prompt_includes_focus_when_set(self):
        from harness.prompts import build_compact_passage_prompt
        with_focus = build_compact_passage_prompt(
            premise="p", story_points="sp", arc_notes="a", entities_text="e",
            parent_prose="pp", snapshot_text="s", human_prompt="h",
            plan_focus="Target beat: reach the city",
        )
        self.assertIn("PLAN FOCUS:", with_focus)
        self.assertIn("reach the city", with_focus)

    def test_compact_prompt_omits_focus_block_when_empty(self):
        from harness.prompts import build_compact_passage_prompt
        without = build_compact_passage_prompt(
            premise="p", story_points="sp", arc_notes="a", entities_text="e",
            parent_prose="pp", snapshot_text="s", human_prompt="h",
        )
        self.assertNotIn("PLAN FOCUS:", without)


# ── SugarCube 2 documentation integration tests ───────────────────────────────


class SugarCubeGuidancePromptTests(unittest.TestCase):
    """The SugarCube authoring cheat sheet must appear in full + JSON prompts."""

    def test_full_prompt_contains_sugarcube_guidance(self):
        from harness.prompts import build_full_passage_prompt, SUGARCUBE_GUIDANCE
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
        )
        self.assertIn(SUGARCUBE_GUIDANCE, prompt)
        # Variable scoping guidance present.
        self.assertIn("_var", prompt)
        self.assertIn("$var", prompt)
        # Markup (not markdown) guidance present.
        self.assertIn("''bold''", prompt)
        self.assertIn("//italic//", prompt)

    def test_json_prompt_contains_sugarcube_guidance(self):
        from harness.prompts import build_json_passage_prompt, SUGARCUBE_GUIDANCE
        prompt = build_json_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
        )
        self.assertIn(SUGARCUBE_GUIDANCE, prompt)

    def test_compact_prompt_omits_sugarcube_guidance(self):
        """Compact prompt is token-budget-constrained; guidance is reserved
        for the full and JSON prompts."""
        from harness.prompts import build_compact_passage_prompt, SUGARCUBE_GUIDANCE
        prompt = build_compact_passage_prompt(
            premise="p", story_points="sp", arc_notes="a", entities_text="e",
            parent_prose="pp", snapshot_text="s", human_prompt="h",
        )
        self.assertNotIn(SUGARCUBE_GUIDANCE, prompt)

    def test_prompt_version_bumped(self):
        """PROMPT_VERSION must reflect the SugarCube guidance addition."""
        from harness.prompts import PROMPT_VERSION
        self.assertGreaterEqual(PROMPT_VERSION, 6)


class TemplatePromptTests(unittest.TestCase):
    """Template style guidance must appear in prompts only when set."""

    def test_full_prompt_includes_template_block(self):
        from harness.prompts import build_full_passage_prompt
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
            template_id="space-tech",
        )
        self.assertIn("[TEMPLATE STYLE: Space-Tech UI]", prompt)

    def test_full_prompt_omits_template_block_when_empty(self):
        from harness.prompts import build_full_passage_prompt
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
            template_id="",
        )
        self.assertNotIn("[TEMPLATE STYLE:", prompt)

    def test_json_prompt_includes_template_block(self):
        from harness.prompts import build_json_passage_prompt
        prompt = build_json_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
            template_id="character-creator",
        )
        self.assertIn("[TEMPLATE STYLE: Character Creator]", prompt)

    def test_unknown_template_id_omits_block(self):
        from harness.prompts import build_full_passage_prompt
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
            template_id="nonexistent",
        )
        self.assertNotIn("[TEMPLATE STYLE:", prompt)


class TemplateRegistryTests(unittest.TestCase):
    """The template registry catalogs the 7 bundled HTML templates."""

    def test_registry_has_seven_templates(self):
        from harness.templates import TEMPLATE_REGISTRY
        self.assertEqual(len(TEMPLATE_REGISTRY), 7)

    def test_expected_template_ids(self):
        from harness.templates import list_template_ids
        self.assertEqual(
            set(list_template_ids()),
            {
                "character-creator", "one-page", "settings",
                "simple-book", "space-tech", "title-page", "vn-lite-rpg",
            },
        )

    def test_get_template_returns_info(self):
        from harness.templates import get_template
        tpl = get_template("space-tech")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.name, "Space-Tech UI")
        self.assertTrue(tpl.has_story_interface)
        self.assertTrue(tpl.uses_widgets)

    def test_get_template_unknown_returns_none(self):
        from harness.templates import get_template
        self.assertIsNone(get_template("nope"))

    def test_template_guidance_returns_nonempty_for_known(self):
        from harness.templates import template_guidance
        g = template_guidance("vn-lite-rpg")
        self.assertIn("VN-lite", g)
        self.assertIn("[TEMPLATE STYLE:", g)

    def test_template_guidance_empty_for_unknown(self):
        from harness.templates import template_guidance
        self.assertEqual(template_guidance("nope"), "")

    def test_template_guidance_empty_for_empty(self):
        from harness.templates import template_guidance
        self.assertEqual(template_guidance(""), "")

    def test_template_css_path_exists_for_all(self):
        """Every registered template that declares a css_file must resolve
        to an existing file on disk."""
        from harness.templates import list_templates, template_css_path
        for tpl in list_templates():
            if tpl.css_file:
                p = template_css_path(tpl.id)
                self.assertIsNotNone(p, f"CSS missing for {tpl.id}")
                self.assertTrue(p.exists(), f"CSS file not found for {tpl.id}: {p}")

    def test_template_js_path_for_js_templates(self):
        """Templates with js_file must resolve to existing files; title-page
        (CSS-only, no JS) must return None."""
        from harness.templates import template_js_path
        cc_js = template_js_path("character-creator")
        self.assertIsNotNone(cc_js)
        self.assertTrue(cc_js.exists())
        tp_js = template_js_path("title-page")
        self.assertIsNone(tp_js)  # CSS-only template

    def test_template_assets_returns_css_and_js(self):
        from harness.templates import template_assets
        assets = template_assets("one-page")
        names = {p.name for p in assets}
        self.assertIn("StyleSheet.css", names)
        self.assertIn("Script.js", names)

    def test_template_assets_empty_for_unknown(self):
        from harness.templates import template_assets
        self.assertEqual(template_assets("nope"), [])


class TemplateAssetInjectionTests(unittest.TestCase):
    """compile.inject_template_assets copies CSS/JS into build_src."""

    def test_no_template_id_copies_nothing(self):
        from harness.compile import inject_template_assets
        with TemporaryDirectory() as tmp:
            build_src = Path(tmp)
            cfg = HarnessConfig()  # template_id=""
            copied = inject_template_assets(cfg, build_src)
            self.assertEqual(copied, [])
            self.assertEqual(list(build_src.iterdir()), [])

    def test_copies_css_and_js_for_template(self):
        from harness.compile import inject_template_assets
        with TemporaryDirectory() as tmp:
            build_src = Path(tmp)
            cfg = HarnessConfig(template_id="space-tech")
            copied = inject_template_assets(cfg, build_src)
            names = {p.name for p in copied}
            self.assertIn("StyleSheet.css", names)
            self.assertIn("Script.js", names)
            # Files exist on disk
            for f in copied:
                self.assertTrue(f.exists())
                self.assertTrue(f.stat().st_size > 0)

    def test_title_page_copies_only_css(self):
        from harness.compile import inject_template_assets
        with TemporaryDirectory() as tmp:
            build_src = Path(tmp)
            cfg = HarnessConfig(template_id="title-page")
            copied = inject_template_assets(cfg, build_src)
            self.assertEqual(len(copied), 1)
            self.assertTrue(copied[0].name.endswith(".css"))


class WidgetPassageRenderTests(unittest.TestCase):
    """widget and include passage types render SugarCube-idiomatic output."""

    def test_widget_auto_wraps_prose(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="You see $name standing there.",
                choices=[],
                summary="Widget body.",
            )
            pid, graph = create_passage(
                p, "intro", "01_stats_widget", out, None,
                passage_type="widget",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn("<<widget \"stats_widget\">>", tw)
            self.assertIn("You see $name standing there.", tw)
            self.assertIn("<</widget>>", tw)
            # widget tag in header
            self.assertIn("widget", tw.splitlines()[0])

    def test_widget_preserves_existing_widget_macro(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose='<<widget "greet">>Hello there.<</widget>>',
                choices=[],
                summary="Widget.",
            )
            pid, graph = create_passage(
                p, "intro", "01_greet_widget", out, None,
                passage_type="widget",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # Should NOT auto-wrap a second time
            self.assertEqual(tw.count("<<widget"), 1)
            self.assertIn("<<widget \"greet\">>", tw)

    def test_include_passage_renders_prose_verbatim(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Shared menu content here.",
                choices=[],
                summary="Include.",
            )
            pid, graph = create_passage(
                p, "intro", "01_menu_elements", out, None,
                passage_type="include",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn("Shared menu content here.", tw)
            # include tag in header, no choices rendered
            self.assertIn("include", tw.splitlines()[0])
            self.assertNotIn("<<link", tw)


class DeprecatedFeatureValidationTests(unittest.TestCase):
    """check_deprecated_features warns on SugarCube v2.37.0 deprecations."""

    @staticmethod
    def _check(tmp, body, tags=""):
        p = init_project(Path(tmp), title="Test")
        f = p.arcs_dir / "x" / "01.tw"
        f.parent.mkdir(parents=True, exist_ok=True)
        header = f":: x__01 [x{(' ' + tags) if tags else ''}]"
        f.write_text(header + "\n" + body + "\n", encoding="utf-8")
        from harness.project import load_story, save_story
        from harness.validation import check_deprecated_features
        graph = load_story(p)
        graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
        save_story(p, graph)
        return check_deprecated_features(p, graph)

    def test_actions_macro_warns(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<actions [[Go|target]]>>")
            self.assertTrue(any(i.code == "deprecated_macro" and "actions" in i.message for i in issues))

    def test_choice_macro_warns(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<choice \"opt\">>text<</choice>>")
            self.assertTrue(any(i.code == "deprecated_macro" and "choice" in i.message for i in issues))

    def test_silently_macro_warns(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<silently>>hidden<</silently>>")
            self.assertTrue(any(i.code == "deprecated_macro" and "silently" in i.message for i in issues))

    def test_silent_macro_does_not_warn(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<silent>>hidden<</silent>>")
            self.assertFalse(any(i.code == "deprecated_macro" for i in issues))

    def test_bookmark_tag_warns(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "body", tags="bookmark")
            self.assertTrue(any(i.code == "deprecated_tag" and "bookmark" in i.message for i in issues))

    def test_clean_passage_has_no_deprecation_warnings(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<if $x>>ok<</if>>\n<<link \"Go\" \"target\">><</link>>")
            self.assertEqual(
                [i for i in issues if i.code.startswith("deprecated")],
                [],
            )

    def test_deprecated_warnings_are_warnings_not_errors(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<actions [[Go|target]]>>")
            for i in issues:
                self.assertEqual(i.level, "warning")

    def test_storyshare_passage_warns(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "x" / "01.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(":: StoryShare [x]\nshare content\n", encoding="utf-8")
            from harness.project import load_story, save_story
            from harness.validation import check_deprecated_features
            graph = load_story(p)
            graph.passages["StoryShare"] = PassageEntry(file="arcs/x/01.tw", arc="x")
            save_story(p, graph)
            issues = check_deprecated_features(p, graph)
            self.assertTrue(any(i.code == "deprecated_passage" and "StoryShare" in i.message for i in issues))


class MacroContainerSetTests(unittest.TestCase):
    """MACRO_CONTAINERS includes the v2.37.x additions."""

    def test_silent_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("silent", MACRO_CONTAINERS)

    def test_do_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("do", MACRO_CONTAINERS)

    def test_script_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("script", MACRO_CONTAINERS)

    def test_done_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("done", MACRO_CONTAINERS)

    def test_silently_still_in_containers(self):
        """Deprecated silently is kept for backward-compat validation."""
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("silently", MACRO_CONTAINERS)

    def test_new_containers_validate_as_pairs(self):
        """<<silent>> and <<do>> should validate cleanly when properly closed."""
        with TemporaryDirectory() as tmp:
            from harness.validation import check_macro_pairing
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "x" / "01.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(":: x__01 [x]\n<<silent>>hi<</silent>><<do>>x<</do>>\n", encoding="utf-8")
            graph = StoryGraph()
            graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
            self.assertEqual(check_macro_pairing(p, graph), [])


class ScanStateReadsTests(unittest.TestCase):
    """scan_state_reads now covers RHS of <<set>>, naked prose vars, <<if>>."""

    def test_reads_rhs_of_set(self):
        from harness.passage import scan_state_reads
        reads = scan_state_reads("<<set $b to $a + 1>>")
        self.assertIn("$a", reads)
        self.assertNotIn("$b", reads)  # LHS is a write, not a read

    def test_reads_naked_prose_var(self):
        from harness.passage import scan_state_reads
        reads = scan_state_reads("You have $gold coins and $hp health.")
        self.assertIn("$gold", reads)
        self.assertIn("$hp", reads)

    def test_reads_if_condition_vars(self):
        from harness.passage import scan_state_reads
        reads = scan_state_reads("<<if $has_key and $door_open>>yes<</if>>")
        self.assertIn("$has_key", reads)
        self.assertIn("$door_open", reads)

    def test_reads_print_expr_vars(self):
        from harness.passage import scan_state_reads
        reads = scan_state_reads("<<print $obj.prop>>")
        self.assertIn("$obj", reads)


class HarnessConfigTemplateFieldTests(unittest.TestCase):
    """HarnessConfig carries a template_id field."""

    def test_default_template_id_empty(self):
        cfg = HarnessConfig()
        self.assertEqual(cfg.template_id, "")

    def test_template_id_set(self):
        cfg = HarnessConfig(template_id="vn-lite-rpg")
        self.assertEqual(cfg.template_id, "vn-lite-rpg")

    def test_template_id_round_trips_through_yaml(self):
        import yaml
        cfg = HarnessConfig(template_id="space-tech")
        dumped = yaml.dump(cfg.model_dump(), allow_unicode=True)
        loaded = yaml.safe_load(dumped)
        cfg2 = HarnessConfig.model_validate(loaded)
        self.assertEqual(cfg2.template_id, "space-tech")


if __name__ == "__main__":
    unittest.main()

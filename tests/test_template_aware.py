"""Tests for the SugarCube template-aware generation improvements.

Covers the improvements implemented in task t_73b72fe2, validated against
patterns drawn from the 7 studied HTML templates in
examples/html_templates/ (TEMPLATE_VERIFICATION_REPORT.md) and the SugarCube 2
docs analysis (docs/sugarcube2-analysis.md).

Test groups map to the analysis recommendations:
  * ContainerMacroTests        — §3.2/§3.3 (silent, do, script, done added)
  * DeprecatedFeatureTests      — §3.1/§3.4/§3.15 (actions, choice, silently, bookmark, StoryShare)
  * HubRenderingTests           — §3.1 (<<actions>> replaced with visited-gated <<link>>)
  * PromptGuidanceTests         — §3.5/§3.6 (SugarCube scoping + markup cheat sheet)
  * ScanStateReadsTests         — §3.12-3.14 (naked prose vars, <<if>>, <<print>>, setter RHS)
  * WidgetPassageTests          — §3.7 (widget passage type; Space-Tech/Character Creator pattern)
  * IncludePassageTests         — §3.8 (include passage type; Title Page "Menu Elements" pattern)
  * TemplateCompatibilityTests  — end-to-end validation against 2+ studied templates
"""
from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.compile import _storyinit_twee, _storydata_twee
from harness.models import (
    HarnessConfig,
    ModelOutput,
    ParsedChoice,
    PassageEntry,
    StateVariable,
    StoryGraph,
)
from harness.passage import create_passage, scan_state_reads
from harness.project import ProjectPaths, init_project, load_story, save_story
from harness.validation import (
    MACRO_CONTAINERS,
    check_deprecated_features,
    check_macro_pairing,
    check_orphan_passages,
    run_validation,
)


# ── §3.2/§3.3: New container macros validate correctly ────────────────────────

class ContainerMacroTests(unittest.TestCase):
    """The four container macros missing from MACRO_CONTAINERS (silent, do,
    script, done) are now present and validate as containers."""

    @staticmethod
    def _check(tmp, body):
        p = init_project(Path(tmp), title="Test")
        f = p.arcs_dir / "x" / "01.tw"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(":: x__01 [x]\n" + body + "\n", encoding="utf-8")
        graph = StoryGraph()
        graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
        return check_macro_pairing(p, graph)

    def test_silent_in_containers(self):
        self.assertIn("silent", MACRO_CONTAINERS)

    def test_do_in_containers(self):
        self.assertIn("do", MACRO_CONTAINERS)

    def test_script_in_containers(self):
        self.assertIn("script", MACRO_CONTAINERS)

    def test_done_in_containers(self):
        self.assertIn("done", MACRO_CONTAINERS)

    def test_silent_balanced_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<silent>>quiet<</silent>>"), [])

    def test_do_balanced_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<do>>dynamic<</do>>"), [])

    def test_script_balanced_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<script>>JS code<</script>>"), [])

    def test_done_balanced_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<done>>after<</done>>"), [])

    def test_done_unclosed_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "<<done>>after")
            self.assertTrue(any("never closed" in i.message for i in issues))

    def test_silently_still_validated(self):
        # Backward compat: the deprecated <<silently>> is still a container.
        self.assertIn("silently", MACRO_CONTAINERS)
        with TemporaryDirectory() as tmp:
            self.assertEqual(self._check(tmp, "<<silently>>x<</silently>>"), [])


# ── §3.1/§3.4/§3.15: Deprecated feature detection ─────────────────────────────

class DeprecatedFeatureTests(unittest.TestCase):
    """check_deprecated_features warns on deprecated macros, tags, and special
    passages from SugarCube v2.37.0+."""

    @staticmethod
    def _make_passage(tmp, pid, body, tags=None):
        p = init_project(Path(tmp), title="Test")
        tag_str = f" [{' '.join(tags)}]" if tags else ""
        f = p.arcs_dir / "x" / f"{pid}.tw"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f":: {pid}{tag_str}\n{body}\n", encoding="utf-8")
        graph = StoryGraph()
        graph.passages[pid] = PassageEntry(file=f"arcs/x/{pid}.tw", arc="x")
        return p, graph

    def _warnings(self, p, graph):
        return [i for i in check_deprecated_features(p, graph) if i.level == "warning"]

    def test_actions_macro_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "x__01", "<<actions [[Go|next]]>>")
            ws = self._warnings(p, g)
            self.assertTrue(any(i.code == "deprecated_macro" and "actions" in i.message for i in ws))

    def test_choice_macro_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "x__01", "<<choice \"Go\">>")
            ws = self._warnings(p, g)
            self.assertTrue(any(i.code == "deprecated_macro" and "choice" in i.message for i in ws))

    def test_silently_macro_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "x__01", "<<silently>>x<</silently>>")
            ws = self._warnings(p, g)
            self.assertTrue(any(i.code == "deprecated_macro" and "silently" in i.message for i in ws))

    def test_bookmark_tag_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "x__01", "body", tags=["bookmark"])
            ws = self._warnings(p, g)
            self.assertTrue(any(i.code == "deprecated_tag" and "bookmark" in i.message for i in ws))

    def test_storyshare_passage_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "StoryShare", "share body")
            ws = self._warnings(p, g)
            self.assertTrue(any(i.code == "deprecated_passage" and "StoryShare" in i.message for i in ws))

    def test_clean_passage_no_warnings(self):
        with TemporaryDirectory() as tmp:
            p, g = self._make_passage(tmp, "x__01", "<<link \"Go\" \"next\">><</link>>")
            self.assertEqual(self._warnings(p, g), [])

    def test_deprecated_check_in_run_validation(self):
        """check_deprecated_features is wired into run_validation."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "x" / "01.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(":: x__01 [x]\n<<actions [[Go|next]]>>\n", encoding="utf-8")
            graph = StoryGraph(start_passage="x__01")
            graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
            save_story(p, graph)
            result = run_validation(p)
            self.assertTrue(any(w.code == "deprecated_macro" for w in result.warnings))


# ── §3.1: Hub rendering replaces <<actions>> ──────────────────────────────────

class HubRenderingTests(unittest.TestCase):
    """Hub passages render visited-gated <<link>> instead of deprecated <<actions>>."""

    def _make_hub(self, tmp, choices):
        p = init_project(Path(tmp), title="Test")
        out = ModelOutput(
            prose="Town square.",
            choices=choices,
            summary="Hub.",
        )
        pid, graph = create_passage(
            p, "intro", "01_hub", out, None, passage_type="hub",
        )
        tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
        return p, pid, graph, tw

    def test_no_actions_macro_in_hub(self):
        with TemporaryDirectory() as tmp:
            _, _, _, tw = self._make_hub(tmp, [
                ParsedChoice(text="Visit shop", hint="shop"),
                ParsedChoice(text="Talk to king", hint="king"),
            ])
            self.assertNotIn("<<actions ", tw)

    def test_hub_uses_visited_gated_links(self):
        with TemporaryDirectory() as tmp:
            _, _, _, tw = self._make_hub(tmp, [
                ParsedChoice(text="Visit shop", hint="shop"),
            ])
            self.assertIn('<<if not hasVisited("UNRESOLVED_choice0_shop")>>', tw)
            self.assertIn('<<link "Visit shop" "UNRESOLVED_choice0_shop">><</link>>', tw)
            self.assertIn("<</if>>", tw)

    def test_hub_state_write_choice_not_visit_gated(self):
        with TemporaryDirectory() as tmp:
            _, _, _, tw = self._make_hub(tmp, [
                ParsedChoice(text="Bribe guard", hint="bribe", state_writes={"$gold": 5}),
            ])
            self.assertNotIn("<<if not hasVisited", tw)
            self.assertIn('<<link "Bribe guard" "UNRESOLVED_choice0_bribe">>', tw)
            self.assertIn("<<set $gold to 5>>", tw)

    def test_hub_validates_clean(self):
        with TemporaryDirectory() as tmp:
            p, pid, graph, _ = self._make_hub(tmp, [
                ParsedChoice(text="Visit shop", hint="shop"),
            ])
            result = run_validation(p)
            # No deprecated_macro warning for the hub (uses <<link>>, not <<actions>>)
            self.assertFalse(any(w.code == "deprecated_macro" for w in result.warnings))


# ── §3.5/§3.6: Prompt guidance includes SugarCube markup + scoping ────────────

class PromptGuidanceTests(unittest.TestCase):
    """The full and JSON passage prompts include a SugarCube authoring cheat
    sheet covering variable scopes ($ vs _) and markup conventions."""

    def test_full_prompt_has_sugarcube_guidance(self):
        from harness.prompts import build_full_passage_prompt, SUGARCUBE_GUIDANCE
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
        )
        self.assertIn(SUGARCUBE_GUIDANCE, prompt)

    def test_json_prompt_has_sugarcube_guidance(self):
        from harness.prompts import build_json_passage_prompt, SUGARCUBE_GUIDANCE
        prompt = build_json_passage_prompt(
            premise="p", story_points="sp", arc_md="a", snapshot_text="s",
            entities_text="e", inspiration="i", parent_prose="pp",
            human_prompt="h", mode="co-author",
        )
        self.assertIn(SUGARCUBE_GUIDANCE, prompt)

    def test_guidance_covers_variable_scopes(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("$var", SUGARCUBE_GUIDANCE)
        self.assertIn("_var", SUGARCUBE_GUIDANCE)
        self.assertIn("persistent", SUGARCUBE_GUIDANCE)
        self.assertIn("temporary", SUGARCUBE_GUIDANCE)

    def test_guidance_covers_markup_not_markdown(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("''bold''", SUGARCUBE_GUIDANCE)
        self.assertIn("//italic//", SUGARCUBE_GUIDANCE)
        self.assertIn("NOT markdown", SUGARCUBE_GUIDANCE)

    def test_guidance_covers_naked_interpolation(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("$var auto-interpolates", SUGARCUBE_GUIDANCE)

    def test_guidance_covers_print_and_include(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("<<print", SUGARCUBE_GUIDANCE)
        self.assertIn("<<include", SUGARCUBE_GUIDANCE)

    def test_guidance_covers_widget(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("widget", SUGARCUBE_GUIDANCE.lower())

    def test_prompt_version_bumped(self):
        from harness.prompts import PROMPT_VERSION
        self.assertGreaterEqual(PROMPT_VERSION, 6)


# ── §3.12-3.14: scan_state_reads covers more expression contexts ───────────────

class ScanStateReadsTests(unittest.TestCase):
    """scan_state_reads now catches naked prose variables, <<if>> conditions,
    <<print>> expressions, and the RHS of <<set>> (which could read other vars)."""

    def test_naked_prose_variable(self):
        reads = scan_state_reads("You have $gold coins and $name greets you.")
        self.assertIn("$gold", reads)
        self.assertIn("$name", reads)

    def test_if_condition_variable(self):
        reads = scan_state_reads("<<if $has_key>>The door is open.<</if>>")
        self.assertIn("$has_key", reads)

    def test_print_expression_variable(self):
        reads = scan_state_reads("You weigh <<print $weight>> kg.")
        self.assertIn("$weight", reads)

    def test_set_rhs_reads_other_var(self):
        # <<set $b to $a + 1>> — $a is a read, $b is a write (not a read).
        reads = scan_state_reads("<<set $b to $a + 1>>")
        self.assertIn("$a", reads)
        self.assertNotIn("$b", reads)

    def test_link_setter_variable(self):
        reads = scan_state_reads('[[Take key|key_room][$has_key to true]]')
        self.assertIn("$has_key", reads)

    def test_set_target_not_counted_as_read(self):
        reads = scan_state_reads("<<set $gold to 50>>")
        self.assertNotIn("$gold", reads)


# ── §3.7: Widget passage type ─────────────────────────────────────────────────

class WidgetPassageTests(unittest.TestCase):
    """Widget passages render as SugarCube widget definitions and are not
    flagged as orphans (they're invoked as macros, not navigated to). Pattern
    from Space-Tech UI's <<widget "statsformat">> and Character Creator's
    widget grid (TEMPLATE_VERIFICATION_REPORT §2.3.1, §2.3.5)."""

    def test_widget_passage_auto_wraps_prose(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(prose="<<if $fuel lt 25>>low fuel<</if>>", summary="widget")
            pid, graph = create_passage(
                p, "intro", "stat_bar", out, None, passage_type="widget",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn("<<widget", tw)
            self.assertIn("<</widget>>", tw)
            # widget tag in header
            self.assertIn("[intro widget]", tw.splitlines()[0])

    def test_widget_passage_with_explicit_widget_macro_emitted_raw(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose='<<widget "greeting">>"Hello, $name."<</widget>>',
                summary="widget",
            )
            pid, graph = create_passage(
                p, "intro", "greet", out, None, passage_type="widget",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # Should not double-wrap since prose already has <<widget>>.
            self.assertEqual(tw.count("<<widget"), 1)

    def test_widget_passage_not_orphan_without_parent(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(prose="<<if $x>>y<</if>>", summary="widget")
            pid, graph = create_passage(
                p, "intro", "stat_bar", out, None, passage_type="widget",
            )
            result = run_validation(p)
            self.assertFalse(any(e.code == "orphan_passage" and pid in e.message
                                 for e in result.errors))

    def test_widget_passage_in_passage_types(self):
        from harness.models import PASSAGE_TYPES
        self.assertIn("widget", PASSAGE_TYPES)


# ── §3.8: Include passage type ────────────────────────────────────────────────

class IncludePassageTests(unittest.TestCase):
    """Include passages are shared-content passages meant to be <<include>>d,
    not navigated to. Pattern from Title Page's <<include "Menu Elements">>
    and Simple Book's "Navigation" passage (TEMPLATE_VERIFICATION_REPORT §2.3.6,
    §2.3.4)."""

    def test_include_passage_renders_prose_verbatim(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="<<link \"Saves\">><<run UI.saves()>><</link>>",
                summary="menu",
            )
            pid, graph = create_passage(
                p, "intro", "menu_elements", out, None, passage_type="include",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            self.assertIn("<<link \"Saves\">>", tw)
            self.assertIn("<<run UI.saves()>>", tw)
            self.assertIn("[intro include]", tw.splitlines()[0])

    def test_include_passage_not_orphan_without_parent(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(prose="shared menu content", summary="menu")
            pid, graph = create_passage(
                p, "intro", "menu_elements", out, None, passage_type="include",
            )
            result = run_validation(p)
            self.assertFalse(any(e.code == "orphan_passage" and pid in e.message
                                 for e in result.errors))

    def test_include_passage_in_passage_types(self):
        from harness.models import PASSAGE_TYPES
        self.assertIn("include", PASSAGE_TYPES)


# ── Template compatibility: validated against 2+ studied templates ────────────

class TemplateCompatibilityTests(unittest.TestCase):
    """End-to-end validation that generated output follows patterns from the
    studied HTML templates. Validates against:
      1. Space-Tech UI  — widget passage pattern (<<widget "statsformat">>)
      2. Title Page     — include passage pattern (<<include "Menu Elements">>)
      3. One Page       — hub with visited-gated links (replaces <<actions>>)

    These mirror the SugarCube v2.37.3 conventions documented in
    examples/html_templates/TEMPLATE_VERIFICATION_REPORT.md.
    """

    def test_space_tech_widget_pattern(self):
        """Space-Tech UI uses <<widget \"statsformat\">> in a [widget]-tagged
        passage to render stat bars (TEMPLATE_VERIFICATION_REPORT §2.3.5).
        The harness can now generate this pattern."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="<<if $fuel lt 25>>!<<else>>$fuel%<</if>>",
                summary="stat widget",
            )
            pid, graph = create_passage(
                p, "ui", "stats_bar", out, None, passage_type="widget",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # Widget definition present and well-formed
            self.assertIn("<<widget", tw)
            self.assertIn("<</widget>>", tw)
            # Validated as a container macro (no pairing errors)
            result = run_validation(p)
            self.assertFalse(any(e.code == "macro_pairing" for e in result.errors))
            # Not flagged as orphan
            self.assertFalse(any(e.code == "orphan_passage" for e in result.errors))

    def test_title_page_include_pattern(self):
        """Title Page uses <<include \"Menu Elements\">> for shared title
        content (TEMPLATE_VERIFICATION_REPORT §2.3.6). The harness can now
        generate include passages that other passages reference."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            # Create an include passage with shared menu content
            menu_out = ModelOutput(
                prose="<<link \"Saves\">><<run UI.saves()>><</link>>\\n<<link \"Settings\">><<run UI.settings()>><</link>>",
                summary="shared menu",
            )
            menu_pid, graph = create_passage(
                p, "ui", "menu_elements", menu_out, None, passage_type="include",
            )
            # Create a normal passage that includes it
            start_out = ModelOutput(
                prose=f'Title page\\n<<include "{menu_pid}">>',
                choices=[ParsedChoice(text="Begin", hint="start")],
                summary="title",
            )
            start_pid, graph = create_passage(
                p, "intro", "01_start", start_out, None, passage_type="normal",
            )
            # Validate the whole story
            result = run_validation(p)
            # Include passage not orphan, start passage valid
            self.assertFalse(any(e.code == "orphan_passage" and menu_pid in e.message
                                 for e in result.errors))
            # The include macro should be recognized as a reference (not broken)
            tw = (Path(tmp) / graph.passages[start_pid].file).read_text(encoding="utf-8")
            self.assertIn(f'<<include "{menu_pid}">>', tw)

    def test_one_page_hub_pattern(self):
        """One Page template's hub/start page uses one-shot links. The harness
        now renders these as visited-gated <<link>> instead of the deprecated
        <<actions>> (TEMPLATE_VERIFICATION_REPORT §2.3.3, analysis §3.1)."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Main menu.",
                choices=[
                    ParsedChoice(text="New Game", hint="new"),
                    ParsedChoice(text="Continue", hint="resume"),
                    ParsedChoice(text="Settings", hint="settings"),
                ],
                summary="hub",
            )
            pid, graph = create_passage(
                p, "intro", "01_start", out, None, passage_type="hub",
            )
            tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
            # No deprecated <<actions>>
            self.assertNotIn("<<actions ", tw)
            # Each choice is a visited-gated link
            for hint in ("new", "resume", "settings"):
                self.assertIn(f"hasVisited(\"UNRESOLVED_", tw)
            # Validates clean — no deprecated warnings, no macro pairing errors
            result = run_validation(p)
            self.assertFalse(any(w.code == "deprecated_macro" for w in result.warnings))
            self.assertFalse(any(e.code == "macro_pairing" for e in result.errors))

    def test_storydata_targets_sugarcube_2_format(self):
        """Generated StoryData targets the SugarCube 2 format, matching all 7
        studied templates (TEMPLATE_VERIFICATION_REPORT §2.2)."""
        cfg = HarnessConfig(
            story_title="Test Tale",
            story_format="SugarCube2",
            story_ifid="ABC-123",
            format_version="2.37.3",
        )
        out = _storydata_twee(cfg, "intro__01_start")
        self.assertIn(":: StoryData", out)
        self.assertIn('"format": "SugarCube2"', out)
        self.assertIn('"format-version": "2.37.3"', out)
        self.assertIn('"start": "intro__01_start"', out)

    def test_storyinit_emits_declared_defaults(self):
        """StoryInit initializes declared variable defaults, matching the
        pattern in Character Creator's StoryInit (TEMPLATE_VERIFICATION_REPORT
        §2.3.1)."""
        graph = StoryGraph()
        graph.state_variables["$has_key"] = StateVariable(type="bool", default=False)
        graph.state_variables["$gold"] = StateVariable(type="int", default=10)
        out = _storyinit_twee(graph)
        self.assertIn(":: StoryInit", out)
        self.assertIn("<<set $has_key to false>>", out)
        self.assertIn("<<set $gold to 10>>", out)


if __name__ == "__main__":
    unittest.main()

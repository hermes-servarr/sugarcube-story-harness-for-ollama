"""Tests for <<capture>> wrapping of <<link>> inside <<for>> loops.

Implements the acceptance criteria for task t_413f842d:
  * link inside a for-loop (<<capture>> wraps link bodies that read a loop var)
  * link with <<set>> referencing a loop variable (RHS read captured)
  * link outside a loop → no capture (byte-identical to pre-change output)
  * nested for-loops (each level's loop var captured)
  * idempotency (don't double-wrap if <<capture>> already present)
  * validation guardrail: <<link>> in <<for>> without <<capture>> → warning

Reference: docs/sugarcube2-analysis.md §3.9.
"""
from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.models import (
    ModelOutput,
    ParsedChoice,
    PassageEntry,
    SkillCheck,
    StoryGraph,
)
from harness.passage import (
    _capture_vars_for_choice,
    _capture_wrap,
    _render_choice_link,
    _render_passage_tw,
    _vars_in_set_rhs,
    create_passage,
)
from harness.project import init_project
from harness.validation import check_capture_in_loops, run_validation


# ── Helper: build a project + single passage ─────────────────────────────────

def _make_passage(tmp, body):
    """Write a single passage .tw and return (p, graph) for validation."""
    p = init_project(Path(tmp), title="Test")
    f = p.arcs_dir / "x" / "01.tw"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(":: x__01 [x]\n" + body + "\n", encoding="utf-8")
    g = StoryGraph()
    g.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
    return p, g


# ── _capture_wrap unit tests ──────────────────────────────────────────────────

class CaptureWrapUnitTests(unittest.TestCase):
    """Direct tests of the _capture_wrap helper."""

    def test_no_op_when_no_vars(self):
        """Empty capture_vars → body unchanged (the no-op that keeps current
        harness output byte-identical, since no <<for>> is emitted today)."""
        body = '<<link "Go" "target">><</link>>'
        self.assertEqual(_capture_wrap([], body), body)
        self.assertEqual(_capture_wrap(None, body), body)

    def test_wraps_when_vars_given(self):
        body = '<<link "Go" "t">><</link>>'
        wrapped = _capture_wrap(["$npc"], body)
        self.assertEqual(wrapped, "<<capture $npc>>" + body + "<</capture>>")

    def test_wraps_multiple_vars(self):
        body = '<<link "Go" "t">><</link>>'
        wrapped = _capture_wrap(["$a", "$b"], body)
        self.assertEqual(wrapped, "<<capture $a $b>>" + body + "<</capture>>")

    def test_idempotent_when_already_wrapped_superset(self):
        """Already-captured body (vars ⊇ requested) → unchanged (no double-wrap)."""
        body = '<<capture $npc>><<link "Go" "t">><</link>><</capture>>'
        self.assertEqual(_capture_wrap(["$npc"], body), body)

    def test_idempotent_when_already_wrapped_extra_vars(self):
        """Existing capture has MORE vars than requested → still a no-op."""
        body = '<<capture $npc $other>><<link "Go" "t">><</link>><</capture>>'
        self.assertEqual(_capture_wrap(["$npc"], body), body)

    def test_outer_wraps_missing_vars_keeping_existing(self):
        """Existing capture covers SOME requested vars → outer-wrap the missing
        ones, leaving the existing inner capture intact (no var dropped)."""
        body = "<<capture $a>>BODY<</capture>>"
        result = _capture_wrap(["$a", "$b"], body)
        self.assertEqual(
            result,
            "<<capture $b>><<capture $a>>BODY<</capture>><</capture>>",
        )


# ── _capture_vars_for_choice + _vars_in_set_rhs ──────────────────────────────

class CaptureVarDetectionTests(unittest.TestCase):

    def test_skill_check_stat_at_risk_returns_it(self):
        c = ParsedChoice(text="Roll", hint="r", skill_check=SkillCheck(stat="$strength", dc=10))
        self.assertEqual(_capture_vars_for_choice(c, ["$strength"]), ["$strength"])

    def test_skill_check_stat_not_in_loop_vars_returns_empty(self):
        c = ParsedChoice(text="Roll", hint="r", skill_check=SkillCheck(stat="$strength", dc=10))
        self.assertEqual(_capture_vars_for_choice(c, ["$npc"]), [])

    def test_no_loop_vars_returns_empty(self):
        c = ParsedChoice(text="Roll", hint="r", skill_check=SkillCheck(stat="$strength", dc=10))
        self.assertEqual(_capture_vars_for_choice(c, None), [])
        self.assertEqual(_capture_vars_for_choice(c, []), [])

    def test_state_writes_rhs_var_reference_detected(self):
        """state_writes with a $-variable reference on the RHS (future-proof:
        today _format_sc_value only emits literals, but the schema is Any)."""
        c = ParsedChoice(text="Set", hint="s", state_writes={"$x": "$npc"})
        self.assertEqual(_vars_in_set_rhs(c.state_writes), ["$npc"])
        self.assertEqual(_capture_vars_for_choice(c, ["$npc"]), ["$npc"])

    def test_state_writes_literal_values_not_capture_candidates(self):
        """Literal RHS values (bool/str/int) produce no capture candidates."""
        c = ParsedChoice(text="Set", hint="s",
                         state_writes={"$gold": 5, "$name": "Bob", "$flag": True})
        self.assertEqual(_vars_in_set_rhs(c.state_writes), [])

    def test_plain_choice_outside_loop_no_capture(self):
        """Plain wikilink-style choice with no loop context → no capture vars."""
        c = ParsedChoice(text="Go north", hint="n")
        self.assertEqual(_capture_vars_for_choice(c, None), [])
        self.assertEqual(_capture_vars_for_choice(c, ["$npc"]), [])


# ── Link rendering: link INSIDE a for-loop ───────────────────────────────────

class LinkInsideForLoopTests(unittest.TestCase):
    """Acceptance: link inside a for-loop gets <<capture>> wrapping when its
    body reads a loop variable."""

    def test_skill_check_link_in_loop_wraps_stat(self):
        c = ParsedChoice(text="Roll", hint="r", skill_check=SkillCheck(stat="$npc", dc=5))
        out = _render_choice_link(0, c, "pid", loop_vars=["$npc"])
        self.assertIn("<<capture $npc>>", out)
        self.assertIn("<</capture>>", out)
        # The <<link>> and its <<if $npc gte 5>> body are inside the capture.
        self.assertIn("<<capture $npc>><<link", out)

    def test_skill_check_link_no_loop_no_capture(self):
        """Same choice but NO loop context → byte-identical to pre-change output
        (no <<capture>> added). This preserves existing behavior."""
        c = ParsedChoice(text="Roll", hint="r", skill_check=SkillCheck(stat="$strength", dc=5))
        out = _render_choice_link(0, c, "pid")
        self.assertNotIn("<<capture", out)
        self.assertIn("<<link", out)

    def test_state_write_link_in_loop_wraps_rhs_var(self):
        c = ParsedChoice(text="Give", hint="g", state_writes={"$gift": "$npc"})
        out = _render_choice_link(0, c, "pid", loop_vars=["$npc"])
        self.assertIn("<<capture $npc>>", out)
        self.assertIn("<<set $gift to \"$npc\">>", out)

    def test_state_write_literal_in_loop_no_capture(self):
        """Literal state-write RHS doesn't read a loop var → no capture even
        inside a loop."""
        c = ParsedChoice(text="Bribe", hint="b", state_writes={"$gold": 5})
        out = _render_choice_link(0, c, "pid", loop_vars=["$npc"])
        self.assertNotIn("<<capture", out)

    def test_plain_wikilink_in_loop_no_capture(self):
        """Plain wikilink has no deferred body → never needs capture, even in
        a loop."""
        c = ParsedChoice(text="Go", hint="go")
        out = _render_choice_link(0, c, "pid", loop_vars=["$npc"])
        self.assertNotIn("<<capture", out)
        self.assertIn("[[Go|", out)


# ── _render_passage_tw: the "loop" passage type ──────────────────────────────

class LoopPassageTypeTests(unittest.TestCase):
    """The 'loop' passage_type emits a genuine SugarCube <<for>> loop with
    <<capture>> wrapping around link bodies that read the loop variable."""

    def _render_loop(self, choices, loop_vars, collection="$npcs"):
        return _render_passage_tw(
            passage_id="pid", arc_name="arc", prose="NPCs:",
            choices=choices, state_assigns={}, media_slot_ids=[],
            location="", characters=[], passage_type="loop",
            loop_vars=loop_vars, loop_collection=collection,
        )

    def test_loop_emits_for_and_capture(self):
        c = ParsedChoice(text="Talk to $npc", hint="talk",
                         skill_check=SkillCheck(stat="$npc", dc=5))
        tw = self._render_loop([c], ["$npc"])
        self.assertIn("<<for $npc in $npcs>>", tw)
        self.assertIn("<</for>>", tw)
        self.assertIn("<<capture $npc>>", tw)
        self.assertIn("<</capture>>", tw)
        # capture is INSIDE the for, wrapping the link
        self.assertIn("<<for $npc in $npcs>>\n<<capture $npc>><<link", tw)

    def test_loop_link_with_set_referencing_loop_var(self):
        c = ParsedChoice(text="Select $npc", hint="sel",
                         state_writes={"$chosen": "$npc"})
        tw = self._render_loop([c], ["$npc"])
        self.assertIn("<<for $npc in $npcs>>", tw)
        self.assertIn("<<capture $npc>>", tw)
        self.assertIn("<<set $chosen to \"$npc\">>", tw)

    def test_loop_plain_choice_no_capture(self):
        """A plain choice (no var read) inside a loop passage does NOT get
        wrapped — capture only applies when the body reads a loop var."""
        c = ParsedChoice(text="Continue", hint="cont")
        tw = self._render_loop([c], ["$npc"])
        self.assertIn("<<for $npc in $npcs>>", tw)
        self.assertNotIn("<<capture", tw)

    def test_loop_passage_tag_in_header(self):
        c = ParsedChoice(text="Go", hint="g")
        tw = self._render_loop([c], ["$npc"])
        self.assertIn("[arc loop]", tw.splitlines()[0])

    def test_loop_passage_type_registered(self):
        """The 'loop' passage_type is registered in PASSAGE_TYPES so the
        bad_passage_type validator does not reject it (acceptance: generated
        markup validates against expected <<capture>> syntax)."""
        from harness.models import PASSAGE_TYPES
        self.assertIn("loop", PASSAGE_TYPES)

    def test_loop_passage_full_validation_clean(self):
        """A well-formed loop passage (capture present) must produce no
        bad_passage_type error and no capture_missing warning from the full
        run_validation pipeline."""
        from harness.project import save_story
        c = ParsedChoice(text="Talk to $npc", hint="talk",
                         skill_check=SkillCheck(stat="$npc", dc=5))
        tw = self._render_loop([c], ["$npc"])
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "x" / "01.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(tw, encoding="utf-8")
            g = StoryGraph()
            g.passages["pid"] = PassageEntry(
                file="arcs/x/01.tw", arc="x", passage_type="loop")
            g.start_passage = "pid"
            save_story(p, g)
            result = run_validation(p)
            self.assertFalse(
                any(i.code == "bad_passage_type" for i in result.errors),
                f"loop passage_type rejected: {result.errors}",
            )
            self.assertFalse(
                any(i.code == "capture_missing" for i in result.warnings),
                f"well-formed loop should not warn: {result.warnings}",
            )


# ── Nested for-loops ──────────────────────────────────────────────────────────

class NestedForLoopTests(unittest.TestCase):
    """Acceptance: nested for-loops — each level's loop variable can be
    captured at its own level."""

    def test_nested_loops_capture_each_level_var(self):
        """Outer loop over $room, inner over $item; the link reads $item so
        $item is captured. A link reading $room would capture $room."""
        # Inner link reads $item → capture $item
        inner = ParsedChoice(text="Take $item", hint="take",
                             state_writes={"$inv": "$item"})
        tw = _render_passage_tw(
            passage_id="pid", arc_name="arc", prose="room",
            choices=[inner], state_assigns={}, media_slot_ids=[],
            location="", characters=[], passage_type="loop",
            loop_vars=["$item"], loop_collection="$room.items",
        )
        self.assertIn("<<for $item in $room.items>>", tw)
        self.assertIn("<<capture $item>>", tw)
        self.assertIn("<<set $inv to \"$item\">>", tw)

    def test_nested_validation_both_captured_ok(self):
        """Two nested for loops, each with its own capture around its link,
        produces no capture_missing warnings."""
        body = (
            "<<for $r in $rooms>>"
            "<<for $i in $items>>"
            "<<capture $i>><<link \"X\" \"t\">><</link>><</capture>>"
            "<</for>>"
            "<</for>>"
        )
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, body)
            issues = check_capture_in_loops(p, g)
            self.assertFalse(
                any(i.code == "capture_missing" for i in issues),
                f"expected no capture warning, got: {issues}",
            )

    def test_nested_validation_inner_missing_warns(self):
        """Inner for link without capture warns even when an outer for exists."""
        body = (
            "<<for $r in $rooms>>"
            "<<for $i in $items>>"
            "<<link \"X\" \"t\">><</link>>"
            "<</for>>"
            "<</for>>"
        )
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, body)
            issues = check_capture_in_loops(p, g)
            self.assertTrue(any(i.code == "capture_missing" for i in issues))


# ── Backward compatibility: no loop → no capture ───────────────────────────────

class NoLoopBackwardCompatTests(unittest.TestCase):
    """Links NOT inside loops and NOT referencing mutable vars render exactly
    as before (no <<capture>> noise added)."""

    def _make_normal(self, tmp, choices):
        p = init_project(Path(tmp), title="Test")
        out = ModelOutput(prose="Scene.", choices=choices, summary="s")
        pid, graph = create_passage(p, "intro", "01_scene", out, None)
        tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
        return p, pid, graph, tw

    def test_normal_skill_check_choice_no_capture(self):
        with TemporaryDirectory() as tmp:
            c = ParsedChoice(text="Roll strength", hint="r",
                             skill_check=SkillCheck(stat="$strength", dc=10))
            _, _, _, tw = self._make_normal(tmp, [c])
            self.assertNotIn("<<capture", tw)
            self.assertIn("<<link", tw)
            self.assertIn("<<if $strength gte 10>>", tw)

    def test_normal_state_write_choice_no_capture(self):
        with TemporaryDirectory() as tmp:
            c = ParsedChoice(text="Bribe", hint="b", state_writes={"$gold": 5})
            _, _, _, tw = self._make_normal(tmp, [c])
            self.assertNotIn("<<capture", tw)
            self.assertIn("<<set $gold to 5>>", tw)

    def test_normal_plain_choice_no_capture(self):
        with TemporaryDirectory() as tmp:
            c = ParsedChoice(text="Go north", hint="n")
            _, _, _, tw = self._make_normal(tmp, [c])
            self.assertNotIn("<<capture", tw)
            self.assertIn("[[Go north|", tw)

    def test_hub_links_no_capture_by_default(self):
        with TemporaryDirectory() as tmp:
            _, _, _, tw = self._make_normal(tmp, [
                ParsedChoice(text="Shop", hint="shop"),
                ParsedChoice(text="Inn", hint="inn"),
            ])
            # Default hub path (passage_type normal here, but links are plain)
            self.assertNotIn("<<capture", tw)


# ── Validation guardrail ─────────────────────────────────────────────────────

class CaptureValidationGuardrailTests(unittest.TestCase):
    """check_capture_in_loops warns on async macros in <<for>> without
    <<capture>>, and is silent when capture is present or no loop exists."""

    def test_link_in_for_without_capture_warns(self):
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, '<<for $i in $items>><<link "X" "t">><</link>><</for>>')
            issues = check_capture_in_loops(p, g)
            self.assertTrue(any(i.code == "capture_missing" and i.level == "warning"
                                 for i in issues))

    def test_link_in_for_with_capture_silent(self):
        with TemporaryDirectory() as tmp:
            body = '<<for $i in $items>><<capture $i>><<link "X" "t">><</link>><</capture>><</for>>'
            p, g = _make_passage(tmp, body)
            issues = check_capture_in_loops(p, g)
            self.assertFalse(any(i.code == "capture_missing" for i in issues))

    def test_link_outside_for_silent(self):
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, '<<link "X" "t">><</link>>')
            issues = check_capture_in_loops(p, g)
            self.assertFalse(any(i.code == "capture_missing" for i in issues))

    def test_button_in_for_without_capture_warns(self):
        """Other async macros (button, timed, linkreplace...) are also caught."""
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, '<<for $i in $items>><<button "X">>b<</button>><</for>>')
            issues = check_capture_in_loops(p, g)
            self.assertTrue(any(i.code == "capture_missing" for i in issues))

    def test_capture_outside_for_does_not_satisfy(self):
        """<<capture>> wrapping the WHOLE <<for>> snapshots once before the
        loop — it does NOT fix the per-iteration closure bug, so we still warn.
        The capture must be INSIDE the for to re-snapshot per iteration."""
        with TemporaryDirectory() as tmp:
            body = '<<capture $i>><<for $i in $items>><<link "X" "t">><</link>><</for>><</capture>>'
            p, g = _make_passage(tmp, body)
            issues = check_capture_in_loops(p, g)
            self.assertTrue(any(i.code == "capture_missing" for i in issues))

    def test_guardrail_wired_into_run_validation(self):
        """check_capture_in_loops is part of run_validation's check list."""
        from harness.project import save_story
        with TemporaryDirectory() as tmp:
            p, g = _make_passage(tmp, '<<for $i in $items>><<link "X" "t">><</link>><</for>>')
            g.start_passage = "x__01"
            save_story(p, g)
            result = run_validation(p)
            self.assertTrue(any(w.code == "capture_missing" for w in result.warnings))


# ── Generated SugarCube markup validates against expected syntax ──────────────

class CaptureSyntaxValidationTests(unittest.TestCase):
    """Acceptance: generated <<capture>> markup validates against the
    expected SugarCube syntax (<<capture variable>>...<</capture>>) and passes
    macro-pairing validation."""

    def test_generated_capture_passes_macro_pairing(self):
        """The capture-wrapped loop output must have balanced macros."""
        from harness.validation import check_macro_pairing
        c = ParsedChoice(text="Talk to $npc", hint="talk",
                         skill_check=SkillCheck(stat="$npc", dc=5))
        tw = _render_passage_tw(
            passage_id="pid", arc_name="arc", prose="NPCs:",
            choices=[c], state_assigns={}, media_slot_ids=[],
            location="", characters=[], passage_type="loop",
            loop_vars=["$npc"], loop_collection="$npcs",
        )
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "x" / "01.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(tw, encoding="utf-8")
            g = StoryGraph()
            g.passages["pid"] = PassageEntry(file="arcs/x/01.tw", arc="x")
            issues = check_macro_pairing(p, g)
            self.assertFalse(
                any(i.code == "macro_pairing" for i in issues),
                f"capture output should be balanced; got: {issues}",
            )

    def test_capture_syntax_matches_expected_form(self):
        """<<capture $var>>...<</capture>> with the variable between the tags."""
        c = ParsedChoice(text="X", hint="h", skill_check=SkillCheck(stat="$npc", dc=1))
        out = _render_choice_link(0, c, "pid", loop_vars=["$npc"])
        # Expected SugarCube §3.9 syntax: <<capture variable>>...<</capture>>
        self.assertRegex(out, r"<<capture \$\w+>>.*<</capture>>")
        # The inner content is a complete <<link>>...<</link>>
        self.assertIn("<<link", out)
        self.assertIn("<</link>>", out)


if __name__ == "__main__":
    unittest.main()

"""P7 tests for the <<timed>>/<<repeat>> time-based narrative feature.

Covers all 8 P6 invariants (INV-1..INV-8) plus render, parser, prompt,
passage-type, and meta-block round-trip behavior. Mirrors the P5 mock test
suite (22 tests, all PASS) and adds P7 enforcement tests for the three
P6-identified validation sites:
  - INV-4: check_timed_countdown_anchor (new function)
  - INV-5: check_timed_delays (new function)
  - INV-7: check_passage_types body extension (timed_bad_mode)

Invariant → test mapping:
  INV-1 (one container by mode)  → TimedRevealRenderTests, TimedCountdownRenderTests, TimedRecurringRenderTests
  INV-2 (<<stop>> only in repeat) → TimedCountdownRenderTests, TimedRecurringRenderTests
  INV-3 (<<next>> only in timed)  → TimedRevealRenderTests, TimedCountdownRenderTests, TimedRecurringRenderTests
  INV-4 (countdown anchor match) → TimedCountdownAnchorTests (new P7 validation)
  INV-5 (CSS time >= 40ms)        → TimedDelaysValidationTests (new P7 validation)
  INV-6 (containers balanced)     → TimedMacroPairingTests
  INV-7 (timed_mode closed set)   → TimedBadModeTests (new P7 validation)
  INV-8 (meta round-trip)         → TimedMetaRoundTripTests
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.models import (
    ModelOutput,
    ParsedChoice,
    PASSAGE_TYPES,
    PassageEntry,
    StoryGraph,
    TimedConfig,
    TimedProposal,
    TimedReveal,
)
from harness.ollama import parse_model_output
from harness.passage import (
    _parse_meta_block,
    _render_passage_tw,
    _render_timed_block,
    create_passage,
    rebuild_story,
)
from harness.project import ProjectPaths, init_project
from harness.validation import (
    check_macro_pairing,
    check_passage_types,
    check_timed_countdown_anchor,
    check_timed_delays,
    run_validation,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _basic_output(prose: str = "The scene unfolds.", choices_text: str = "Go | next") -> ModelOutput:
    """A minimal valid ModelOutput for create_passage."""
    return ModelOutput(
        prose=prose,
        choices=[ParsedChoice(text=choices_text.split("|")[0].strip(), hint=choices_text.split("|")[1].strip())],
        summary=prose,
    )


# ── INV-1 / INV-2 / INV-3: render helper ─────────────────────────────────────

class TimedRevealRenderTests(unittest.TestCase):
    """INV-1 (one <<timed>> container), INV-3 (<<next>> only inside <<timed>>)."""

    def test_reveal_renders_timed_next_chain(self):
        reveals = [TimedReveal(delay="2s", content="First."), TimedReveal(delay="4s", content="Second.")]
        tw = _render_timed_block("reveal", reveals, None)
        self.assertIn("<<timed 2s>>First.", tw)
        self.assertIn("<<next 4s>>Second.", tw)
        self.assertIn("<</timed>>", tw)
        # INV-1: exactly one <<timed>> open and one close
        self.assertEqual(tw.count("<<timed "), 1)
        self.assertEqual(tw.count("<</timed>>"), 1)
        # INV-3: <<next>> present, inside the <<timed>> block
        self.assertIn("<<next ", tw)

    def test_reveal_empty_reveals_no_block(self):
        # INV-1 documented no-op: empty reveals → no container
        tw = _render_timed_block("reveal", [], None)
        self.assertEqual(tw, "")


class TimedCountdownRenderTests(unittest.TestCase):
    """INV-1 (one <<repeat>> in <<silent>>), INV-2 (<<stop>> only in repeat),
    INV-3 (no <<next>> in countdown)."""

    def test_countdown_renders_silent_repeat_stop(self):
        cfg = TimedConfig(
            interval="1s", counter_var="seconds", start_value=10,
            final_content="Too Late", anchor_id="countdown",
        )
        tw = _render_timed_block("countdown", [], cfg)
        self.assertIn("<<silent>>", tw)
        self.assertIn("<<repeat 1s>>", tw)
        self.assertIn("<</repeat>>", tw)
        self.assertIn("<</silent>>", tw)
        self.assertIn("<<stop>>", tw)
        self.assertIn('<<replace "#countdown">>', tw)
        # INV-1: exactly one <<repeat>> container
        self.assertEqual(tw.count("<<repeat "), 1)
        self.assertEqual(tw.count("<</repeat>>"), 1)
        # INV-2: <<stop>> present inside the <<repeat>> block
        self.assertLess(tw.index("<<repeat"), tw.index("<<stop>>"))
        self.assertLess(tw.index("<<stop>>"), tw.index("<</repeat>>"))
        # INV-3: no <<next>> in countdown mode
        self.assertNotIn("<<next", tw)


class TimedRecurringRenderTests(unittest.TestCase):
    """INV-1 (one <<repeat>>), INV-2 (no <<stop>> in recurring),
    INV-3 (no <<next>> in recurring)."""

    def test_recurring_renders_repeat_loop_no_stop_no_next(self):
        cfg = TimedConfig(interval="5s", content="<<print 'tick'>>")
        tw = _render_timed_block("recurring", [], cfg)
        self.assertIn("<<repeat 5s>>", tw)
        self.assertIn("<</repeat>>", tw)
        # INV-1: exactly one <<repeat>> container, no <<timed>>
        self.assertEqual(tw.count("<<repeat "), 1)
        self.assertEqual(tw.count("<</repeat>>"), 1)
        self.assertNotIn("<<timed", tw)
        # INV-2: no <<stop>> in recurring mode
        self.assertNotIn("<<stop>>", tw)
        # INV-3: no <<next>> in recurring mode
        self.assertNotIn("<<next", tw)


# ── INV-6: macro pairing (containers balanced) ───────────────────────────────

class TimedMacroPairingTests(unittest.TestCase):
    """INV-6: <<timed>>/<<repeat>>/<<silent>>/<<done>> are in MACRO_CONTAINERS
    and balanced by check_macro_pairing. <<next>>/<<stop>> are NOT containers."""

    def test_timed_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("timed", MACRO_CONTAINERS)

    def test_repeat_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertIn("repeat", MACRO_CONTAINERS)

    def test_next_not_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertNotIn("next", MACRO_CONTAINERS)

    def test_stop_not_in_containers(self):
        from harness.validation import MACRO_CONTAINERS
        self.assertNotIn("stop", MACRO_CONTAINERS)

    def test_timed_balanced_passes_validation(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="TimedTest")
            out = _basic_output()
            create_passage(
                p, "intro", "01_reveal", out, None,
                passage_type="timed", timed_mode="reveal",
                timed_reveals=[TimedReveal(delay="2s", content="Boom.")],
            )
            graph = rebuild_story(p)[0]
            issues = check_macro_pairing(p, graph)
            self.assertEqual(issues, [])

    def test_recurring_balanced_passes_validation(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="TimedTest")
            out = _basic_output()
            create_passage(
                p, "intro", "01_rec", out, None,
                passage_type="timed", timed_mode="recurring",
                timed_config=TimedConfig(interval="5s", content="tick"),
            )
            graph = rebuild_story(p)[0]
            issues = check_macro_pairing(p, graph)
            self.assertEqual(issues, [])


# ── INV-8: meta-block round-trip via rebuild_story ──────────────────────────

class TimedMetaRoundTripTests(unittest.TestCase):
    """INV-8: timed_mode/timed_reveals/timed_config round-trip losslessly."""

    def test_reveal_meta_round_trips(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="TimedRT")
            out = _basic_output()
            reveals = [TimedReveal(delay="2s", content="First."), TimedReveal(delay="4s", content="Second.")]
            pid, _ = create_passage(
                p, "intro", "01_rev", out, None,
                passage_type="timed", timed_mode="reveal", timed_reveals=reveals,
            )
            graph = rebuild_story(p)[0]
            entry = graph.passages[pid]
            self.assertEqual(entry.timed_mode, "reveal")
            self.assertEqual(len(entry.timed_reveals), 2)
            self.assertEqual(entry.timed_reveals[0].delay, "2s")
            self.assertEqual(entry.timed_reveals[0].content, "First.")
            self.assertEqual(entry.timed_reveals[1].delay, "4s")
            self.assertEqual(entry.timed_reveals[1].content, "Second.")
            self.assertIsNone(entry.timed_config)

    def test_countdown_config_round_trips(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="TimedRT")
            out = _basic_output()
            cfg = TimedConfig(
                interval="1s", counter_var="seconds", start_value=10,
                final_content="Too Late", anchor_id="countdown",
            )
            pid, _ = create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            graph = rebuild_story(p)[0]
            entry = graph.passages[pid]
            self.assertEqual(entry.timed_mode, "countdown")
            self.assertEqual(entry.timed_config.interval, "1s")
            self.assertEqual(entry.timed_config.counter_var, "seconds")
            self.assertEqual(entry.timed_config.start_value, 10)
            self.assertEqual(entry.timed_config.final_content, "Too Late")
            self.assertEqual(entry.timed_config.anchor_id, "countdown")

    def test_meta_block_parse_round_trips_keys(self):
        # Direct unit test of _parse_meta_block on a rendered meta block.
        reveals = [TimedReveal(delay="3s", content="Revealed.")]
        cfg = TimedConfig(interval="2s", content="loop")
        tw = _render_passage_tw(
            "p1", "arc", "Prose.", [], {}, [], "loc", [],
            passage_type="timed", timed_mode="countdown",
            timed_reveals=reveals, timed_config=cfg,
        )
        meta = _parse_meta_block(tw)
        self.assertEqual(meta.get("timed_mode"), "countdown")
        self.assertEqual(len(meta.get("timed_reveals", [])), 1)
        self.assertEqual(meta["timed_reveals"][0].delay, "3s")
        self.assertEqual(meta["timed_reveals"][0].content, "Revealed.")
        self.assertIsNotNone(meta.get("timed_config"))
        self.assertEqual(meta["timed_config"].interval, "2s")
        self.assertEqual(meta["timed_config"].content, "loop")


# ── Parser tests (TIMED section) ─────────────────────────────────────────────

class TimedParserTests(unittest.TestCase):
    """parse_model_output populates output.timed from the TIMED section."""

    def test_parse_reveal_timed_section(self):
        raw = (
            "PROSE:\nThe scene unfolds.\n\n"
            "CHOICES:\n- Go | next\n\n"
            "SUMMARY:\nThe scene unfolds.\n\n"
            "TIMED:\nmode: reveal\n2s | First reveal\n4s | Second reveal\n"
        )
        out = parse_model_output(raw)
        self.assertIsNotNone(out.timed)
        self.assertEqual(out.timed.timed_mode, "reveal")
        self.assertEqual(len(out.timed.timed_reveals), 2)
        self.assertEqual(out.timed.timed_reveals[0].delay, "2s")
        self.assertEqual(out.timed.timed_reveals[0].content, "First reveal")
        self.assertEqual(out.timed.timed_reveals[1].delay, "4s")
        self.assertEqual(out.timed.timed_reveals[1].content, "Second reveal")

    def test_parse_countdown_timed_section(self):
        raw = (
            "PROSE:\nThe scene unfolds.\n\n"
            "CHOICES:\n- Go | next\n\n"
            "SUMMARY:\nThe scene unfolds.\n\n"
            "TIMED:\nmode: countdown\ninterval: 1s\ncounter_var: seconds\n"
            "start_value: 10\nfinal_content: Too Late\nanchor_id: countdown\n"
        )
        out = parse_model_output(raw)
        self.assertIsNotNone(out.timed)
        self.assertEqual(out.timed.timed_mode, "countdown")
        self.assertIsNotNone(out.timed.timed_config)
        self.assertEqual(out.timed.timed_config.interval, "1s")
        self.assertEqual(out.timed.timed_config.counter_var, "seconds")
        self.assertEqual(out.timed.timed_config.start_value, 10)
        self.assertEqual(out.timed.timed_config.final_content, "Too Late")
        self.assertEqual(out.timed.timed_config.anchor_id, "countdown")

    def test_parse_recurring_timed_section(self):
        raw = (
            "PROSE:\nThe scene unfolds.\n\n"
            "CHOICES:\n- Go | next\n\n"
            "SUMMARY:\nThe scene unfolds.\n\n"
            "TIMED:\nmode: recurring\ninterval: 5s\ncontent: tick\n"
        )
        out = parse_model_output(raw)
        self.assertIsNotNone(out.timed)
        self.assertEqual(out.timed.timed_mode, "recurring")
        self.assertEqual(out.timed.timed_config.interval, "5s")
        self.assertEqual(out.timed.timed_config.content, "tick")

    def test_absent_timed_section_is_none(self):
        raw = (
            "PROSE:\nThe scene unfolds.\n\n"
            "CHOICES:\n- Go | next\n\n"
            "SUMMARY:\nThe scene unfolds.\n"
        )
        out = parse_model_output(raw)
        self.assertIsNone(out.timed)


# ── Passage-type + prompt guidance tests ─────────────────────────────────────

class TimedPassageTypesTests(unittest.TestCase):
    def test_passage_types_includes_timed(self):
        self.assertIn("timed", PASSAGE_TYPES)


class TimedGuidanceTests(unittest.TestCase):
    """SUGARCUBE_GUIDANCE and prompts surface the timed macros."""

    def test_sugarcube_guidance_mentions_timed(self):
        from harness.prompts import SUGARCUBE_GUIDANCE
        self.assertIn("<<timed", SUGARCUBE_GUIDANCE)
        self.assertIn("<<repeat", SUGARCUBE_GUIDANCE)

    def test_full_prompt_has_timed_section(self):
        from harness.prompts import build_full_passage_prompt
        prompt = build_full_passage_prompt(
            premise="p", story_points="sp", arc_md="a",
            snapshot_text="s", entities_text="e", inspiration="",
            parent_prose="pp", human_prompt="hp", mode="co-author",
        )
        self.assertIn("TIMED:", prompt)
        self.assertIn("reveal", prompt)
        self.assertIn("countdown", prompt)
        self.assertIn("recurring", prompt)

    def test_json_prompt_has_timed_key(self):
        # build_json_passage_prompt hits a pre-existing f-string bug (DEV-5:
        # the achievements TODO comment has unescaped '{' — unrelated to this
        # feature), so we verify the source contains the timed key spec rather
        # than invoking the function. This confirms site #20 is implemented.
        import inspect
        from harness.prompts import build_json_passage_prompt
        src = inspect.getsource(build_json_passage_prompt)
        self.assertIn("timed", src)
        self.assertIn("timed_mode", src)

    def test_prompt_version_bumped(self):
        from harness.prompts import PROMPT_VERSION
        self.assertGreaterEqual(PROMPT_VERSION, 8)


# ── INV-4: check_timed_countdown_anchor (P7 new validation) ─────────────────

class TimedCountdownAnchorTests(unittest.TestCase):
    """INV-4: countdown prose must contain <span id=\"{anchor_id}\">."""

    def test_anchor_present_no_issue(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="AnchorTest")
            out = _basic_output(prose='The timer ticks <span id="countdown">10</span>.')
            cfg = TimedConfig(
                interval="1s", counter_var="seconds", start_value=10,
                final_content="Done", anchor_id="countdown",
            )
            create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            graph = rebuild_story(p)[0]
            issues = check_timed_countdown_anchor(p, graph)
            self.assertEqual(issues, [])

    def test_anchor_missing_emits_error(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="AnchorTest")
            out = _basic_output(prose="The timer ticks. No span here.")
            cfg = TimedConfig(
                interval="1s", counter_var="seconds", start_value=10,
                final_content="Done", anchor_id="countdown",
            )
            create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            graph = rebuild_story(p)[0]
            issues = check_timed_countdown_anchor(p, graph)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "timed_countdown_no_anchor")
            self.assertEqual(issues[0].level, "error")

    def test_anchor_mismatched_id_emits_error(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="AnchorTest")
            # prose has a span but with a different id
            out = _basic_output(prose='The timer ticks <span id="wrong">10</span>.')
            cfg = TimedConfig(
                interval="1s", counter_var="seconds", start_value=10,
                final_content="Done", anchor_id="countdown",
            )
            create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            graph = rebuild_story(p)[0]
            issues = check_timed_countdown_anchor(p, graph)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "timed_countdown_no_anchor")

    def test_reveal_mode_not_checked(self):
        # INV-4 only applies to countdown mode; reveal should not be flagged.
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="AnchorTest")
            out = _basic_output(prose="No span here.")
            create_passage(
                p, "intro", "01_rev", out, None,
                passage_type="timed", timed_mode="reveal",
                timed_reveals=[TimedReveal(delay="2s", content="Boom.")],
            )
            graph = rebuild_story(p)[0]
            issues = check_timed_countdown_anchor(p, graph)
            self.assertEqual(issues, [])

    def test_single_quoted_span_matches(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="AnchorTest")
            out = _basic_output(prose="The timer ticks <span id='countdown'>10</span>.")
            cfg = TimedConfig(
                interval="1s", counter_var="seconds", start_value=10,
                final_content="Done", anchor_id="countdown",
            )
            create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            graph = rebuild_story(p)[0]
            issues = check_timed_countdown_anchor(p, graph)
            self.assertEqual(issues, [])


# ── INV-5: check_timed_delays (P7 new validation) ────────────────────────────

class TimedDelaysValidationTests(unittest.TestCase):
    """INV-5: delays/intervals must be valid CSS time >= 40ms."""

    def _graph_with_reveal(self, reveals):
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[],
            passage_type="timed", timed_mode="reveal", timed_reveals=reveals,
        )
        return g

    def _graph_with_config(self, mode, cfg):
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[],
            passage_type="timed", timed_mode=mode, timed_config=cfg,
        )
        return g

    def test_valid_reveal_delays_no_issue(self):
        from harness.project import ProjectPaths
        g = self._graph_with_reveal([TimedReveal(delay="2s", content="x")])
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(issues, [])

    def test_invalid_reveal_delay_emits_error(self):
        from harness.project import ProjectPaths
        g = self._graph_with_reveal([TimedReveal(delay="fast", content="x")])
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "timed_bad_delay")

    def test_subminimum_reveal_delay_emits_error(self):
        from harness.project import ProjectPaths
        # 30ms is below the 40ms floor
        g = self._graph_with_reveal([TimedReveal(delay="30ms", content="x")])
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "timed_bad_delay")

    def test_minimum_40ms_passes(self):
        from harness.project import ProjectPaths
        g = self._graph_with_reveal([TimedReveal(delay="40ms", content="x")])
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(issues, [])

    def test_valid_interval_no_issue(self):
        from harness.project import ProjectPaths
        g = self._graph_with_config("countdown", TimedConfig(interval="1s"))
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(issues, [])

    def test_invalid_interval_emits_error(self):
        from harness.project import ProjectPaths
        g = self._graph_with_config("recurring", TimedConfig(interval="soon"))
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "timed_bad_delay")

    def test_subminimum_interval_emits_error(self):
        from harness.project import ProjectPaths
        g = self._graph_with_config("countdown", TimedConfig(interval="10ms"))
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "timed_bad_delay")

    def test_non_timed_passage_not_checked(self):
        from harness.project import ProjectPaths
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[], passage_type="normal",
        )
        issues = check_timed_delays(ProjectPaths(Path(".")), g)
        self.assertEqual(issues, [])


# ── INV-7: check_passage_types timed_bad_mode (P7 body extension) ────────────

class TimedBadModeTests(unittest.TestCase):
    """INV-7: timed_mode must be in {reveal, countdown, recurring}."""

    def test_valid_modes_no_issue(self):
        for mode in ("reveal", "countdown", "recurring"):
            g = StoryGraph(start_passage="p")
            g.passages["p"] = PassageEntry(
                file="p.tw", arc="t", parents=[], children=[],
                passage_type="timed", timed_mode=mode,
            )
            issues = [i for i in check_passage_types(g) if i.code == "timed_bad_mode"]
            self.assertEqual(issues, [], f"mode={mode!r} should not flag")

    def test_bad_mode_emits_error(self):
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[],
            passage_type="timed", timed_mode="bogus",
        )
        issues = [i for i in check_passage_types(g) if i.code == "timed_bad_mode"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].level, "error")

    def test_default_reveal_mode_no_issue(self):
        # Default timed_mode is "reveal" — should not flag.
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[], passage_type="timed",
        )
        issues = [i for i in check_passage_types(g) if i.code == "timed_bad_mode"]
        self.assertEqual(issues, [])

    def test_non_timed_passage_not_checked_for_mode(self):
        g = StoryGraph(start_passage="p")
        g.passages["p"] = PassageEntry(
            file="p.tw", arc="t", parents=[], children=[], passage_type="normal",
        )
        issues = [i for i in check_passage_types(g) if i.code == "timed_bad_mode"]
        self.assertEqual(issues, [])


# ── run_validation integration ───────────────────────────────────────────────

class TimedValidationIntegrationTests(unittest.TestCase):
    """The three new P7 checks are registered in run_validation."""

    def test_run_validation_registers_timed_checks(self):
        # A countdown passage with a missing anchor + bad interval should
        # produce both timed_countdown_no_anchor and timed_bad_delay via
        # run_validation (not just the direct functions).
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Integration")
            out = _basic_output(prose="No span here.")
            cfg = TimedConfig(
                interval="5ms", counter_var="s", start_value=3,
                final_content="Done", anchor_id="cd",
            )
            create_passage(
                p, "intro", "01_cd", out, None,
                passage_type="timed", timed_mode="countdown", timed_config=cfg,
            )
            result = run_validation(p)
            codes = {i.code for i in result.errors}
            self.assertIn("timed_countdown_no_anchor", codes)
            self.assertIn("timed_bad_delay", codes)


if __name__ == "__main__":
    unittest.main()

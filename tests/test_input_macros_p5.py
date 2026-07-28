"""P5 Mock & Validate tests for the input-macros (form passage type) feature.

Covers all scenarios enumerated in P1 §5:
  1. Form renders all 7 input macros (textbox, numberbox, textarea, checkbox,
     radiobutton, listbox, cycle, numberbox, textarea).
  2. Submit link uses UNRESOLVED_choice0_* placeholder.
  3. State vars auto-declared from input-macro target vars.
  4. scan_state_writes catches input macros.
  5. scan_state_reads skips quoted receivers.
  6. cycle/listbox macro pairing validates.
  7. Form with no fields is an error.

These tests exercise the provisional P5 implementation on the scratch branch.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.models import (
    INPUT_MACRO_KINDS,
    ModelOutput,
    ParsedChoice,
    ParsedInputField,
    ParsedInputOption,
    PassageEntry,
    StateVariable,
    StoryGraph,
)
from harness.ollama import parse_model_output
from harness.passage import (
    _render_input_field,
    _render_form_block,
    create_passage,
    scan_state_reads,
    scan_state_writes,
)
from harness.project import ProjectPaths, init_project, load_story, save_story
from harness.validation import (
    check_form_fields,
    check_macro_pairing,
    check_passage_types,
    run_validation,
)


# ── 1. Rendering all 7 input macros ───────────────────────────────────────────


class InputFieldRenderTests(unittest.TestCase):
    """Each of the 7 input macros renders to the correct SugarCube syntax."""

    def test_textbox_renders(self):
        f = ParsedInputField(kind="textbox", var="$name", default="hero")
        out = _render_input_field(f)
        self.assertIn('<<textbox "$name" "hero"', out)
        self.assertTrue(out.rstrip().endswith(">>"))

    def test_textbox_autofocus_flag(self):
        f = ParsedInputField(kind="textbox", var="$name", default="", autofocus=True)
        out = _render_input_field(f)
        self.assertIn("autofocus", out)

    def test_numberbox_renders(self):
        f = ParsedInputField(kind="numberbox", var="$age", default=18)
        out = _render_input_field(f)
        self.assertIn('<<numberbox "$age" 18', out)

    def test_textarea_renders(self):
        f = ParsedInputField(kind="textarea", var="$bio", default="")
        out = _render_input_field(f)
        self.assertIn('<<textarea "$bio" ""', out)

    def test_checkbox_renders(self):
        f = ParsedInputField(
            kind="checkbox", var="$hardcore",
            unchecked_value="off", checked_value="on",
        )
        out = _render_input_field(f)
        self.assertIn('<<checkbox "$hardcore" "off" "on"', out)

    def test_checkbox_checked_flag(self):
        f = ParsedInputField(
            kind="checkbox", var="$hardcore",
            unchecked_value="off", checked_value="on", checked=True,
        )
        out = _render_input_field(f)
        self.assertIn("checked", out)

    def test_radiobutton_renders(self):
        f = ParsedInputField(kind="radiobutton", var="$gender", checked_value="F")
        out = _render_input_field(f)
        self.assertIn('<<radiobutton "$gender" "F"', out)

    def test_listbox_renders_with_options(self):
        f = ParsedInputField(
            kind="listbox", var="$class",
            options=[
                ParsedInputOption(label="Fighter"),
                ParsedInputOption(label="Mage"),
            ],
        )
        out = _render_input_field(f)
        self.assertIn('<<listbox "$class">', out)
        self.assertIn('<<option "Fighter">', out)
        self.assertIn('<<option "Mage">', out)
        self.assertIn("<</listbox>>", out)

    def test_cycle_renders_with_options(self):
        f = ParsedInputField(
            kind="cycle", var="$tone",
            options=[
                ParsedInputOption(label="Serious"),
                ParsedInputOption(label="Playful"),
            ],
        )
        out = _render_input_field(f)
        self.assertIn('<<cycle "$tone">', out)
        self.assertIn('<<option "Serious">', out)
        self.assertIn('<<option "Playful">', out)
        self.assertIn("<</cycle>>", out)

    def test_cycle_once_flag(self):
        f = ParsedInputField(
            kind="cycle", var="$tone", once=True,
            options=[ParsedInputOption(label="A")],
        )
        out = _render_input_field(f)
        self.assertIn("once", out)

    def test_all_7_kinds_in_INPUT_MACRO_KINDS(self):
        expected = {
            "textbox", "numberbox", "textarea",
            "checkbox", "radiobutton", "listbox", "cycle",
        }
        self.assertEqual(set(INPUT_MACRO_KINDS), expected)
        self.assertEqual(len(INPUT_MACRO_KINDS), 7)


# ── Form block rendering (fields + submit link) ────────────────────────────────


class FormBlockRenderTests(unittest.TestCase):
    """_render_form_block emits label + macro per field, then submit link(s)."""

    def test_form_block_renders_fields_and_submit(self):
        fields = [
            ParsedInputField(kind="textbox", var="$name", default="", label="Name"),
            ParsedInputField(kind="numberbox", var="$age", default=18, label="Age"),
        ]
        choices = [ParsedChoice(text="Submit", hint="submit")]
        lines = _render_form_block(fields, choices, start_index=0)
        joined = "\n".join(lines)
        self.assertIn("Name", joined)
        self.assertIn('<<textbox "$name"', joined)
        self.assertIn("Age", joined)
        self.assertIn('<<numberbox "$age"', joined)
        # Submit uses UNRESOLVED placeholder
        self.assertIn("UNRESOLVED_choice0_submit", joined)

    def test_form_block_empty_fields_returns_empty(self):
        """A form with no fields renders nothing (validation flags the error)."""
        choices = [ParsedChoice(text="Submit", hint="submit")]
        lines = _render_form_block([], choices, start_index=0)
        self.assertEqual(lines, [])


# ── 2. Submit link uses UNRESOLVED placeholder ─────────────────────────────────


class FormPassageSubmitTests(unittest.TestCase):
    """Form passages render a submit <<link>> with UNRESOLVED_choice0_*."""

    def _make_form(self, tmp, fields, choices=None):
        p = init_project(Path(tmp), title="Test")
        if choices is None:
            choices = [ParsedChoice(text="Submit", hint="submit")]
        out = ModelOutput(
            prose="Character creation.",
            choices=choices,
            inputs=fields,
            summary="Form.",
        )
        pid, graph = create_passage(
            p, "intro", "01_form", out, None, passage_type="form",
        )
        tw = (Path(tmp) / graph.passages[pid].file).read_text(encoding="utf-8")
        return p, pid, graph, tw

    def test_submit_uses_unresolved_placeholder(self):
        with TemporaryDirectory() as tmp:
            _, _, _, tw = self._make_form(
                tmp,
                [ParsedInputField(kind="textbox", var="$name", default="")],
            )
            self.assertIn("UNRESOLVED_choice0_submit", tw)

    def test_form_tag_in_passage_header(self):
        with TemporaryDirectory() as tmp:
            _, pid, graph, tw = self._make_form(
                tmp,
                [ParsedInputField(kind="textbox", var="$name", default="")],
            )
            self.assertIn(f":: {pid} [intro form]", tw)

    def test_form_renders_all_7_macros_in_passage(self):
        with TemporaryDirectory() as tmp:
            fields = [
                ParsedInputField(kind="textbox", var="$name", default=""),
                ParsedInputField(kind="numberbox", var="$age", default=18),
                ParsedInputField(kind="textarea", var="$bio", default=""),
                ParsedInputField(
                    kind="checkbox", var="$hc",
                    unchecked_value="off", checked_value="on",
                ),
                ParsedInputField(kind="radiobutton", var="$g", checked_value="F"),
                ParsedInputField(
                    kind="listbox", var="$cls",
                    options=[ParsedInputOption(label="A")],
                ),
                ParsedInputField(
                    kind="cycle", var="$tone",
                    options=[ParsedInputOption(label="X")],
                ),
            ]
            _, _, _, tw = self._make_form(tmp, fields)
            self.assertIn('<<textbox "$name"', tw)
            self.assertIn('<<numberbox "$age"', tw)
            self.assertIn('<<textarea "$bio"', tw)
            self.assertIn('<<checkbox "$hc"', tw)
            self.assertIn('<<radiobutton "$g"', tw)
            self.assertIn('<<listbox "$cls"', tw)
            self.assertIn('<<cycle "$tone"', tw)
            self.assertIn("<</listbox>>", tw)
            self.assertIn("<</cycle>>", tw)


# ── 3. State vars auto-declared ───────────────────────────────────────────────


class FormStateVarDeclarationTests(unittest.TestCase):
    """Input-macro target vars are auto-declared as state variables."""

    def test_input_target_vars_auto_declared(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Character creation.",
                choices=[ParsedChoice(text="Submit", hint="submit")],
                inputs=[
                    ParsedInputField(kind="textbox", var="$name", default=""),
                    ParsedInputField(kind="numberbox", var="$age", default=18),
                ],
                summary="Form.",
            )
            pid, graph = create_passage(
                p, "intro", "01_form", out, None, passage_type="form",
            )
            # The create_passage function should register the input-macro
            # target vars in the passage's state_writes (via scan_state_writes
            # on the rendered .tw content).
            entry = graph.passages[pid]
            self.assertIn("$name", entry.state_writes)
            self.assertIn("$age", entry.state_writes)

    def test_input_vars_no_false_undeclared_error(self):
        """A form passage's input target vars should NOT trigger
        undeclared_state_var errors when downstream passages read them,
        because they count as writes."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            # Form passage writes $name via <<textbox "$name" ...>>
            form_out = ModelOutput(
                prose="Enter your name.",
                choices=[ParsedChoice(text="Submit", hint="next")],
                inputs=[ParsedInputField(kind="textbox", var="$name", default="")],
                summary="Form.",
            )
            form_id, graph = create_passage(
                p, "intro", "01_form", form_out, None, passage_type="form",
            )
            # Downstream passage reads $name
            reader_out = ModelOutput(
                prose="Hello, $name!",
                choices=[ParsedChoice(text="Go", hint="on")],
                summary="Reads name.",
            )
            create_passage(
                p, "intro", "02_read", reader_out, form_id, choice_index=0,
            )
            result = run_validation(p)
            # Should NOT flag $name as undeclared
            undeclared = [
                e for e in result.errors
                if e.code == "undeclared_state_var" and "$name" in e.message
            ]
            self.assertEqual(
                undeclared, [],
                f"$name should be declared via form input macro write, "
                f"but got: {[e.message for e in undeclared]}",
            )


# ── 4. scan_state_writes catches input macros ─────────────────────────────────


class ScanStateWritesInputMacroTests(unittest.TestCase):
    """scan_state_writes recognizes input macros as writers."""

    def test_textbox_target_is_write(self):
        tw = '<<textbox "$name" "default">>'
        self.assertIn("$name", scan_state_writes(tw))

    def test_all_7_macros_are_writes(self):
        samples = [
            '<<textbox "$a" "">>',
            '<<numberbox "$b" 0>>',
            '<<textarea "$c" "">>',
            '<<checkbox "$d" "off" "on">>',
            '<<radiobutton "$e" "F">',
            '<<listbox "$f">>',
            '<<cycle "$g">>',
        ]
        for tw in samples:
            writes = scan_state_writes(tw)
            # Extract the var name we expect
            import re
            m = re.search(r'"\$([a-zA-Z_]\w*)"', tw)
            self.assertIsNotNone(m)
            expected = "$" + m.group(1)
            self.assertIn(expected, writes, f"{tw} should write {expected}")

    def test_set_still_recognized(self):
        tw = "<<set $gold to 5>>"
        self.assertIn("$gold", scan_state_writes(tw))

    def test_input_and_set_combined(self):
        tw = '<<set $gold to 5>>\n<<textbox "$name" "">>'
        writes = scan_state_writes(tw)
        self.assertIn("$gold", writes)
        self.assertIn("$name", writes)


# ── 5. scan_state_reads skips quoted receivers ────────────────────────────────


class ScanStateReadsQuotedReceiverTests(unittest.TestCase):
    """scan_state_reads does NOT count input-macro quoted receiver args as reads."""

    def test_textbox_receiver_not_a_read(self):
        tw = '<<textbox "$name" "default">>'
        reads = scan_state_reads(tw)
        self.assertNotIn(
            "$name", reads,
            "Input-macro receiver $name should NOT be a read (it's a write).",
        )

    def test_all_7_macros_receivers_not_reads(self):
        samples = [
            '<<textbox "$a" "">>',
            '<<numberbox "$b" 0>>',
            '<<textarea "$c" "">>',
            '<<checkbox "$d" "off" "on">>',
            '<<radiobutton "$e" "F">',
            '<<listbox "$f">>',
            '<<cycle "$g">>',
        ]
        for tw in samples:
            reads = scan_state_reads(tw)
            import re
            m = re.search(r'"\$([a-zA-Z_]\w*)"', tw)
            self.assertIsNotNone(m)
            var = "$" + m.group(1)
            self.assertNotIn(
                var, reads,
                f"Input-macro receiver {var} in {tw} should NOT be a read.",
            )

    def test_prose_read_still_counted(self):
        """Naked $var in prose is still a read (not inside an input macro)."""
        tw = "Hello, $name!"
        self.assertIn("$name", scan_state_reads(tw))

    def test_input_macro_does_not_mask_other_reads(self):
        """An input macro's quoted receiver is stripped, but other $var reads
        in the same content are still caught."""
        tw = '<<textbox "$name" "">> You have $gold coins.'
        reads = scan_state_reads(tw)
        self.assertNotIn("$name", reads)
        self.assertIn("$gold", reads)


# ── 6. cycle/listbox macro pairing validates ──────────────────────────────────


class CycleListboxPairingTests(unittest.TestCase):
    """cycle and listbox are now in MACRO_CONTAINERS — check_macro_pairing
    validates their nesting (fixes P1 §2.4 doc error)."""

    @staticmethod
    def _check(tmp, body):
        p = init_project(Path(tmp), title="Test")
        f = p.arcs_dir / "x" / "01.tw"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(":: x__01 [x]\n" + body + "\n", encoding="utf-8")
        graph = StoryGraph()
        graph.passages["x__01"] = PassageEntry(file="arcs/x/01.tw", arc="x")
        return check_macro_pairing(p, graph)

    def test_balanced_listbox_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                self._check(
                    tmp,
                    '<<listbox "$x">><<option "A">><<option "B">><</listbox>>',
                ),
                [],
            )

    def test_balanced_cycle_ok(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                self._check(
                    tmp,
                    '<<cycle "$y">><<option "A">><</cycle>>',
                ),
                [],
            )

    def test_unclosed_listbox_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, '<<listbox "$x">><<option "A">>')
            self.assertTrue(any("never closed" in i.message for i in issues))

    def test_unclosed_cycle_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, '<<cycle "$y">><<option "A">>')
            self.assertTrue(any("never closed" in i.message for i in issues))

    def test_stray_listbox_close_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "text <</listbox>>")
            self.assertTrue(any("stray" in i.message for i in issues))

    def test_stray_cycle_close_flagged(self):
        with TemporaryDirectory() as tmp:
            issues = self._check(tmp, "text <</cycle>>")
            self.assertTrue(any("stray" in i.message for i in issues))


# ── 7. Form with no fields is an error ────────────────────────────────────────


class FormValidationTests(unittest.TestCase):
    """Form passages with no input fields or no submit target are errors."""

    def test_form_no_submit_is_error(self):
        """check_passage_types flags form passages with no children (no submit)."""
        graph = StoryGraph()
        graph.passages["01_form"] = PassageEntry(
            file="arcs/intro/01_form.tw", arc="intro", passage_type="form",
            children=[],
        )
        issues = check_passage_types(graph)
        self.assertTrue(
            any(i.code == "form_no_submit" for i in issues),
            f"Expected form_no_submit error, got: {[i.code for i in issues]}",
        )

    def test_form_with_submit_no_error(self):
        graph = StoryGraph()
        graph.passages["01_form"] = PassageEntry(
            file="arcs/intro/01_form.tw", arc="intro", passage_type="form",
            children=["02_next"],
        )
        issues = check_passage_types(graph)
        form_issues = [i for i in issues if i.code == "form_no_submit"]
        self.assertEqual(form_issues, [])

    def test_form_no_fields_is_error(self):
        """check_form_fields flags a form passage whose .tw has no input macros."""
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "intro" / "01_form.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                ":: intro__01_form [intro form]\nSome prose\n[[Submit|UNRESOLVED_choice0_submit]]\n",
                encoding="utf-8",
            )
            graph = StoryGraph()
            graph.passages["intro__01_form"] = PassageEntry(
                file="arcs/intro/01_form.tw", arc="intro",
                passage_type="form", children=["02_next"],
            )
            issues = check_form_fields(p, graph)
            self.assertTrue(
                any(i.code == "form_no_fields" for i in issues),
                f"Expected form_no_fields error, got: {[i.code for i in issues]}",
            )

    def test_form_with_fields_no_error(self):
        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            f = p.arcs_dir / "intro" / "01_form.tw"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                ':: intro__01_form [intro form]\nSome prose\n<<textbox "$name" "">>\n[[Submit|UNRESOLVED_choice0_submit]]\n',
                encoding="utf-8",
            )
            graph = StoryGraph()
            graph.passages["intro__01_form"] = PassageEntry(
                file="arcs/intro/01_form.tw", arc="intro",
                passage_type="form", children=["02_next"],
            )
            issues = check_form_fields(p, graph)
            self.assertEqual(
                issues, [],
                f"Form with a field should not error, got: {[i.message for i in issues]}",
            )


# ── Parser tests (INPUT section parsing) ──────────────────────────────────────


class InputSectionParserTests(unittest.TestCase):
    """parse_model_output parses the INPUT section into ModelOutput.inputs."""

    def test_parse_input_section_textbox(self):
        raw = """PROSE:
Enter your name.

CHOICES:
- Submit | submit

INPUT:
- textbox | $name | "" | Player name

SUMMARY:
Form.
"""
        out = parse_model_output(raw)
        self.assertEqual(len(out.inputs), 1)
        self.assertEqual(out.inputs[0].kind, "textbox")
        self.assertEqual(out.inputs[0].var, "$name")
        self.assertEqual(out.inputs[0].label, "Player name")

    def test_parse_input_section_multiple(self):
        raw = """PROSE:
Create your character.

CHOICES:
- Submit | submit

INPUT:
- textbox | $name | "" | Name
- numberbox | $age | 18 | Age
- radiobutton | $gender | F | Gender
- radiobutton | $gender | M | Gender

SUMMARY:
Form.
"""
        out = parse_model_output(raw)
        self.assertEqual(len(out.inputs), 4)
        kinds = [f.kind for f in out.inputs]
        self.assertEqual(kinds, ["textbox", "numberbox", "radiobutton", "radiobutton"])

    def test_parse_input_section_listbox_with_options(self):
        raw = """PROSE:
Pick a class.

CHOICES:
- Submit | submit

INPUT:
- listbox | $class | | Class
  - option | Fighter
  - option | Mage

SUMMARY:
Form.
"""
        out = parse_model_output(raw)
        self.assertEqual(len(out.inputs), 1)
        self.assertEqual(out.inputs[0].kind, "listbox")
        self.assertEqual(len(out.inputs[0].options), 2)
        self.assertEqual(out.inputs[0].options[0].label, "Fighter")
        self.assertEqual(out.inputs[0].options[1].label, "Mage")

    def test_no_input_section_empty_inputs(self):
        raw = """PROSE:
A normal passage.

CHOICES:
- Go | onward

SUMMARY:
Normal.
"""
        out = parse_model_output(raw)
        self.assertEqual(out.inputs, [])

    def test_unknown_kind_skipped(self):
        raw = """PROSE:
Form.

CHOICES:
- Submit | submit

INPUT:
- bogusmacro | $x | "" | Label

SUMMARY:
Form.
"""
        out = parse_model_output(raw)
        self.assertEqual(out.inputs, [])


if __name__ == "__main__":
    unittest.main()

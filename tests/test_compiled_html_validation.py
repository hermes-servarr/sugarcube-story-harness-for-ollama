"""Validation tests for compiled SugarCube HTML files.

Extracts <script>, <style>, and <tw-passagedata> blocks from compiled SugarCube
stories and checks them for real, detectable JS/CSS/structural errors using:

  * node --check    — real JS syntax validation (a full JS engine, so regex
                      literals in minified SugarCube/jQuery engine code are
                      parsed correctly and NOT reported as errors).
  * tinycss2        — CSS parsing for <style> blocks.
  * html.parser     — stdlib HTML parser to separate script/style blocks so
                      ``<style``/``<script`` substrings that appear *inside* JS
                      regex literals are never mistaken for real tags.

Run with::

    uv run python -m pytest tests/test_compiled_html_validation.py

SugarCube-specific checks:
  * unescaped ``<<...>>`` macro syntax inside <script> JS blocks,
  * malformed <tw-passagedata> tags (missing required attrs, bad pid/position),
  * broken HTML entities (``&`` not part of a valid entity reference).

Reporting: every error is a dict with ``severity`` (``error``/``warning``),
``line``, ``column``, ``message``, ``context`` (surrounding source), plus
``block`` and ``section`` tags to identify which check produced it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import tinycss2

REPO_ROOT = Path(__file__).resolve().parent.parent

# Known-good compiled HTML files shipped with the repo. The validation suite
# must pass cleanly against these.
KNOWN_GOOD_HTML_FILES = [
    REPO_ROOT / "tests" / "fixtures" / "test_story.html",
    REPO_ROOT / "test_stories" / "rpg-sandbox" / "build" / "story.html",
    REPO_ROOT / "examples" / "the-cartographers-dilemma" / "the-cartographers-dilemma.html",
]

# Severity levels used in reported errors.
SEV_ERROR = "error"
SEV_WARNING = "warning"

# Known SugarCube macro names. Used to distinguish a genuine macro-leak
# (``<<set ...>>``) from arithmetic bit-shifts (``a << b >> c``).
SUGARCUBE_MACROS = {
    "set", "unset", "if", "elseif", "else", "endif", "switch", "case",
    "default", "endswitch", "for", "break", "continue", "endfor",
    "link", "linkappend", "linkprepend", "linkreplace", "endlink",
    "endlinkappend", "endlinkprepend", "endlinkreplace",
    "print", "silently", "nobr", "capture", "script", "include",
    "widget", "done", "repeat", "stop", "endrepeat",
    "timed", "next", "endtimed", "event", "endevent",
    "button", "return", "actions", "choice", "checkbox", "cycle",
    "listbox", "numberbox", "radiobutton", "textbox", "textarea",
    "dropdown", "option", "append", "prepend", "replace",
    "endappend", "endprepend", "endreplace", "endchoice", "endcapture",
    "endwidget", "endnobr", "endprint", "endsilently", "endbutton",
    "endactions", "endcycle", "endlistbox", "endnumberbox", "endtextbox",
    "endtextarea", "endradiobutton", "endcheckbox", "endoption",
    "playlist", "stopallaudio", "createplaylist", "setplaylist",
    "removeplaylist", "masteraudio", "track", "audio", "video",
    "endaudio", "endvideo", "type",
}

# At-rules whose block content is a *declaration list* (not a nested rule list).
# Parsing their content with the wrong parser triggers spurious errors.
_AT_RULES_WITH_DECL_BODY = {
    "font-face", "page", "viewport", "counter-style",
    "font-feature-values", "property",
}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

class _BlockExtractor(HTMLParser):
    """Extract <script> and <style> block contents using a real HTML parser.

    Using a real parser (rather than naive regex) is critical for compiled
    SugarCube output: the minified jQuery/SugarCube engine code contains regex
    literals like ``/<style|<link/i`` and ``/<script|<style|<link/i`` that a
    regex-based extractor would mistake for real tags, producing false
    positives. The HTML parser only fires for actual tag tokens.

    Also collects non-script, non-style text data (for HTML-entity checks that
    must skip JS/CSS content where ``&&`` and ``&`` are legitimate).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[tuple[tuple[int, int], dict[str, str], str]] = []
        self.styles: list[tuple[tuple[int, int], dict[str, str], str]] = []
        self.html_text_parts: list[str] = []
        self._current: list[str] | None = None
        self._tag: str | None = None
        self._pos: tuple[int, int] = (0, 0)
        self._attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._current = []
            self._tag = tag
            self._pos = self.getpos()
            self._attrs = {k: (v or "") for k, v in attrs}

    def handle_endtag(self, tag: str) -> None:
        if tag == self._tag and self._current is not None:
            content = "".join(self._current)
            entry = (self._pos, self._attrs, content)
            if tag == "script":
                self.scripts.append(entry)
            else:
                self.styles.append(entry)
            self._current = None
            self._tag = None
            self._attrs = {}

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.append(data)
        elif self._tag is None:
            # Text outside any script/style block — candidate for entity checks.
            self.html_text_parts.append(data)


class _PassageDataExtractor(HTMLParser):
    """Extract <tw-passagedata> start-tag attributes and text content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.passages: list[tuple[tuple[int, int], dict[str, str], str]] = []
        self._in_passage = False
        self._pos: tuple[int, int] = (0, 0)
        self._attrs: dict[str, str] = {}
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tw-passagedata":
            self._in_passage = True
            self._pos = self.getpos()
            self._attrs = {k: (v or "") for k, v in attrs}
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "tw-passagedata" and self._in_passage:
            self.passages.append((self._pos, self._attrs, "".join(self._buf)))
            self._in_passage = False

    def handle_data(self, data: str) -> None:
        if self._in_passage:
            self._buf.append(data)


def extract_blocks(html: str) -> tuple[list, list, str]:
    """Return (scripts, styles, html_text) where each entry is (pos, attrs,
    content); html_text is the concatenation of text outside script/style."""
    p = _BlockExtractor()
    p.feed(html)
    return p.scripts, p.styles, "".join(p.html_text_parts)


def extract_passages(html: str) -> list:
    """Return list of (pos, attrs, content) for <tw-passagedata> elements."""
    p = _PassageDataExtractor()
    p.feed(html)
    return p.passages


# ---------------------------------------------------------------------------
# JS validation via node --check
# ---------------------------------------------------------------------------

_NODE = shutil.which("node")


def validate_js(content: str) -> list[dict]:
    """Validate a JS string with ``node --check``.

    node is a complete JS engine, so regex literals (e.g. SugarCube/jQuery
    minified engine code full of ``/pattern/flags``) are tokenised correctly
    and never reported as syntax errors. Returns a list of error dicts with
    line, column, message, severity, and surrounding context.
    """
    if not _NODE:
        return [{"severity": SEV_ERROR, "message": "node executable not found; cannot validate JS"}]
    if not content.strip():
        return []
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = f.name
    try:
        r = subprocess.run(
            [_NODE, "--check", path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        os.unlink(path)
    if r.returncode == 0:
        return []
    errors = []
    stderr = r.stderr or ""
    # node prints: "<file>:<line>\n\nSyntaxError: <msg>\n    at ..."
    for line in stderr.splitlines():
        m = re.match(r"^(?:\S+:)?(?P<line>\d+)(?::(?P<col>\d+))?\s*$", line)
        if m:
            ctx_line = int(m.group("line"))
            errors.append({
                "severity": SEV_ERROR,
                "line": ctx_line,
                "column": int(m.group("col")) if m.group("col") else 0,
                "message": "JS syntax error (see SyntaxError below)",
            })
            continue
        m = re.match(r"^\s*SyntaxError:\s*(?P<msg>.*)$", line)
        if m and errors:
            errors[-1]["message"] = f"SyntaxError: {m.group('msg').strip()}"
    for err in errors:
        err["context"] = _context_around(content, err.get("line", 0))
    return errors


def _context_around(text: str, line: int, radius: int = 2) -> str:
    """Return ~2*radius lines of context around 1-indexed ``line``."""
    if line <= 0:
        return ""
    lines = text.splitlines()
    start = max(0, line - 1 - radius)
    end = min(len(lines), line + radius)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))


# ---------------------------------------------------------------------------
# CSS validation via tinycss2
# ---------------------------------------------------------------------------

def _collect_css_errors(rules_list: list, errors: list[dict]) -> None:
    """Recursively collect tinycss2 parse errors from a rule list."""
    for node in rules_list:
        if node.type == "error":
            errors.append({
                "severity": SEV_ERROR,
                "line": 0,
                "column": 0,
                "message": f"CSS parse error: {getattr(node, 'message', '')}",
            })
        elif node.type == "qualified-rule":
            _collect_css_errors(
                tinycss2.parse_declaration_list(
                    node.content, skip_comments=False, skip_whitespace=False),
                errors,
            )
        elif node.type == "at-rule":
            if node.content:
                if node.at_keyword.lower() in _AT_RULES_WITH_DECL_BODY:
                    # @font-face, @page, etc. — body is a declaration list.
                    _collect_css_errors(
                        tinycss2.parse_declaration_list(
                            node.content, skip_comments=False, skip_whitespace=False),
                        errors,
                    )
                else:
                    # @media, @supports, @keyframes — body is a nested rule list.
                    _collect_css_errors(
                        tinycss2.parse_rule_list(
                            node.content, skip_comments=False, skip_whitespace=False),
                        errors,
                    )


def validate_css(content: str) -> list[dict]:
    """Validate a CSS string with tinycss2.

    Returns a list of error dicts. tinycss2 is lenient about unclosed braces
    (it auto-closes them) but flags tokenization errors (malformed tokens,
    unterminated strings) which surface as ``error`` nodes.
    """
    if not content.strip():
        return []
    errors: list[dict] = []
    rules = tinycss2.parse_stylesheet(content, skip_comments=False, skip_whitespace=False)
    _collect_css_errors(rules, errors)
    return errors


# ---------------------------------------------------------------------------
# SugarCube-specific checks
# ---------------------------------------------------------------------------

# Strip JS string literals so macro names mentioned *inside* engine error
# messages (e.g. ``"<<else>> must be the final clause"``) are not flagged.
_JS_STRING_RE = re.compile(
    r'"(?:\\.|[^"\\])*"'      # double-quoted
    r"|'(?:\\.|[^'\\])*'"     # single-quoted
    r"|`(?:\\.|[^`\\])*`",    # template literal
    re.DOTALL,
)

# After stripping strings, match ``<<word`` where word is a known SugarCube macro.
_MACRO_START_RE = re.compile(r"<<\s*([a-zA-Z][a-zA-Z0-9_-]*)")


def check_unescaped_macros_in_js(script_content: str) -> list[dict]:
    """Detect SugarCube ``<<...>>`` macro syntax that leaked into JS.

    The SugarCube engine legitimately contains macro names inside JS string
    literals (error messages like ``"<<else>> must be..."``). We strip string
    literals first, then only flag ``<<`` followed by a *known macro name*,
    so arithmetic bit-shifts (``a << b >> c``) are never reported.
    """
    errors: list[dict] = []
    stripped = _JS_STRING_RE.sub("", script_content)
    for m in _MACRO_START_RE.finditer(stripped):
        name = m.group(1).lower()
        if name not in SUGARCUBE_MACROS:
            continue
        line = script_content.count("\n", 0, m.start()) + 1
        col = m.start() - (script_content.rfind("\n", 0, m.start()) + 1) + 1
        snippet = script_content[max(0, m.start() - 20): m.end() + 20]
        errors.append({
            "severity": SEV_ERROR,
            "line": line,
            "column": col,
            "message": f"unescaped SugarCube macro '{m.group(1)}' inside <script> block",
            "context": snippet,
        })
    return errors


# Required attributes for a well-formed <tw-passagedata>.
_PASSAGE_REQUIRED_ATTRS = ("pid", "name")
_POS_RE = re.compile(r"^\d+,\d+$")


def check_passage_data(passages: list) -> list[dict]:
    """Validate <tw-passagedata> tags for required attrs and well-formed values."""
    errors = []
    for pos, attrs, content in passages:
        for req in _PASSAGE_REQUIRED_ATTRS:
            if req not in attrs or not attrs[req]:
                errors.append({
                    "severity": SEV_ERROR,
                    "line": pos[0],
                    "column": pos[1],
                    "message": f"<tw-passagedata> missing required attribute '{req}'",
                    "context": f"attrs={attrs}",
                })
        if "pid" in attrs and attrs["pid"] and not attrs["pid"].isdigit():
            errors.append({
                "severity": SEV_ERROR,
                "line": pos[0],
                "column": pos[1],
                "message": f"<tw-passagedata> pid is not a positive integer: {attrs['pid']!r}",
                "context": f"pid={attrs['pid']!r}",
            })
        if "position" in attrs and attrs["position"] and not _POS_RE.match(attrs["position"]):
            errors.append({
                "severity": SEV_WARNING,
                "line": pos[0],
                "column": pos[1],
                "message": f"<tw-passagedata> position not 'X,Y': {attrs['position']!r}",
                "context": f"position={attrs['position']!r}",
            })
        if "size" in attrs and attrs["size"] and not _POS_RE.match(attrs["size"]):
            errors.append({
                "severity": SEV_WARNING,
                "line": pos[0],
                "column": pos[1],
                "message": f"<tw-passagedata> size not 'W,H': {attrs['size']!r}",
                "context": f"size={attrs['size']!r}",
            })
    return errors


# Matches an ampersand that is NOT part of a valid entity reference.
# Valid forms: &name;  &#NNN;  &#xHH;  &#XHH;  & (bare & followed by non-entity)
_BROKEN_ENTITY_RE = re.compile(r"&(?!#?\w+;)")


def check_broken_html_entities(html_text: str) -> list[dict]:
    """Detect malformed HTML entities (bare ``&`` not part of a reference).

    Only run on text *outside* script/style blocks — inside JS, ``&&`` is the
    logical-and operator and inside CSS ``&`` may appear in nesting syntax.
    """
    errors: list[dict] = []
    if not html_text:
        return errors
    for m in _BROKEN_ENTITY_RE.finditer(html_text):
        line = html_text.count("\n", 0, m.start()) + 1
        col = m.start() - (html_text.rfind("\n", 0, m.start()) + 1) + 1
        snippet = html_text[max(0, m.start() - 15): m.end() + 15]
        errors.append({
            "severity": SEV_WARNING,
            "line": line,
            "column": col,
            "message": "potentially unescaped '&' (not a valid HTML entity)",
            "context": snippet,
        })
    return errors


# ---------------------------------------------------------------------------
# Top-level validation orchestrator
# ---------------------------------------------------------------------------

def validate_compiled_html(html: str) -> list[dict]:
    """Run all validations on a compiled SugarCube HTML string.

    Returns a flat list of error dicts, each with keys:
    severity, line, column, message, context (and optionally block/section).
    """
    errors: list[dict] = []
    scripts, styles, html_text = extract_blocks(html)
    passages = extract_passages(html)

    for idx, (pos, attrs, content) in enumerate(scripts):
        block_label = f"script[{idx}] id={attrs.get('id', '<none>')}"
        js_errs = validate_js(content)
        for e in js_errs:
            e["block"] = block_label
            e["section"] = "js"
        errors.extend(js_errs)
        macro_errs = check_unescaped_macros_in_js(content)
        for e in macro_errs:
            e["block"] = block_label
            e["section"] = "macro-leak"
        errors.extend(macro_errs)

    for idx, (pos, attrs, content) in enumerate(styles):
        block_label = f"style[{idx}] id={attrs.get('id', '<none>')}"
        css_errs = validate_css(content)
        for e in css_errs:
            e["block"] = block_label
            e["section"] = "css"
        errors.extend(css_errs)

    passage_errs = check_passage_data(passages)
    for e in passage_errs:
        e["section"] = "passage"
    errors.extend(passage_errs)

    entity_errs = check_broken_html_entities(html_text)
    for e in entity_errs:
        e["section"] = "html-entity"
    errors.extend(entity_errs)

    # Duplicate pid detection.
    seen_pids: dict[str, tuple[int, int]] = {}
    for pos, attrs, _ in passages:
        pid = attrs.get("pid", "")
        if not pid:
            continue
        if pid in seen_pids:
            errors.append({
                "severity": SEV_ERROR,
                "line": pos[0],
                "column": pos[1],
                "message": f"duplicate tw-passagedata pid={pid}",
                "section": "passage",
                "context": f"first seen at line {seen_pids[pid][0]}",
            })
        else:
            seen_pids[pid] = pos

    return errors


def _format_errors(errors: list[dict]) -> str:
    lines = []
    for e in errors:
        loc = f"line {e.get('line', '?')}, col {e.get('column', '?')}"
        sec = e.get("section", "?")
        block = e.get("block", "")
        ctx = e.get("context", "")
        lines.append(f"[{e['severity']}] {sec} {loc}: {e['message']}"
                     + (f" ({block})" if block else "")
                     + (f"\n    context: {ctx}" if ctx else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBlockExtraction(unittest.TestCase):
    """The HTML parser must separate real script/style blocks and must NOT
    be fooled by <script>/<style> substrings inside JS regex literals."""

    def test_extracts_scripts_from_known_good_story(self):
        html = (REPO_ROOT / "test_stories" / "rpg-sandbox" / "build" / "story.html").read_text()
        scripts, styles, _ = extract_blocks(html)
        self.assertGreaterEqual(len(scripts), 2, "compiled story should have >=2 script blocks")
        self.assertGreaterEqual(len(styles), 2, "compiled story should have >=2 style blocks")

    def test_does_not_flag_sugarcube_engine_regex_literals(self):
        """jQuery/SugarCube minified code contains regex literals like
        ``/<script|<style|<link/i``. These must NOT be mistaken for real tags."""
        html = (
            r'<html><head>'
            r'<script>var r=/<script|<style|<link/i; var s=/^\s*class /; var x=/\bhtml\b/;</script>'
            r'<style>body{color:red}</style>'
            r'</head></html>'
        )
        scripts, styles, _ = extract_blocks(html)
        self.assertEqual(len(scripts), 1,
                         "regex literal containing '<script' must not create a phantom script block")
        self.assertEqual(len(styles), 1)
        # The script content should contain the regex, proving it was captured.
        self.assertIn("/<script|<style|<link/i", scripts[0][2])

    def test_empty_script_block_is_allowed(self):
        html = '<script></script><style></style>'
        scripts, styles, _ = extract_blocks(html)
        self.assertEqual(len(scripts), 1)
        self.assertEqual(len(styles), 1)


class TestJSValidation(unittest.TestCase):
    """node --check must accept valid JS (including regex-heavy minified code)
    and reject genuinely broken JS."""

    def test_valid_minified_js_with_regex_passes(self):
        # Excerpt pattern from the SugarCube engine: heavy regex use.
        js = 'var a=/\\s+/g;var b=/^\\s*class /;var c=/\\b(?:java|ecma)script\\b/;a.test("x");'
        errors = validate_js(js)
        self.assertEqual(errors, [], f"valid regex-heavy JS should pass, got: {errors}")

    def test_sugarcube_engine_regex_not_flagged(self):
        # Real patterns lifted from jQuery in the compiled story.
        js = (
            r'var St=/^\s*<!(?:\[CDATA\[|--)|(?:\]\]|--)>/;'
            r'var Le=/checked\s*(?:[^=]|=\s*.checked.)/i;'
        )
        errors = validate_js(js)
        self.assertEqual(errors, [])

    def test_broken_js_is_detected(self):
        js = 'function foo({\n  return 1\n}'
        errors = validate_js(js)
        self.assertTrue(errors, "malformed JS should produce at least one error")
        self.assertEqual(errors[0]["severity"], SEV_ERROR)
        self.assertIn("line", errors[0])
        self.assertIn("message", errors[0])

    def test_empty_js_is_ok(self):
        self.assertEqual(validate_js(""), [])
        self.assertEqual(validate_js("   \n  "), [])


class TestCSSValidation(unittest.TestCase):

    def test_valid_css_passes(self):
        css = 'body{color:red;margin:0} @media screen{.x{font-size:12px}}'
        errors = validate_css(css)
        self.assertEqual(errors, [], f"valid CSS should pass, got: {errors}")

    def test_font_face_with_base64_passes(self):
        # The SugarCube @font-face block embeds a huge base64 data URL.
        css = (
            '@font-face{font-family:tme-fa-icons;'
            'src:url(data:application/octet-stream;base64,d09GRgABAAAAACWoAA4AAAAAQhQAA)}'
        )
        errors = validate_css(css)
        self.assertEqual(errors, [], f"@font-face with data URL should pass, got: {errors}")

    def test_sugarcube_style_blocks_pass(self):
        html = (REPO_ROOT / "test_stories" / "rpg-sandbox" / "build" / "story.html").read_text()
        _, styles, _ = extract_blocks(html)
        for idx, (pos, attrs, content) in enumerate(styles):
            if not content.strip():
                continue
            errors = validate_css(content)
            self.assertEqual(
                errors, [],
                f"style block {idx} ({attrs.get('id')}) should be valid CSS, "
                f"got: {_format_errors(errors)}",
            )

    def test_broken_css_detected(self):
        # tinycss2 flags a numeric token where a property name (ident) is
        # expected — a genuine CSS error that survives tinycss2's lenient
        # auto-closing of braces.
        css = 'a { 1: red }'
        errors = validate_css(css)
        self.assertTrue(errors, "malformed CSS property name should produce a parse error")
        self.assertIn("parse error", errors[0]["message"].lower())


class TestSugarCubeMacroLeak(unittest.TestCase):

    def test_detects_macro_inside_js(self):
        js = 'var x = 1; <<set $flag to 1>> doThing(); <</if>>'
        errors = check_unescaped_macros_in_js(js)
        self.assertTrue(errors, "unescaped <<set>> macro in JS should be detected")
        self.assertEqual(errors[0]["severity"], SEV_ERROR)
        self.assertIn("set", errors[0]["message"])

    def test_does_not_flag_arithmetic_shift(self):
        js = ('var a = b << 2; var c = d >> 1; '
              'if (x < y) { z = a << b >> c; } '
              'var n = 1 << 2 >> 3;')
        errors = check_unescaped_macros_in_js(js)
        self.assertEqual(errors, [],
                         f"arithmetic bit-shifts should not be flagged, got: {errors}")

    def test_does_not_flag_macro_names_in_strings(self):
        # The SugarCube engine has error messages containing macro names.
        js = 'this.error("<<else>> must be the final clause"); this.warn("<<track>> not found");'
        errors = check_unescaped_macros_in_js(js)
        self.assertEqual(errors, [],
                         f"macro names inside string literals should not be flagged, got: {errors}")

    def test_does_not_flag_sugarcube_engine_regex(self):
        # Regex literals in the engine must not be mistaken for macros.
        js = r'var r=/<script|<style|<link/i; var s=/^\s*class /;'
        errors = check_unescaped_macros_in_js(js)
        self.assertEqual(errors, [])


class TestPassageData(unittest.TestCase):

    def test_valid_passages_pass(self):
        html = (REPO_ROOT / "test_stories" / "rpg-sandbox" / "build" / "story.html").read_text()
        passages = extract_passages(html)
        self.assertGreater(len(passages), 0, "compiled story should have passage data")
        errors = check_passage_data(passages)
        self.assertEqual(errors, [],
                         f"known-good passages should pass, got: {_format_errors(errors)}")

    def test_missing_name_flagged(self):
        passages = [((1, 0), {"pid": "1", "tags": ""}, "content")]
        errors = check_passage_data(passages)
        self.assertTrue(any("missing required attribute 'name'" in e["message"] for e in errors))

    def test_missing_pid_flagged(self):
        passages = [((1, 0), {"name": "Start", "tags": ""}, "content")]
        errors = check_passage_data(passages)
        self.assertTrue(any("missing required attribute 'pid'" in e["message"] for e in errors))

    def test_bad_pid_flagged(self):
        passages = [((1, 0), {"pid": "abc", "name": "Start", "position": "100,100", "size": "100,100"}, "")]
        errors = check_passage_data(passages)
        self.assertTrue(any("pid is not a positive integer" in e["message"] for e in errors))

    def test_bad_position_flagged(self):
        passages = [((1, 0), {"pid": "1", "name": "Start", "position": "bad", "size": "100,100"}, "")]
        errors = check_passage_data(passages)
        self.assertTrue(any("position not 'X,Y'" in e["message"] for e in errors))

    def test_duplicate_pid_flagged(self):
        html = ('<tw-passagedata pid="1" name="A" position="100,100" size="100,100">a</tw-passagedata>'
                '<tw-passagedata pid="1" name="B" position="200,100" size="100,100">b</tw-passagedata>')
        errors = validate_compiled_html(html)
        self.assertTrue(any("duplicate" in e["message"] for e in errors))


class TestHTMLEntities(unittest.TestCase):

    def test_valid_entities_pass(self):
        html_text = '<p>Tom &amp; Jerry &#169; &#x2014;</p>'
        errors = check_broken_html_entities(html_text)
        self.assertEqual(errors, [])

    def test_bare_ampersand_flagged(self):
        html_text = '<p>Tom & Jerry</p>'
        errors = check_broken_html_entities(html_text)
        self.assertTrue(errors, "bare & should be flagged")
        self.assertEqual(errors[0]["severity"], SEV_WARNING)

    def test_js_logical_and_not_flagged(self):
        # ``&&`` inside JS must not be reported as a broken entity, because
        # entity checks only run on text outside script/style blocks.
        html = '<script>if (a && b) { c(); }</script><p>valid &amp; text</p>'
        _, _, html_text = extract_blocks(html)
        errors = check_broken_html_entities(html_text)
        self.assertEqual(errors, [], f"JS && should not be flagged, got: {errors}")


class TestKnownGoodCompiledHTML(unittest.TestCase):
    """The full validation pipeline must pass cleanly against known-good
    compiled SugarCube HTML files — including the heavy minified engine code
    full of regex literals."""

    def _check(self, path: Path):
        self.assertTrue(path.exists(), f"known-good HTML file missing: {path}")
        html = path.read_text(encoding="utf-8")
        errors = validate_compiled_html(html)
        if errors:
            self.fail(f"known-good compiled HTML {path} produced validation errors:\n"
                      f"{_format_errors(errors)}")

    def test_fixture_story_html(self):
        self._check(REPO_ROOT / "tests" / "fixtures" / "test_story.html")

    def test_compiled_rpg_sandbox_story_html(self):
        self._check(REPO_ROOT / "test_stories" / "rpg-sandbox" / "build" / "story.html")

    def test_compiled_cartographers_dilemma_html(self):
        self._check(REPO_ROOT / "examples" / "the-cartographers-dilemma" / "the-cartographers-dilemma.html")


class TestDetectsRealErrors(unittest.TestCase):
    """Sanity: the pipeline must actually catch injected errors, proving the
    tests are not vacuously passing."""

    def test_detects_broken_js_in_compiled_html(self):
        base = (REPO_ROOT / "tests" / "fixtures" / "test_story.html").read_text()
        # Inject a syntax error into a script block.
        broken = base.replace(
            "window.SugarCube = {",
            "window.SugarCube = { [UNCLOSED ",
        )
        errors = validate_compiled_html(broken)
        js_errors = [e for e in errors if e.get("section") == "js"]
        self.assertTrue(js_errors, "broken JS should be detected in the pipeline")

    def test_detects_macro_leak_in_compiled_html(self):
        base = (REPO_ROOT / "tests" / "fixtures" / "test_story.html").read_text()
        # Inject an unescaped macro into a script block.
        broken = base.replace(
            "document.querySelectorAll",
            "<<set $x to 1>> document.querySelectorAll",
        )
        errors = validate_compiled_html(broken)
        leak_errors = [e for e in errors if e.get("section") == "macro-leak"]
        self.assertTrue(leak_errors, "macro leak should be detected in the pipeline")

    def test_detects_missing_passage_name(self):
        html = '<tw-passagedata pid="1" tags="" position="100,100" size="100,100">content</tw-passagedata>'
        errors = validate_compiled_html(html)
        self.assertTrue(any("missing required attribute 'name'" in e["message"] for e in errors))


if __name__ == "__main__":
    unittest.main()

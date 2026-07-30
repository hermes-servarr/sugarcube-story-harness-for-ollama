r"""Post-compile JS validation tests for compiled SugarCube story HTML.

Validates that ``harness.validation.validate_compiled_html`` correctly
distinguishes **real** JS errors from the false positives that VS Code's JS
language service (tsserver) reports on minified SugarCube/jQuery engine code.

Background — the 16 VS Code JS "errors":
    The compiled story HTML bundles the SugarCube engine and jQuery verbatim
    (injected by Tweego from the off-limits ``/opt/data/bin/storyformats/``
    bundle).  These minified engine blocks contain regex literals with a ``/``
    inside the pattern, e.g.::

        lookahead:/(?:\/(%|\*)(?:(?:.|\n)*?)\1\/)|(?:<!--(?:(?:.|\n)*?)-->)/gm

    VS Code's tsserver mis-tokenises the ``/`` inside the regex literal (it
    thinks it is a division operator) and reports cascading syntax errors
    downstream — ~16 false positives.  A real JS engine (``node --check``,
    V8) and a spec-compliant parser (acorn) tokenise regex literals correctly
    and report **zero** errors, which is the truth: the JS runs fine in every
    browser.

The fix:
    ``validate_compiled_html`` extracts each ``<script>`` block with a real
    HTML parser (so regex literals containing ``<script|<style|<link`` are not
    mistaken for tags) and validates each body with ``node --check``.  It
    therefore reports 0 errors for valid engine bundles and surfaces genuine
    JS errors from the harness's own generators.

Run with::

    uv run python -m pytest tests/test_compiled_html_js.py -v
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from harness.validation import validate_compiled_html

REPO_ROOT = Path(__file__).resolve().parent.parent

# The known-good tweego-compiled story shipped with the repo.
COMPILED_STORY = (
    REPO_ROOT
    / "examples"
    / "the-cartographers-dilemma"
    / "the-cartographers-dilemma.html"
)

_HAS_NODE = shutil.which("node") is not None


def _write_tmp_html(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return Path(f.name)


# ── The headline test: the compiled story has 0 real JS errors ──────────────

@pytest.mark.skipif(
    not COMPILED_STORY.exists(),
    reason="compiled story HTML not present",
)
def test_compiled_story_has_zero_js_errors():
    """The tweego-compiled story HTML (which VS Code reports 16 JS errors on)
    must validate with zero real JS errors — confirming those 16 are tsserver
    false positives on regex literals, not genuine problems."""
    r = validate_compiled_html(COMPILED_STORY)
    assert r.ok, (
        f"Expected 0 JS errors but got {len(r.errors)}:\n"
        + "\n".join(f"  [{e.code}] {e.message} ({e.passage})" for e in r.errors)
    )
    assert r.errors == []


# ── Regex-literal false positive must NOT be reported ───────────────────────

@pytest.mark.skipif(not _HAS_NODE, reason="node not available")
def test_regex_literal_not_reported():
    """The exact regex literal VS Code mis-parses must produce 0 errors."""
    html = (
        "<html><head>"
        "<script id='engine'>"
        "var re=/(?:\\/(%|\\*)(?:(?:.|\\n)*?)\\1\\/)"
        "|(?:<!--(?:(?:.|\\n)*?)-->)/gm;"
        "re.test('x');"
        "</script></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert r.ok
        assert r.errors == []
    finally:
        p.unlink()


# ── Genuine JS error IS detected (the check is not a no-op) ─────────────────

@pytest.mark.skipif(not _HAS_NODE, reason="node not available")
def test_genuine_js_error_detected():
    """A real syntax error must be reported so the check catches future
    harness-generated JS breakage."""
    html = (
        "<html><head>"
        "<script id='bad'>function broken( { return; }</script>"
        "</head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert not r.ok
        assert len(r.errors) >= 1
        assert r.errors[0].code == "html_js_syntax"
        assert "SyntaxError" in r.errors[0].message
        # the script id is annotated onto the issue
        assert r.errors[0].passage is not None
        assert "script#bad" in r.errors[0].passage
    finally:
        p.unlink()


# ── Empty script blocks are skipped ──────────────────────────────────────────

@pytest.mark.skipif(not _HAS_NODE, reason="node not available")
def test_empty_script_skipped():
    """Empty / whitespace-only <script> blocks (common in compiled output)
    must not raise errors."""
    html = (
        "<html><head><script id='empty'></script>"
        "<script id='ws'>   \n  </script></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert r.ok
        assert r.errors == []
    finally:
        p.unlink()


# ── Multiple script blocks each checked independently ───────────────────────

@pytest.mark.skipif(not _HAS_NODE, reason="node not available")
def test_multiple_blocks_checked():
    """One valid + one broken script → exactly the broken block is flagged."""
    html = (
        "<html><head>"
        "<script id='good'>var x = 1;</script>"
        "<script id='bad'>var y = ;</script>"
        "</head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert not r.ok
        assert len(r.errors) >= 1
        assert all(e.passage == "script#bad" for e in r.errors)
    finally:
        p.unlink()


# ── Regression: VS-Code-confusing regex with <script inside ─────────────────

@pytest.mark.skipif(not _HAS_NODE, reason="node not available")
def test_regex_containing_script_substring():
    """A regex literal that *contains* ``<script|<style|<link`` must not be
    mistaken for a real tag by the block extractor — it is a single script."""
    html = (
        "<html><head>"
        "<script id='lib'>"
        "var r = /<script|<style|<link/i;"
        "var s = /<style|<link/i.test('a');"
        "</script></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert r.ok, f"regex-with-<script should be valid: {[e.message for e in r.errors]}"
        assert r.errors == []
    finally:
        p.unlink()

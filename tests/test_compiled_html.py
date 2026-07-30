"""Post-compile CSS fixer + validator tests for compiled SugarCube story HTML.

Validates that:

1. ``harness.compile.fix_compiled_css`` — the post-compile CSS patcher wired
   into ``compile_story`` — eliminates the 9 SugarCube-bundled CSS linter
   warnings (3 ``vendorPrefix`` + 6 ``unknownProperties``) that VS Code reports
   on freshly compiled story HTML.  The warnings originate from SugarCube's
   bundled CSS (injected verbatim by Tweego from the off-limits
   ``/opt/data/bin/storyformats/`` bundle), not from hand-authored content.

2. ``harness.validation.validate_compiled_html`` — extended in this task to
   also lint ``<style>`` blocks — reports exactly those 9 warnings on
   unpatched output and zero warnings on patched output.

Background — the 9 VS Code CSS warnings:
    * vendorPrefix (3): rules using ``-webkit-appearance:X`` with no matching
      standard ``appearance:X``.  Found in normalize-reset rules for buttons,
      ``input[type=search]``, and the ``input[type=range]`` track.  Rules whose
      selector contains a ``::-webkit-`` pseudo-element (e.g.
      ``::-webkit-slider-thumb``) are NOT flagged by VS Code and NOT patched
      (``appearance`` on ``::-webkit-*`` would itself be an unknown-property
      warning), so the fixer and validator both skip them.
    * unknownProperties (6): ``speak:none`` declarations in fontello icon-font
      rules.  ``speak`` is a valid CSS2 aural property but VS Code's linter
      does not recognise it.  Removing it has no visual effect on icon glyphs.

The fix (in ``harness/compile.py::fix_compiled_css``):
    After Tweego writes ``story.html``, read it back and patch every
    ``<style>`` block: append ``appearance:X`` after each
    ``-webkit-appearance:X`` (skipping ``::-webkit-*`` selectors) and remove
    every ``speak:...`` declaration.  Write the patched HTML back.  Idempotent.

Run with::

    uv run python -m pytest tests/test_compiled_html.py -v
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from harness.compile import fix_compiled_css
from harness.validation import validate_compiled_html

REPO_ROOT = Path(__file__).resolve().parent.parent

# The known-good tweego-compiled story shipped with the repo (already patched
# by fix_compiled_css during the prior compile that produced it).
COMPILED_STORY = (
    REPO_ROOT
    / "examples"
    / "the-cartographers-dilemma"
    / "the-cartographers-dilemma.html"
)


def _write_tmp_html(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return Path(f.name)


# ── Headline: the shipped compiled story is warning-free ───────────────────

@pytest.mark.skipif(
    not COMPILED_STORY.exists(),
    reason="compiled story HTML not present",
)
def test_compiled_story_has_zero_css_warnings():
    """The shipped compiled story HTML (patched by fix_compiled_css at compile
    time) must validate with zero CSS warnings — confirming the fixer
    eliminated all 9 SugarCube-bundled warnings."""
    r = validate_compiled_html(COMPILED_STORY)
    assert r.warnings == [], (
        f"Expected 0 CSS warnings but got {len(r.warnings)}:\n"
        + "\n".join(
            f"  [{w.code}] {w.message} ({w.passage})" for w in r.warnings
        )
    )


# ── fix_compiled_css: vendor-prefix fix ──────────────────────────────────────

def test_fix_adds_appearance_for_webkit_appearance():
    """A rule with ``-webkit-appearance:X`` and no standard ``appearance`` must
    get ``appearance:X`` appended right after it."""
    html = (
        "<html><head>"
        '<style id="s">button{-webkit-appearance:button;color:red}</style>'
        "</head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        out = p.read_text(encoding="utf-8")
        assert n == 1
        assert "appearance:button" in out
        # original -webkit-appearance preserved
        assert "-webkit-appearance:button" in out
    finally:
        p.unlink()


def test_fix_skips_webkit_pseudo_selectors():
    """Selectors containing ``::-webkit-`` (pseudo-elements) must NOT get a
    standard ``appearance`` added — VS Code does not flag them, and
    ``appearance`` on a ``::-webkit-*`` pseudo would itself be a warning."""
    html = (
        "<html><head>"
        '<style id="s">'
        "input[type=range]::-webkit-slider-thumb{-webkit-appearance:none}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 0
        out = p.read_text(encoding="utf-8")
        # unchanged — no appearance: injected
        assert "appearance:none" not in out.replace("-webkit-appearance:none", "")
        assert "-webkit-appearance:none" in out
    finally:
        p.unlink()


def test_fix_does_not_duplicate_when_appearance_present():
    """A rule that already has a standard ``appearance`` declaration must not
    get a duplicate added."""
    html = (
        "<html><head>"
        '<style id="s">'
        "button{-webkit-appearance:button;appearance:button;color:red}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 0
    finally:
        p.unlink()


def test_fix_patches_multiple_vendor_rules():
    """Multiple vendor-prefix rules in one style block are all patched."""
    html = (
        "<html><head>"
        '<style id="s">'
        "button{-webkit-appearance:button}"
        "input[type=search]{-webkit-appearance:textfield}"
        "input[type=range]{-webkit-appearance:none}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 3
        out = p.read_text(encoding="utf-8")
        # Count only the inserted standard ``appearance:`` (preceded by ``;``),
        # not the ``-webkit-appearance:X`` declarations which also contain the
        # ``appearance:X`` substring.
        assert out.count(";appearance:button") == 1
        assert out.count(";appearance:textfield") == 1
        assert out.count(";appearance:none") == 1
    finally:
        p.unlink()


# ── fix_compiled_css: unknown-property (speak) fix ─────────────────────────

def test_fix_removes_speak_none():
    """``speak:none`` declarations must be removed entirely."""
    html = (
        "<html><head>"
        '<style id="s">'
        ".icon{font-family:fontello;speak:none;font-style:normal}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 1
        out = p.read_text(encoding="utf-8")
        assert "speak:none" not in out
        # surrounding declarations preserved
        assert "font-family:fontello" in out
        assert "font-style:normal" in out
    finally:
        p.unlink()


def test_fix_removes_speak_with_any_value():
    """``speak`` with any value (not just none) is removed."""
    html = (
        "<html><head>"
        '<style id="s">'
        ".icon{font-family:fontello;speak:normal;font-style:normal}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 1
        assert "speak:normal" not in p.read_text(encoding="utf-8")
    finally:
        p.unlink()


# ── fix_compiled_css: idempotency ────────────────────────────────────────────

def test_fix_is_idempotent():
    """A second call on already-fixed output must apply 0 patches and not
    rewrite the file."""
    html = (
        "<html><head>"
        '<style id="s">'
        "button{-webkit-appearance:button}"
        ".icon{speak:none}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        n1 = fix_compiled_css(p)
        mtime1 = p.stat().st_mtime_ns
        n2 = fix_compiled_css(p)
        mtime2 = p.stat().st_mtime_ns
        assert n1 == 2
        assert n2 == 0
        # file not rewritten on the no-op second call
        assert mtime2 == mtime1
    finally:
        p.unlink()


# ── fix_compiled_css: end-to-end on a SugarCube-like CSS sample ──────────────

def test_fix_eliminates_all_warnings_on_sample():
    """A CSS sample mimicking the real SugarCube bundle (both warning classes,
    incl. a ::-webkit- pseudo that must be skipped) must produce zero validator
    warnings after the fixer runs."""
    html = (
        "<html><head>"
        '<style id="style-normalize" type="text/css">'
        "button,input[type=reset],input[type=submit]"
        "{-webkit-appearance:button;cursor:pointer}"
        "input[type=search]{-webkit-appearance:textfield;box-sizing:content-box}"
        "input[type=search]::-webkit-search-cancel-button,"
        "input[type=search]::-webkit-search-decoration"
        "{-webkit-appearance:none}"
        "</style>"
        '<style id="style-core" type="text/css">'
        "input[type=range]{-webkit-appearance:none;min-height:1.2em}"
        "input[type=range]::-webkit-slider-thumb"
        "{-webkit-appearance:none;background:#35a}"
        ".error-view>.error:before,[data-icon]:before"
        "{font-family:tme-fa-icons;speak:none;font-style:normal}"
        ".saves .empty{speak:none;-webkit-user-select:none}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        # before fix: validator should report the warnings
        r0 = validate_compiled_html(p)
        vendor0 = [w for w in r0.warnings if w.code == "html_vendor_prefix"]
        speak0 = [w for w in r0.warnings if w.code == "html_unknown_property"]
        assert len(vendor0) == 3, f"expected 3 vendor warnings, got {len(vendor0)}"
        assert len(speak0) == 2, f"expected 2 speak warnings, got {len(speak0)}"

        n = fix_compiled_css(p)
        # 3 vendor (the ::-webkit- ones skipped) + 2 speak = 5 patches
        assert n == 5, f"expected 5 patches, got {n}"

        # after fix: validator should report zero warnings
        r1 = validate_compiled_html(p)
        assert r1.warnings == [], (
            f"Expected 0 warnings after fix but got {len(r1.warnings)}:\n"
            + "\n".join(
                f"  [{w.code}] {w.message} ({w.passage})"
                for w in r1.warnings
            )
        )
    finally:
        p.unlink()


# ── validator: detects the 9 warnings on the original unpatched CSS ─────────

def _original_compiled_story() -> Path | None:
    """Return a temp file holding the compiled story HTML with the ORIGINAL
    (unpatched) SugarCube-bundled CSS — i.e. before fix_compiled_css ran.

    The shipped file in the repo is already patched, so we recover the
    pristine version from git (``git show HEAD~1:<path>``), which contains the
    raw Tweego output with all 9 CSS warnings present.  Returns None if git
    is unavailable or the file is not tracked.
    """
    import subprocess

    if not COMPILED_STORY.exists():
        return None
    rel = str(COMPILED_STORY.relative_to(REPO_ROOT))
    try:
        r = subprocess.run(
            ["git", "show", f"HEAD~1:{rel}"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return _write_tmp_html(r.stdout)


def test_validator_flags_unpatched_sugarcube_css():
    """The validator must report exactly the 9 SugarCube-bundled CSS warnings
    (3 vendor-prefix + 6 unknown-property) on the pristine (unpatched) Tweego
    output recovered from git HEAD."""
    p = _original_compiled_story()
    if p is None:
        pytest.skip("could not recover original compiled story HTML from git")
    try:
        r = validate_compiled_html(p)
        from collections import Counter
        codes = Counter(w.code for w in r.warnings)
        assert codes["html_vendor_prefix"] == 3, (
            f"expected 3 vendor warnings, got {codes.get('html_vendor_prefix', 0)}"
        )
        assert codes["html_unknown_property"] == 6, (
            f"expected 6 speak warnings, got {codes.get('html_unknown_property', 0)}"
        )
        assert len(r.warnings) == 9
    finally:
        p.unlink()


def test_fixer_then_validator_on_original_story():
    """End-to-end: take the pristine unpatched Tweego output from git, run the
    CSS fixer on it, then confirm the validator reports zero warnings.  This
    proves the fixer eliminates exactly the warnings the validator detects."""
    p = _original_compiled_story()
    if p is None:
        pytest.skip("could not recover original compiled story HTML from git")
    try:
        r0 = validate_compiled_html(p)
        assert len(r0.warnings) == 9, f"expected 9 pre-fix warnings, got {len(r0.warnings)}"
        n = fix_compiled_css(p)
        assert n >= 9, f"expected at least 9 patches, got {n}"
        r1 = validate_compiled_html(p)
        assert r1.warnings == [], (
            f"expected 0 warnings after fix but got {len(r1.warnings)}:\n"
            + "\n".join(
                f"  [{w.code}] {w.message} ({w.passage})" for w in r1.warnings
            )
        )
    finally:
        p.unlink()


# ── validator: clean CSS produces no warnings ────────────────────────────────

def test_validator_clean_css_no_warnings():
    """CSS without -webkit-appearance or speak produces no warnings."""
    html = (
        "<html><head>"
        '<style id="s">body{color:red;margin:0}.x{display:block}</style>'
        "</head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        assert r.warnings == []
        assert r.ok
    finally:
        p.unlink()


# ── validator: webkit-pseudo selectors are not flagged ──────────────────────

def test_validator_skips_webkit_pseudo_selectors():
    """``-webkit-appearance`` on a ``::-webkit-*`` selector must NOT be flagged
    as a vendor-prefix warning (mirrors the fixer and VS Code)."""
    html = (
        "<html><head>"
        '<style id="s">'
        "input[type=range]::-webkit-slider-thumb{-webkit-appearance:none}"
        "</style></head></html>"
    )
    p = _write_tmp_html(html)
    try:
        r = validate_compiled_html(p)
        vendor = [w for w in r.warnings if w.code == "html_vendor_prefix"]
        assert vendor == [], "::-webkit- selector should not be flagged"
    finally:
        p.unlink()


# ── fixer + validator round-trip on the shipped story ───────────────────────

@pytest.mark.skipif(
    not COMPILED_STORY.exists(),
    reason="compiled story HTML not present",
)
def test_fixer_roundtrip_on_compiled_story():
    """Running fix_compiled_css on the already-patched shipped story must be a
    no-op (0 patches) and the validator must still report 0 warnings — proving
    the shipped output is in the fixed, warning-free steady state."""
    # work on a temp copy so we never mutate the shipped file
    html = COMPILED_STORY.read_text(encoding="utf-8")
    p = _write_tmp_html(html)
    try:
        n = fix_compiled_css(p)
        assert n == 0, "already-patched story should need 0 patches"
        r = validate_compiled_html(p)
        assert r.warnings == []
        assert r.ok
    finally:
        p.unlink()

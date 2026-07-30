"""Unit test: compiled story HTML is free of JS errors and CSS warnings.

This test compiles/loads a representative story HTML file and validates the
output is free of JS errors and CSS warnings using **independent** parser /
linter tooling — ``acorn`` (a spec-compliant JS parser) for JavaScript and
``css-tree`` (a CSS parser/linter) for CSS — rather than the harness's own
``validate_compiled_html`` (which uses ``node --check`` + a bespoke CSS
linter).  Using independent parsers is a stronger guarantee: it cross-checks
the harness validator against a second, unrelated implementation.

Background — why independent parsers matter:
    The compiled story HTML bundles the SugarCube engine and jQuery verbatim
    (injected by Tweego from the off-limits ``/opt/data/bin/storyformats/``
    bundle).  These minified engine blocks contain regex literals with a ``/``
    inside the pattern.  VS Code's JS language service (tsserver) mis-tokenises
    the ``/`` as a division operator and reports ~16 cascading false-positive
    "errors".  A spec-compliant parser (``acorn``) and a real JS engine
    (``node --check``) tokenise regex literals correctly and report **zero**
    errors.  This test uses ``acorn`` as an independent confirmation that the
    JS is genuinely error-free.

    Likewise the SugarCube bundled CSS produces 9 VS-Code CSS-linter warnings
    (3 ``vendorPrefix`` for ``-webkit-appearance`` without standard
    ``appearance`` + 6 ``unknownProperties`` for ``speak``).  The harness's
    post-compile CSS fixer (``fix_compiled_css``) removes them; this test
    confirms the *fixed* output is warning-free via an independent CSS parser
    (``css-tree``).

Block extraction:
    ``<script>`` and ``<style>`` blocks are extracted with the harness's
    ``_BlockExtractor`` (a real HTML parser) — NOT a regex — so that regex
    literals containing ``<script|<style`` substrings in the minified engine
    bundles are not mistaken for real tags (the false-positive source).

Tooling bootstrap:
    ``acorn`` and ``css-tree`` are installed via ``npm`` into a cache dir on
    first run (idempotent — ``npm`` skips re-download when already present).
    This means the test runs in the existing ``pytest`` suite with **no
    additional manual setup steps**: the first invocation bootstraps its own
    JS tooling; subsequent invocations are fast (cache hit).  The test is
    skipped (not failed) if ``node`` or ``npm`` are unavailable on the host.

Run with::

    uv run python -m pytest tests/test_compiled_html_lint.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from harness.validation import _BlockExtractor

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent

# The known-good tweego-compiled story shipped with the repo (already patched
# by ``fix_compiled_css`` during the prior compile that produced it).
COMPILED_STORY = (
    REPO_ROOT
    / "examples"
    / "the-cartographers-dilemma"
    / "the-cartographers-dilemma.html"
)

# The Node linter script shipped alongside this test.
LINTER_JS = TESTS_DIR / "_lint_compiled_blocks.js"

# Cache dir for the npm-installed acorn + css-tree modules.  Lives under the
# repo's pytest cache so it persists across runs (fast on repeat) but is
# self-contained and cleaned by ``pytest --cache-clear`` or rm -rf.
_LINT_MODULES_DIR = REPO_ROOT / ".pytest_cache" / "lint_node_modules"

_HAS_NODE = shutil.which("node") is not None
_HAS_NPM = shutil.which("npm") is not None


# ── Tooling bootstrap ─────────────────────────────────────────────────────────

def _ensure_lint_modules() -> Path:
    """Install ``acorn`` + ``css-tree`` into a cache dir if missing; return the
    ``node_modules`` path.  Idempotent — ``npm install`` is a no-op when the
    packages are already present.  Raises ``RuntimeError`` on install failure
    so the caller can surface a clear error rather than a confusing import
    error from the linter script."""
    nm = _LINT_MODULES_DIR / "node_modules"
    acorn_ok = (nm / "acorn" / "package.json").is_file()
    csstree_ok = (nm / "css-tree" / "package.json").is_file()
    if acorn_ok and csstree_ok:
        return nm  # cache hit — nothing to do
    _LINT_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    # package.json so npm installs into our cache dir (not a parent).
    pkg = _LINT_MODULES_DIR / "package.json"
    if not pkg.is_file():
        pkg.write_text('{"name":"lint-cache","private":true,"version":"1.0.0"}\n',
                       encoding="utf-8")
    r = subprocess.run(
        ["npm", "install", "--no-save", "--no-audit", "--no-fund",
         "acorn", "css-tree"],
        cwd=str(_LINT_MODULES_DIR),
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(
            "npm install of acorn + css-tree failed:\n" + r.stderr
        )
    if not (nm / "acorn" / "package.json").is_file() or not (nm / "css-tree" / "package.json").is_file():
        raise RuntimeError(
            "npm install reported success but acorn/css-tree are missing in "
            + str(nm)
        )
    return nm


def _run_linter(node_modules: Path, manifest_path: Path) -> dict:
    """Run the Node linter over the block manifest; return the parsed JSON
    report.  Raises ``RuntimeError`` if node fails to run the linter."""
    r = subprocess.run(
        ["node", str(LINTER_JS), str(node_modules), str(manifest_path)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(
            "node linter failed (exit %d):\n%s" % (r.returncode, r.stderr)
        )
    return json.loads(r.stdout)


def _build_manifest(html_path: Path) -> Path:
    """Extract <script>/<style> blocks from ``html_path`` with a real HTML
    parser and write a JSON manifest (the linter's input) to a temp file.
    Returns the manifest path.  Uses the harness's ``_BlockExtractor`` so
    regex literals containing ``<script|<style`` substrings are not mistaken
    for real tags."""
    html = html_path.read_text(encoding="utf-8")
    ext = _BlockExtractor()
    ext.feed(html)
    manifest = {
        "scripts": [
            {"id": attrs.get("id", ""), "body": body}
            for _pos, attrs, body in ext.scripts
        ],
        "styles": [
            {"id": attrs.get("id", ""), "body": body}
            for _pos, attrs, body in ext.styles
        ],
    }
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(manifest, f)
    f.close()
    return Path(f.name)


def _format_report(report: dict) -> str:
    """Render a linter report as a clear, readable multi-line list of issues
    for assertion-failure messages."""
    lines = []
    for e in report.get("js_errors", []):
        loc = f" (line {e['line']}:{e['col']})" if e.get("line") else ""
        lines.append(f"  JS ERROR   [{e['id']}] {e['message']}{loc}")
    for e in report.get("css_errors", []):
        lines.append(f"  CSS ERROR  [{e['id']}] {e['message']}")
    for w in report.get("css_warnings", []):
        lines.append(
            f"  CSS WARN   [{w['id']}] ({w['kind']}) {w['message']} "
            f"[selector: {w['selector']}]"
        )
    return "\n".join(lines) if lines else "(no issues)"


# ── Skip markers ──────────────────────────────────────────────────────────────

requires_node = pytest.mark.skipif(
    not _HAS_NODE, reason="node not available — JS/CSS linter needs node"
)
requires_npm = pytest.mark.skipif(
    not _HAS_NPM, reason="npm not available — cannot bootstrap acorn/css-tree"
)
requires_compiled_story = pytest.mark.skipif(
    not COMPILED_STORY.exists(), reason="compiled story HTML not present"
)


# ── Headline: the shipped compiled story is error-free + warning-free ──────────

@requires_compiled_story
@requires_node
@requires_npm
def test_compiled_story_is_error_and_warning_free():
    """The shipped compiled story HTML must validate with **zero** JS errors
    (acorn) and **zero** CSS warnings (css-tree).  This is the headline
    acceptance criterion: the fixed compiled output is clean against
    independent parser/linter tooling."""
    node_modules = _ensure_lint_modules()
    manifest = _build_manifest(COMPILED_STORY)
    try:
        report = _run_linter(node_modules, manifest)
    finally:
        manifest.unlink(missing_ok=True)

    assert not report["js_errors"], (
        f"Expected 0 JS errors (acorn) but got {len(report['js_errors'])}:\n"
        + _format_report(report)
    )
    assert not report["css_errors"], (
        f"Expected 0 CSS parse errors (css-tree) but got "
        f"{len(report['css_errors'])}:\n" + _format_report(report)
    )
    assert not report["css_warnings"], (
        f"Expected 0 CSS warnings (css-tree) but got "
        f"{len(report['css_warnings'])}:\n" + _format_report(report)
    )
    # Sanity: the linter actually checked something (not a no-op).
    assert report["scripts_checked"] >= 1, "linter checked no script blocks"
    assert report["styles_checked"] >= 1, "linter checked no style blocks"


# ── Negative: reintroduced JS error IS caught ─────────────────────────────────

@requires_node
@requires_npm
def test_linter_catches_reintroduced_js_error():
    """If a JS syntax error were reintroduced into a <script> block, the
    linter MUST report it — proving the check is not a no-op for JS.  This
    satisfies acceptance criterion (3): the test would fail if errors were
    reintroduced."""
    node_modules = _ensure_lint_modules()
    manifest = _build_manifest(COMPILED_STORY)
    try:
        # Inject a genuine JS syntax error into the first non-empty script.
        import json as _json
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        for blk in data["scripts"]:
            if blk["body"].strip():
                blk["body"] = "function broken( { return; }\n" + blk["body"]
                break
        manifest.write_text(_json.dumps(data), encoding="utf-8")
        report = _run_linter(node_modules, manifest)
    finally:
        manifest.unlink(missing_ok=True)

    assert report["js_errors"], (
        "Expected the linter to catch the injected JS syntax error, but it "
        "reported none.  The check may be a no-op for JS.\n"
        + _format_report(report)
    )
    assert "SyntaxError" in report["js_errors"][0]["message"] or "Unexpected" in report["js_errors"][0]["message"], (
        f"Injected JS error message looks wrong: {report['js_errors'][0]['message']!r}"
    )


# ── Negative: reintroduced CSS warning IS caught ──────────────────────────────

@requires_compiled_story
@requires_node
@requires_npm
def test_linter_catches_reintroduced_css_warning():
    """If a CSS warning (``-webkit-appearance`` without standard
    ``appearance``) were reintroduced into a <style> block, the linter MUST
    report it — proving the check is not a no-op for CSS.  This satisfies
    acceptance criterion (3): the test would fail if warnings were
    reintroduced."""
    node_modules = _ensure_lint_modules()
    manifest = _build_manifest(COMPILED_STORY)
    try:
        import json as _json
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        # Inject a vendor-prefix warning into the first non-empty style block.
        injected = (
            "button{-webkit-appearance:button;color:red}"
        )
        for blk in data["styles"]:
            if blk["body"].strip():
                blk["body"] = injected + blk["body"]
                break
        manifest.write_text(_json.dumps(data), encoding="utf-8")
        report = _run_linter(node_modules, manifest)
    finally:
        manifest.unlink(missing_ok=True)

    vendor = [w for w in report["css_warnings"] if w["kind"] == "vendor_prefix"]
    assert vendor, (
        "Expected the linter to catch the injected -webkit-appearance vendor "
        "warning, but it reported none.\n" + _format_report(report)
    )
    assert any("appearance" in w["message"] for w in vendor), (
        f"Vendor warning message looks wrong: {vendor[0]['message']!r}"
    )


# ── Negative: reintroduced speak unknown-property warning IS caught ────────────

@requires_compiled_story
@requires_node
@requires_npm
def test_linter_catches_reintroduced_speak_warning():
    """If a ``speak`` unknown-property CSS warning were reintroduced, the
    linter MUST report it.  Covers the second CSS warning class."""
    node_modules = _ensure_lint_modules()
    manifest = _build_manifest(COMPILED_STORY)
    try:
        import json as _json
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        injected = ".icon{font-family:fontello;speak:none;font-style:normal}"
        for blk in data["styles"]:
            if blk["body"].strip():
                blk["body"] = injected + blk["body"]
                break
        manifest.write_text(_json.dumps(data), encoding="utf-8")
        report = _run_linter(node_modules, manifest)
    finally:
        manifest.unlink(missing_ok=True)

    speak = [w for w in report["css_warnings"] if w["kind"] == "unknown_property"]
    assert speak, (
        "Expected the linter to catch the injected speak unknown-property "
        "warning, but it reported none.\n" + _format_report(report)
    )
    assert any("speak" in w["message"] for w in speak)


# ── Cross-check: matches harness validator on the unpatched original ──────────

@requires_compiled_story
@requires_node
@requires_npm
def test_linter_matches_harness_on_unpatched_original():
    """Cross-check the independent linter against the harness's own
    ``validate_compiled_html`` on the *unpatched* (pre-fixer) compiled story
    recovered from git HEAD.  Both must report the same 9 CSS warnings
    (3 vendor + 6 speak) and 0 JS errors — confirming the independent linter
    and the harness validator agree, and that the fixer eliminated exactly
    those warnings."""
    # Recover the pristine (unpatched) compiled story from git HEAD.
    rel = str(COMPILED_STORY.relative_to(REPO_ROOT))
    gr: subprocess.CompletedProcess
    try:
        gr = subprocess.run(
            ["git", "show", f"HEAD~1:{rel}"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        pytest.skip("could not run git to recover original compiled story")
    if gr.returncode != 0:
        pytest.skip("compiled story HTML not tracked in git HEAD")

    # Write the unpatched HTML to a temp file, build a manifest, run the linter.
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    )
    f.write(gr.stdout)
    f.close()
    unpatched = Path(f.name)
    try:
        node_modules = _ensure_lint_modules()
        manifest = _build_manifest(unpatched)
        try:
            report = _run_linter(node_modules, manifest)
        finally:
            manifest.unlink(missing_ok=True)

        # 0 JS errors (the regex-literal false positives are tsserver-only).
        assert not report["js_errors"], (
            "Unpatched story should have 0 JS errors (acorn):\n"
            + _format_report(report)
        )
        # Exactly 9 CSS warnings: 3 vendor_prefix + 6 unknown_property.
        from collections import Counter
        kinds = Counter(w["kind"] for w in report["css_warnings"])
        assert kinds["vendor_prefix"] == 3, (
            f"expected 3 vendor_prefix warnings on unpatched, "
            f"got {kinds.get('vendor_prefix', 0)}:\n" + _format_report(report)
        )
        assert kinds["unknown_property"] == 6, (
            f"expected 6 unknown_property (speak) warnings on unpatched, "
            f"got {kinds.get('unknown_property', 0)}:\n" + _format_report(report)
        )
        assert len(report["css_warnings"]) == 9
    finally:
        unpatched.unlink(missing_ok=True)

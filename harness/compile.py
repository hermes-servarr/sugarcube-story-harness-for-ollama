"""Tweego compile pipeline with pre-compile validation gate.

The pipeline writes a mirror of ``arcs/`` plus a generated ``StoryData.twee``
into ``.harness/cache/build_src/`` and feeds that directory to Tweego. This
leverages Tweego's native source-tree recursion (which auto-bundles .css /
.js / images / fonts / etc) instead of hand-concatenating one giant .tw file.
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
from pathlib import Path

from .media import media_markup, stage_media_for_build
from .models import HarnessConfig, StoryGraph
# TODO(settings-api): C0 — add SettingDef to this import once defined in models.py
# (P2 S1). _storysettings_twee and default_settings_defs reference it in type
# annotations (P3 §1/§3). Exact code:
#   from .models import HarnessConfig, SettingDef, StoryGraph
# Alphabetical position: HarnessConfig < SettingDef < StoryGraph.
from .project import ProjectPaths, load_slots, load_story
from .validation import run_validation


# Tweego treats both extensions identically — research notes both are valid
# Twee v3 source files.
PASSAGE_EXTENSIONS = ("*.tw", "*.twee")


def _embed_media(p: ProjectPaths, tw_content: str, rel_map: dict[str, dict[str, str]]) -> str:
    """
    Replace ``<!-- media:SLOT_ID -->`` with an img/audio/video tag pointing at
    the relative ``media/<file>`` path produced by :func:`stage_media_for_build`.
    Pending / unstaged slots are left as comments.
    """
    slots = load_slots(p)

    def replace_slot(m: re.Match) -> str:
        slot_id = m.group(1)
        slot = slots.slots.get(slot_id)
        staged = rel_map.get(slot_id)
        if slot is None or staged is None:
            return m.group(0)  # leave as-is (pending or missing on disk)
        return media_markup(slot, staged["src"], staged.get("poster", ""))

    return re.sub(r'<!-- media:(slot_[a-zA-Z0-9_]+) -->', replace_slot, tw_content)


def find_tweego(configured_path: str = "tweego") -> str | None:
    """
    Return the first usable tweego executable path, or None.
    Checks configured_path, then common install locations on Windows/Mac/Linux.
    """
    # Try the configured value first (handles both bare name in PATH and full path)
    if shutil.which(configured_path):
        return configured_path
    if Path(configured_path).is_file():
        return configured_path

    appdata    = os.environ.get("APPDATA", "")
    localdata  = os.environ.get("LOCALAPPDATA", "")
    home       = str(Path.home())

    candidates: list[str] = [
        # bare names (in PATH)
        "tweego.exe",
        "tweego",
        # Windows common installs
        rf"C:\tweego\tweego.exe",
        rf"C:\Program Files\tweego\tweego.exe",
        rf"C:\Program Files (x86)\tweego\tweego.exe",
        os.path.join(appdata,   "tweego", "tweego.exe"),
        os.path.join(localdata, "tweego", "tweego.exe"),
        os.path.join(home,      "tweego", "tweego.exe"),
        os.path.join(home,      "bin", "tweego.exe"),
        os.path.join(home,      "bin", "tweego"),
        # macOS / Linux
        "/usr/local/bin/tweego",
        "/usr/bin/tweego",
        os.path.join(home, ".local", "bin", "tweego"),
        # beside the project (if user dropped it in)
        "./tweego.exe",
        "./tweego",
        "./tweego/tweego.exe",
        "./tweego/tweego",
    ]

    for c in candidates:
        try:
            found = shutil.which(c) or (Path(c).is_file() and c)
            if found:
                return found
        except Exception:
            pass
    return None


def collect_passage_files(p: ProjectPaths) -> list[Path]:
    """Return every .tw / .twee passage file under arcs/."""
    files: list[Path] = []
    for pattern in PASSAGE_EXTENSIONS:
        files.extend(p.arcs_dir.rglob(pattern))
    return sorted(files)


def _format_sc_default(val) -> str:
    """Render a state-variable default as SugarCube source."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        # double-quoted string literal with escapes
        return '"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if val is None:
        return "null"
    # list/dict — fall back to JSON-ish notation SugarCube accepts.
    import json as _json
    return _json.dumps(val)


# TODO(prng-seed): S2 — add module-private _escape_sc_string(s: str) -> str
# helper here (P3 §3.2 I2). Escapes a raw string into a double-quoted JS string
# literal (escapes backslash then double quote, returning the literal
# INCLUDING surrounding double quotes). Semantics identical to the str branch
# of _format_sc_default above (line 110), factored to a single-purpose function
# for testability and decoupling so the hostile-seed unit test can call it
# directly without constructing a StateVariable. Both input and output are str
# — no new types introduced (P2 §3). P7 will uncomment the def/body below.
# def _escape_sc_string(s: str) -> str:
#     """Escape a raw string into a double-quoted JS string literal
#     (escapes backslash then double quote, returning the literal
#     including surrounding double quotes)."""
#     return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# TODO(prng-seed): S3 — change _storyinit_twee signature to accept the config:
#   def _storyinit_twee(graph: StoryGraph, cfg: HarnessConfig) -> str:
# Accepting cfg (not just cfg.prng_seed) matches the sibling _storydata_twee
# (cfg, ...) pattern and leaves room for future init-time config. Only
# cfg.prng_seed is read. The docstring below must be updated to mention the
# optional PRNG init line and the revised empty-return condition (no defaults
# AND no seed). See p3_interfaces.md §3.1 I1, p1_research.md §3.2. P7 will edit
# the def line and docstring.
def _storyinit_twee(graph: StoryGraph) -> str:
    """
    Emit a SugarCube StoryInit passage that initialises every declared default.

    Without this, story.json's declared defaults are honoured by the validator
    but never written to the compiled HTML — so passages that read $var before
    any setter would observe undefined at runtime.
    """
    lines: list[str] = []
    # TODO(prng-seed): S4 — when cfg.prng_seed is non-empty, prepend the PRNG
    # init line as the FIRST entry of `lines` so State.prng.init() runs before
    # any random()/either() consumer. Seed is quoted via _escape_sc_string.
    # Init line MUST precede any <<set>> defaults (SugarCube docs examples).
    # Empty seed = no init line (unchanged behavior). P7 will uncomment:
    #   if cfg.prng_seed:
    #       lines.append(f"<<run State.prng.init({_escape_sc_string(cfg.prng_seed)})>>")
    # See p3_interfaces.md §3.2, p1_research.md §3.2, p6 INV-3.
    for var, decl in sorted(graph.state_variables.items()):
        if decl.default is None:
            continue
        lines.append(f"<<set {var} to {_format_sc_default(decl.default)}>>")
    # TODO(settings-api): C1 — after the <<set>> defaults loop, append
    # `Setting.load();` when graph.settings_defs is non-empty (P3 §2, P1 §"StoryInit
    # Wiring"). Restores the player's persisted settings on startup. Idiomatic
    # SugarCube: Setting.load() in StoryInit, Setting.save() triggered by the
    # settings dialog (P1 OQ1 resolved to load-only here). Makes StoryInit
    # non-empty whenever settings exist even with no state vars, so the
    # `if init_body:` write at the caller still fires. Exact code:
    #   if getattr(graph, "settings_defs", None):
    #       lines.append("<<run Setting.load()>>")
    # See p1_research.md §"StoryInit Wiring", p3_interfaces.md §2.
    # TODO(settings-api): C2 — the return-empty guard below must account for
    # settings: when graph.settings_defs is non-empty, StoryInit must be written
    # even if there are no $var defaults (because C1 appended Setting.load()).
    # Final guard form: `if not lines and not getattr(graph, "settings_defs", None):`
    # Empty string returned ONLY when no defaults AND no settings. See P1 §"StoryInit
    # Wiring", P6 INV. Coordinate with any other feature that also widens this guard.
    # TODO(achievements): _storyinit_twee body — after the <<set $var>> loop
    # above, call _metadata_init_block(graph) (I1) and append when non-None:
    #   meta_block = _metadata_init_block(graph)
    #   if meta_block:
    #       lines.append(meta_block)
    # When graph.metadata_keys is empty (default), returns None → no change.
    # See p3_interfaces.md §2 I1, p1_research.md §4A/§7.
    # TODO(prng-seed): S5 — the empty-return guard below must also account for
    # the seed: when cfg.prng_seed is non-empty, StoryInit must be written even
    # with zero declared defaults (otherwise the seed never reaches the
    # compiled story). PRNG widening of this guard: add `and not cfg.prng_seed`.
    # NOTE: this guard is ALREADY slated to widen for settings (TODO(settings-api)
    # C2 above) and achievements (metadata block). The final merged form at P7
    # must combine ALL conditions — e.g. `if not lines and not cfg.prng_seed and
    # not getattr(graph, "settings_defs", None):`. Empty string returned ONLY
    # when no defaults AND no seed AND no settings. Coordinate the merge at P7.
    # See p1_research.md §3.2, p6_invariants.md INV-2.
    if not lines:
        return ""
    body = "\n".join(lines)
    return f":: StoryInit\n{body}\n"


# TODO(achievements): I1 — add _metadata_init_block(graph: StoryGraph) -> str | None
# here (P3 §2 I1), as a module-private peer to _storyinit_twee. Emits the
# StoryInit metadata-hydration block: one
# `<<set setup.<id> to recall('<id>', <default>)>>` line per declared
# MetadataKey in graph.metadata_keys. Returns None when metadata_keys is
# empty so _storyinit_twee can skip emission entirely. Signature-only; P7 body.
#   def _metadata_init_block(graph: StoryGraph) -> str | None:
#       """Emit the SugarCube StoryInit metadata-hydration block, or None."""
# See p3_interfaces.md §2 I1.


# TODO(settings-api): C3 — add _storysettings_twee(graph: StoryGraph) -> str
# here, after _storyinit_twee and grouped with the _story*_twee helpers, before
# _storydata_twee (P3 §1, P1 §"StorySettings Passage Generation"). Emits a
# SugarCube StorySettings [script] passage with Setting.add*() calls for each
# SettingDef in graph.settings_defs; returns "" when none defined (parallel to
# _storyinit_twee's empty-return at line 200). Signature + one-line docstring
# only; body in P7. Exact stub:
#   def _storysettings_twee(graph: StoryGraph) -> str:
#       """Emit a SugarCube StorySettings [script] passage with Setting.add*() calls for each SettingDef in graph.settings_defs; return "" if none defined."""
# SettingDef is imported via the C0 TODO at line 17. See p3_interfaces.md §1.


# TODO(settings-api): C4 — add default_settings_defs() -> list[SettingDef]
# here, near the other compile helpers (P3 §3, P1 §"Default Settings"). Returns
# the three default SettingDef entries (difficulty addList, text_speed addRange,
# content_warnings addToggle) for templates that opt into the settings API via
# uses_settings_api. No parameters — the three defaults are fixed per the
# feature spec (P1 lines 170-176). The decision of WHETHER to use them (opt-in
# via template uses_settings_api or explicit graph.settings_defs) is made by
# the caller (_populate_build_src, TODO C5), not this factory. Signature + one-
# line docstring only; body in P7. Exact stub:
#   def default_settings_defs() -> list[SettingDef]:
#       """Return the three default SettingDef entries (difficulty, text_speed, content_warnings) for templates that opt into the settings API."""
# See p3_interfaces.md §3.


def _storydata_twee(cfg: HarnessConfig, start_passage: str) -> str:
    """StoryData + StoryTitle as their own Twee v3 passages."""
    start = start_passage or "Start"
    ifid = cfg.story_ifid or "00000000-0000-0000-0000-000000000000"
    return (
        f":: StoryData\n"
        f'{{\n'
        f'  "ifid": "{ifid}",\n'
        f'  "format": "{cfg.story_format}",\n'
        f'  "format-version": "{cfg.format_version}",\n'
        f'  "start": "{start}"\n'
        f'}}\n\n'
        f":: StoryTitle\n{cfg.story_title}\n"
    )


# TODO(story-interface): add _storyinterface_twee(cfg: HarnessConfig) -> str
# here, after _storydata_twee, grouped with the _story*_twee special-passage
# emitters (P3 I1, P1 3.2). Signature + one-line docstring only; body in P7.
# Reads cfg.story_interface (Optional[StoryInterfaceConfig], P2 D3); returns ''
# when None (no StoryInterface emitted — preserves default UI bar; P6 INV
# "None => no StoryInterface.twee"). Non-empty: ':: StoryInterface\n<html>\n'.
# Why cfg (not the sub-model): matches _storydata_twee(cfg, start_passage) which
# takes the whole HarnessConfig. No start_passage param (StoryInterface is pure
# static HTML from config, no graph dependency — P1 3.2). Exact stub:
#   def _storyinterface_twee(cfg: HarnessConfig) -> str:
#       """Emit a `:: StoryInterface` Twee passage from cfg.story_interface, or '' when unset."""
# See p3_interfaces.md I1, p1_research.md 3.2.


def _populate_build_src(
    p: ProjectPaths,
    cfg: HarnessConfig,
    media_map: dict[str, dict[str, str]],
) -> Path:
    """
    Mirror arcs/ into .harness/cache/build_src/, embedding resolved media into
    each passage on the way. ``media_map`` maps slot ids to the relative
    ``media/<file>`` paths already staged next to the output HTML. Returns the
    build_src root.
    """
    graph = load_story(p)
    build_src = p.cache_dir / "build_src"
    if build_src.exists():
        shutil.rmtree(build_src)
    build_src.mkdir(parents=True, exist_ok=True)

    (build_src / "StoryData.twee").write_text(
        _storydata_twee(cfg, graph.start_passage),
        encoding="utf-8",
    )

    # TODO(prng-seed): S6 — thread cfg into the call: change
    #   init_body = _storyinit_twee(graph)
    # to
    #   init_body = _storyinit_twee(graph, cfg)
    # The caller (_populate_build_src) already has cfg in scope (param at line
    # ~247). One-line change required by the modified S3 signature. P7 will
    # edit this line. See p3_interfaces.md §3.1, p1_research.md §3.3.
    init_body = _storyinit_twee(graph)
    if init_body:
        (build_src / "StoryInit.twee").write_text(init_body, encoding="utf-8")

    # TODO(settings-api): C5 — emit StorySettings.twee here, after the StoryInit
    # block and before the arcs mirror loop (P3 §1/§3, P1 §"StorySettings Passage
    # Generation"). StorySettings is a generated special passage (like
    # StoryData/StoryInit). graph is already loaded above (load_story, line 258).
    # Generate when EITHER graph.settings_defs is non-empty (explicit per-story
    # settings) OR the active template's uses_settings_api is True (then use
    # default_settings_defs() for the three defaults — P1 OQ2 resolved: template
    # flag triggers the default set). Mirrors the StoryInit emission pattern
    # (body / if body: write). No-op (no file) when no settings defined (P6 INV).
    # See p1_research.md §"Template-Aware Trigger", p3_interfaces.md §1/§3.

    # TODO(story-interface): emit StoryInterface.twee here, after the StoryInit
    # block and before the arcs mirror loop (P3 I2, P1 3.2). StoryInterface is
    # a generated special passage (like StoryData/StoryInit), not an arcs file,
    # so it belongs in the "generated special passages" section which precedes
    # the arcs mirror. cfg is already in scope (param). Mirrors the existing
    # StoryInit emission pattern (init_body / if init_body: write). Exact code:
    #   si_body = _storyinterface_twee(cfg)
    #   if si_body:
    #       (build_src / "StoryInterface.twee").write_text(si_body, encoding="utf-8")
    # No-op (no file) when cfg.story_interface is None (P6 INV). See
    # p3_interfaces.md I2, p1_research.md 3.2.

    for tw_path in collect_passage_files(p):
        rel = tw_path.relative_to(p.arcs_dir)
        target = build_src / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _embed_media(p, tw_path.read_text(encoding="utf-8"), media_map),
            encoding="utf-8",
        )

    # ── Template assets ──────────────────────────────────────────────────
    # When a template id is configured, copy its CSS/JS into build_src/ so
    # Tweego bundles them into the compiled story (Tweego natively wraps
    # and injects any .css/.js it finds in the source tree into <head>).
    inject_template_assets(cfg, build_src)
    # TODO(passage-tags): _populate_build_src body — after inject_template_assets,
    # call generate_mood_tag_css(graph) and write the non-empty result to
    # build_src/mood-tags.css. graph is already loaded above (load_story), and
    # load_story / StoryGraph are already imported. No-op when the result is ""
    # (don't emit an empty .css — P1 §3b no-op-when-empty, P6 INV-T5). Exact:
    #   mood_css = generate_mood_tag_css(graph)
    #   if mood_css:
    #       (build_src / "mood-tags.css").write_text(mood_css, encoding="utf-8")
    # See p3_interfaces.md §S6, p1_research.md §3b, p6 INV-T5.

    return build_src


def inject_template_assets(cfg: HarnessConfig, build_src: Path) -> list[Path]:
    """Copy the active template's CSS/JS source files into *build_src*.

    Returns the list of files actually copied (empty when no template is
    configured or the template has no assets).  Tweego natively discovers
    ``.css`` / ``.js`` files in the source directory and injects them into
    the compiled HTML ``<head>``, so copying them next to the passages is
    sufficient — no manual wrapping or ``--head`` flag needed.

    See ``harness/templates.py`` (TEMPLATE_REGISTRY) and
    ``examples/html_templates/TEMPLATE_VERIFICATION_REPORT.md``.
    """
    if not getattr(cfg, "template_id", ""):
        return []

    # Imported here to avoid a circular import at module load time
    # (templates.py is standalone, but keeping the import local documents
    # the compile-time dependency and lets tests stub it out cleanly).
    from .templates import template_assets

    copied: list[Path] = []
    for src in template_assets(cfg.template_id):
        dest = build_src / src.name
        # Avoid collisions with story-owned stylesheets by prefixing.
        if dest.exists():
            dest = build_src / f"template_{src.name}"
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


# TODO(passage-tags): define generate_mood_tag_css(graph: StoryGraph) -> str
# here, after inject_template_assets (P3 §S5, P1 §3b). Return CSS text with one
# [data-tags~="tag"] rule per distinct mood tag across the graph, or "" when
# no passage has mood tags. Consumes StoryGraph and reads PassageEntry.tags
# (P2 §2) across all passages. The caller (_populate_build_src) writes the
# result to build_src/mood-tags.css only when non-empty (Tweego auto-bundles
# any .css in the tree — same pattern as inject_template_assets). No dedicated
# CSS struct (YAGNI per P2 non-goals). Signature + one-line docstring only;
# body in P7. Exact stub:
#   def generate_mood_tag_css(graph: StoryGraph) -> str:
#       """Return CSS text with one [data-tags~="tag"] rule per distinct mood tag across the graph, or "" when no passage has mood tags."""
# StoryGraph is already imported in compile.py (load_story / StoryGraph).
# See p3_interfaces.md §S5, p1_research.md §3b, p6 INV-T5.


def _build_tweego_argv(
    tweego: str,
    cfg: HarnessConfig,
    build_src: Path,
    out_html: Path,
) -> list[str]:
    """Assemble the tweego command line from config + paths."""
    cmd: list[str] = [tweego, "-o", str(out_html)]
    if cfg.sugarcube_path:
        cmd += ["--format", cfg.sugarcube_path]
    if cfg.tweego_log_stats:
        cmd.append("-l")
    if cfg.tweego_test_mode:
        cmd.append("-t")
    if cfg.tweego_head_file:
        cmd.append(f"--head={cfg.tweego_head_file}")
    for mod in cfg.tweego_module_dirs:
        if mod:
            cmd += ["-m", mod]
    cmd.append(str(build_src))
    return cmd


def compile_story(p: ProjectPaths, cfg: HarnessConfig) -> tuple[bool, str]:
    """
    Validate then compile. Returns (success, output_or_error).
    Errors block compile; warnings do not.
    """
    result = run_validation(p)
    if not result.ok:
        msg = "Compile blocked by validation errors:\n"
        for err in result.errors:
            msg += f"  [{err.code}] {err.message}\n"
        return False, msg

    if not collect_passage_files(p):
        return False, "No .tw or .twee files found in arcs/."

    # Stage resolved media into build/media/ (next to the output html) and embed
    # the relative paths Tweego won't touch — the game ships as html + media/.
    p.build_dir.mkdir(parents=True, exist_ok=True)
    media_map = stage_media_for_build(p, p.build_dir)
    build_src = _populate_build_src(p, cfg, media_map)

    tweego = find_tweego(cfg.tweego_path)
    if not tweego:
        return False, (
            f"Tweego not found (configured: {cfg.tweego_path!r}).\n"
            f"Download: https://www.motoslave.net/tweego/\n"
            f"Then set tweego_path in Settings or in .harness/config.yaml."
        )

    p.build_dir.mkdir(parents=True, exist_ok=True)
    out_html = p.build_dir / "story.html"

    cmd = _build_tweego_argv(tweego, cfg, build_src, out_html)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "Tweego timed out after 60 seconds."
    except FileNotFoundError as e:
        return False, str(e)

    if proc.returncode != 0:
        return False, f"Tweego error:\n{proc.stderr}\n{proc.stdout}"

    # `-l` (log stats) prints to stderr — surface it alongside the output path.
    stats = (proc.stderr or "").strip() if cfg.tweego_log_stats else ""
    if stats:
        return True, f"{out_html}\n\n--- tweego stats ---\n{stats}"
    return True, str(out_html)

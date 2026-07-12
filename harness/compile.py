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

    return re.sub(r'<!-- media:(slot_[a-f0-9]+) -->', replace_slot, tw_content)


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


def _storyinit_twee(graph: StoryGraph) -> str:
    """
    Emit a SugarCube StoryInit passage that initialises every declared default.

    Without this, story.json's declared defaults are honoured by the validator
    but never written to the compiled HTML — so passages that read $var before
    any setter would observe undefined at runtime.
    """
    lines: list[str] = []
    for var, decl in sorted(graph.state_variables.items()):
        if decl.default is None:
            continue
        lines.append(f"<<set {var} to {_format_sc_default(decl.default)}>>")
    if not lines:
        return ""
    body = "\n".join(lines)
    return f":: StoryInit\n{body}\n"


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

    init_body = _storyinit_twee(graph)
    if init_body:
        (build_src / "StoryInit.twee").write_text(init_body, encoding="utf-8")

    for tw_path in collect_passage_files(p):
        rel = tw_path.relative_to(p.arcs_dir)
        target = build_src / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _embed_media(p, tw_path.read_text(encoding="utf-8"), media_map),
            encoding="utf-8",
        )
    return build_src


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

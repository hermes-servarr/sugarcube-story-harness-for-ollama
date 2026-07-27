"""Template registry — SugarCube HTML template awareness for generation.

Catalogs the 7 manonamora SugarCube v2.37.3 HTML templates in
``examples/html_templates/`` so the harness can:

1. **Guide generation** toward a template's style by injecting a compact
   prompt hint (``template_guidance``).
2. **Inject template styling** into compiled stories by copying the
   template's CSS/JS into the Tweego build source (``template_assets``).

The registry is a static dict (``TEMPLATE_REGISTRY``) keyed by template id.
Each entry is a :class:`TemplateInfo` describing the template's metadata,
recommended story types, the SugarCube features it showcases, and the
relative paths of its CSS/JS source files.

Template data was distilled from
``examples/html_templates/TEMPLATE_VERIFICATION_REPORT.md`` (task t_1d39efd8)
and ``docs/sugarcube2-analysis.md``.  Templates are CC-BY by manonamora;
see ``examples/html_templates/attribution_and_github.txt``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata for one bundled SugarCube HTML template."""

    id: str                         # registry key, e.g. "character-creator"
    name: str                       # display name
    category: str                   # "Code Template" | "UI Template"
    description: str                # one-line summary
    story_types: tuple[str, ...]    # recommended story types (for selection guide)
    # Relative to examples/html_templates/<Template Name>/source/
    css_file: str = ""
    js_file: str = ""
    has_story_interface: bool = False
    uses_widgets: bool = False
    uses_settings_api: bool = False
    uses_chapel_macros: bool = False  # <<popup>>, <<dialog>>, <<notify>>
    uses_fontawesome: bool = False
    features: tuple[str, ...] = field(default_factory=tuple)
    # Compact one-line hint injected into passage prompts when this template
    # is active. Kept short to respect local-model token budgets.
    prompt_hint: str = ""


# ── Registry ─────────────────────────────────────────────────────────────────

TEMPLATE_REGISTRY: dict[str, TemplateInfo] = {

    "character-creator": TemplateInfo(
        id="character-creator",
        name="Character Creator",
        category="Code Template",
        description=(
            "Multi-page interactive character creation flow with widgets, "
            "popups, and deep nested-object state."
        ),
        story_types=("character-driven RPG", "RPG with stats"),
        css_file="StyleSheet.css",
        js_file="Script.js",
        has_story_interface=False,
        uses_widgets=True,
        uses_settings_api=False,
        uses_chapel_macros=False,
        uses_fontawesome=False,
        features=(
            "Multi-step character creation with review/confirm flow",
            "Extensive <<widget>> definitions for trait grids",
            "Deeply nested SugarCube objects ($mc.name, $hair.length, …)",
            "<<button>>, <<link>>, <<if>>/<<elseif>>/<<else>>, <<timed>>",
            "nobr tag on widget passages",
        ),
        prompt_hint=(
            "Character-creation style: use <<widget>> for reusable trait "
            "selectors, nested $mc.* objects for PC data, <<button>> to "
            "advance steps."
        ),
    ),

    "one-page": TemplateInfo(
        id="one-page",
        name="One Page",
        category="UI Template",
        description=(
            "Chapbook-style single-page display with dropdown menu, "
            "popup dialogs, and accessibility features."
        ),
        story_types=("minimalist IF", "accessibility-focused"),
        css_file="StyleSheet.css",
        js_file="Script.js",
        has_story_interface=True,
        uses_widgets=False,
        uses_settings_api=True,
        uses_chapel_macros=True,
        uses_fontawesome=False,
        features=(
            "Custom StoryInterface with #passages + #menu",
            "Dropdown menu with popup links (stats, saves, settings)",
            "Chapel's Dialog API (<<popup>>, <<dialog>>)",
            "noreturn tag on title/info pages",
            "Settings API: font, autosave, autoname, theme",
        ),
        prompt_hint=(
            "One-page UI: single-page layout, <<include>> for shared menu "
            "elements, noreturn tag on non-story pages."
        ),
    ),

    "settings": TemplateInfo(
        id="settings",
        name="Settings",
        category="Code Template",
        description=(
            "Full Settings API reference: range, toggle, list, with audio "
            "and animation demos."
        ),
        story_types=("settings-heavy project", "reference / showcase"),
        css_file="CSS.css",
        js_file="JavaScript.js",
        has_story_interface=False,
        uses_widgets=False,
        uses_settings_api=True,
        uses_chapel_macros=True,  # <<notify>>
        uses_fontawesome=False,
        features=(
            "Setting.addHeader / addList / addRange / addToggle",
            "Config.saves.isAllowed with Save.Type.Auto check",
            "Config.saves.descriptions (autoname)",
            "<<type>> typewriter macro, <<audio>> macro",
            "Chapel's <<notify>> macro",
        ),
        prompt_hint=(
            "Settings-aware: use Setting.addToggle/addList for player "
            "options, Config.saves.isAllowed with noreturn tag."
        ),
    ),

    "simple-book": TemplateInfo(
        id="simple-book",
        name="Simple Book",
        category="UI Template",
        description=(
            "Notebook look with front/back covers, toggleable left/right "
            "side menus, and FontAwesome icons."
        ),
        story_types=("interactive fiction (book-style)", "codex/stats menu"),
        css_file="StyleSheet.css",
        js_file="Script.js",
        has_story_interface=True,
        uses_widgets=False,
        uses_settings_api=True,
        uses_chapel_macros=True,
        uses_fontawesome=True,
        features=(
            "Book-like StoryInterface (#title, #middle, #left-menu, #right-menu)",
            "<<toggleclass>> for menu show/hide",
            "cover-start / cover-end tags for book covers",
            "FontAwesome icons (fa-solid fa-*)",
            "Chapel's Dialog API + <<notify>>",
            "CODEX tag for info/reference pages",
        ),
        prompt_hint=(
            "Book style: room-type passages with named exits, <<include>> "
            "for shared navigation, cover tags for title/end pages."
        ),
    ),

    "space-tech": TemplateInfo(
        id="space-tech",
        name="Space-Tech UI",
        category="UI Template",
        description=(
            "Dual sci-fi themes (Space + CRT/Tech) with tag-driven CSS "
            "theming and widget-based stat bars."
        ),
        story_types=("sci-fi/tech themed", "RPG with stats"),
        css_file="StyleSheet.css",
        js_file="Script.js",
        has_story_interface=True,
        uses_widgets=True,
        uses_settings_api=True,
        uses_chapel_macros=False,
        uses_fontawesome=False,
        features=(
            "Dual theme via tag-based CSS ([data-tags~=\"codex\"])",
            "Widget-based stat bars (<<widget \"statsformat\">>)",
            "Mobile/desktop responsive layout",
            "stats-visible tag triggers stats bar display",
            "codex tag switches visual theme",
            "Unicode icons instead of FontAwesome",
        ),
        prompt_hint=(
            "Space-tech style: tag passages for CSS theming (codex, "
            "stats-visible), <<widget>> for stat bars, nobr on interface "
            "passages."
        ),
    ),

    "title-page": TemplateInfo(
        id="title-page",
        name="Title Page",
        category="UI Template",
        description=(
            "Multiple title/menu page layout variants using passage tags "
            "and CSS positioning. CSS-only, no JS."
        ),
        story_types=("title/menu focused", "minimalist"),
        css_file="Stylesheet.css",
        js_file="",
        has_story_interface=False,
        uses_widgets=False,
        uses_settings_api=False,
        uses_chapel_macros=False,
        uses_fontawesome=False,
        features=(
            "Multiple title layouts via tags (title bar, top-left, centered, …)",
            "<<include \"Menu Elements\">> for shared title content",
            "tag-colors in StoryData",
            "No custom JS — pure CSS theming",
            "Dialog.create().wikiPassage().open() for credits",
        ),
        prompt_hint=(
            "Title-page style: tag passages for layout variants, "
            "<<include>> for shared menu content, CSS-only theming."
        ),
    ),

    "vn-lite-rpg": TemplateInfo(
        id="vn-lite-rpg",
        name="VN-lite RPG",
        category="UI Template",
        description=(
            "Visual-novel layout with character/portrait image areas, "
            "bottom icon menu bar, and conditional image selection."
        ),
        story_types=("visual novel", "RPG with portraits"),
        css_file="StyleSheet.css",
        js_file="Script.js",
        has_story_interface=True,
        uses_widgets=False,
        uses_settings_api=True,
        uses_chapel_macros=False,
        uses_fontawesome=True,
        features=(
            "VN-style StoryInterface (#header, #container, #perso, #footer)",
            "Conditional image selection via passage() and tags()",
            "side tag marks non-story pages (no party images, no saving)",
            "Bottom icon-only menu bar (FontAwesome)",
            "Minimal settings (autosave only)",
        ),
        prompt_hint=(
            "VN-lite style: conditional images via <<if passage() isnot "
            "\"X\">>, side tag for menu pages, portrait display areas."
        ),
    ),
}


# ── Public API ───────────────────────────────────────────────────────────────

def get_template(template_id: str) -> TemplateInfo | None:
    """Return the :class:`TemplateInfo` for *template_id*, or ``None``."""
    return TEMPLATE_REGISTRY.get(template_id)


def list_templates() -> list[TemplateInfo]:
    """Return all registered templates in registry order."""
    return list(TEMPLATE_REGISTRY.values())


def list_template_ids() -> list[str]:
    """Return all registered template ids in registry order."""
    return list(TEMPLATE_REGISTRY.keys())


def template_guidance(template_id: str) -> str:
    """Compact guidance string for prompt injection.

    Returns an empty string for unknown / no template so callers can
    unconditionally interpolate the result.
    """
    tpl = get_template(template_id)
    if tpl is None:
        return ""
    return f"[TEMPLATE STYLE: {tpl.name}]\n{tpl.prompt_hint}"


def _templates_root() -> Path:
    """Return the ``examples/html_templates/`` directory.

    Resolved relative to the harness package — works both in a source
    checkout and in an editable install.
    """
    # harness/ is one level below the repo root; examples/ is at repo root.
    return Path(__file__).resolve().parent.parent / "examples" / "html_templates"


# Mapping from template id to the on-disk directory name (which has spaces).
_TEMPLATE_DIR_NAMES: dict[str, str] = {
    "character-creator": "Character Creator Template",
    "one-page":          "One Page Template",
    "settings":          "Settings Template",
    "simple-book":       "Simple Book Template",
    "space-tech":        "Space-Tech UI Template",
    "title-page":        "Title Page Template",
    "vn-lite-rpg":       "VN-lite RPG Template",
}


def template_dir(template_id: str, root: Path | None = None) -> Path | None:
    """Return the on-disk directory for *template_id*, or ``None``.

    *root* defaults to :func:`_templates_root`.
    """
    name = _TEMPLATE_DIR_NAMES.get(template_id)
    if name is None:
        return None
    base = root or _templates_root()
    d = base / name
    return d if d.is_dir() else None


def template_css_path(template_id: str, root: Path | None = None) -> Path | None:
    """Return the absolute path to the template's CSS source file, or None."""
    tpl = get_template(template_id)
    if tpl is None or not tpl.css_file:
        return None
    d = template_dir(template_id, root)
    if d is None:
        return None
    p = d / "source" / tpl.css_file
    return p if p.is_file() else None


def template_js_path(template_id: str, root: Path | None = None) -> Path | None:
    """Return the absolute path to the template's JS source file, or None."""
    tpl = get_template(template_id)
    if tpl is None or not tpl.js_file:
        return None
    d = template_dir(template_id, root)
    if d is None:
        return None
    p = d / "source" / tpl.js_file
    return p if p.is_file() else None


def template_assets(template_id: str, root: Path | None = None) -> list[Path]:
    """Return existing CSS/JS source paths for the template (may be empty).

    These are the files that :func:`harness.compile.inject_template_assets`
    copies into the build source directory so Tweego bundles them.
    """
    paths: list[Path] = []
    css = template_css_path(template_id, root)
    if css is not None:
        paths.append(css)
    js = template_js_path(template_id, root)
    if js is not None:
        paths.append(js)
    return paths

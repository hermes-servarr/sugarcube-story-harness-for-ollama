"""Playwright browser controller for the playtester."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Browser

from harness.playtest.models import ChoiceInfo, ConsoleMessage


def launch_browser() -> Page:
    """Launch headless Chromium and return a ready Playwright Page.

    Sets PLAYWRIGHT_BROWSERS_PATH if the default location exists.
    Raises a helpful error if Playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright is not installed. Install it with:\n"
            "  uv pip install playwright\n"
            "  playwright install chromium\n"
            "Or use the crawl4ai venv which already has Playwright:\n"
            "  /opt/data/.venvs/crawl4ai/bin/python"
        )

    # Point Playwright at the existing chromium install if present
    pw_path = "/opt/data/.playwright"
    if os.path.isdir(pw_path):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", pw_path)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    # Attach handles so close_browser can find them
    page._browser = browser  # type: ignore[attr-defined]
    page._playwright = pw  # type: ignore[attr-defined]
    return page


def close_browser(browser: Browser) -> None:
    """Close the browser and release all resources."""
    try:
        browser.close()
    except Exception:
        pass
    # Stop the playwright instance if it's attached
    pw = getattr(browser, "_playwright", None)
    if pw is not None:
        try:
            pw.stop()
        except Exception:
            pass


def load_page(page: Page, file_url: str) -> None:
    """Navigate the page to a file:// URL and wait for load."""
    page.goto(file_url, wait_until="domcontentloaded")


def verify_sugarcube(page: Page) -> bool:
    """Return True if the SugarCube engine is detected on the page."""
    try:
        return page.evaluate(
            "() => !!(window.SugarCube || window.sugarcube "
            "|| (window.sugarcube !== undefined))"
        )
    except Exception:
        return False


def get_current_passage(page: Page) -> str:
    """Return the current SugarCube passage id from JS state or DOM fallback."""
    # Try JS state first
    try:
        passage = page.evaluate(
            "() => {"
            "  if (window.SugarCube && window.SugarCube.State) {"
            "    return window.SugarCube.State.passage || '';"
            "  }"
            "  if (window.sugarcube && window.sugarcube.State) {"
            "    return window.sugarcube.State.passage || '';"
            "  }"
            "  return '';"
            "}"
        )
        if passage:
            return passage
    except Exception:
        pass
    # Fall back to DOM: the .passage element may have a data-passage attribute
    try:
        el = page.query_selector(".passage")
        if el:
            pid = el.get_attribute("data-passage")
            if pid:
                return pid
    except Exception:
        pass
    return ""


def get_passage_type(page: Page) -> str:
    """Detect passage type from body tag classes or DOM attributes."""
    try:
        body = page.query_selector("body")
        if not body:
            return ""
        cls = body.get_attribute("class") or ""
        # SugarCube adds body.tag-<tagname> for passage tags
        for token in cls.split():
            if token.startswith("tag-"):
                return token[4:]
        return ""
    except Exception:
        return ""


def get_choices(page: Page) -> list[ChoiceInfo]:
    """Extract all navigational choices from the current passage."""
    choices: list[ChoiceInfo] = []
    try:
        # Primary: a.link-internal within .passage
        links = page.query_selector_all(".passage a.link-internal")
        if not links:
            # Broader: all a within .passage that aren't external
            links = page.query_selector_all(".passage a")
            links = [
                l for l in links
                if not _is_external(l)
            ]

        for idx, link in enumerate(links):
            text = (link.inner_text() or "").strip()
            href = link.get_attribute("href") or ""
            target = ""
            # SugarCube wikilinks use href like "#passage_id" or javascript: links
            if href.startswith("#"):
                target = href[1:]
            # Try data-passage attribute
            dp = link.get_attribute("data-passage")
            if dp:
                target = dp
            external = _is_external(link)
            choices.append(ChoiceInfo(
                text=text or f"choice_{idx}",
                target=target,
                element_index=idx,
                is_external=external,
            ))
    except Exception:
        pass
    return choices


def _is_external(link) -> bool:
    """Check if a link element is external."""
    try:
        cls = link.get_attribute("class") or ""
        if "link-external" in cls:
            return True
        href = link.get_attribute("href") or ""
        if href.startswith("http://") or href.startswith("https://"):
            return True
        if href.startswith("mailto:") or href.startswith("javascript:void"):
            return False
    except Exception:
        pass
    return False


def click_choice(page: Page, element_index: int) -> bool:
    """Click a choice by zero-based index and wait for passage transition.

    Returns True if the passage changed, False if it didn't (broken nav or
    the link was not found). Uses SugarCube's State.passage to confirm the
    transition rather than a fixed timeout.
    """
    try:
        # Record current passage so we can detect transition
        before = get_current_passage(page)

        links = page.query_selector_all(".passage a.link-internal")
        if not links:
            links = [
                l for l in page.query_selector_all(".passage a")
                if not _is_external(l)
            ]
        if element_index >= len(links):
            return False

        links[element_index].click(timeout=5000)

        # Wait for SugarCube to update the passage. SugarCube renders
        # asynchronously after a link click, so wait for State.passage to
        # change rather than using a fixed sleep.
        try:
            page.wait_for_function(
                f"() => {{"
                f"  if (window.SugarCube && window.SugarCube.State) {{"
                f"    return window.SugarCube.State.passage !== {repr(before)};"
                f"  }}"
                f"  // Fallback: check DOM .passage data-passage attr"
                f"  var el = document.querySelector('.passage');"
                f"  return el && el.getAttribute('data-passage') !== {repr(before)};"
                f"}}",
                timeout=5000,
            )
            return True
        except Exception:
            # The passage didn't change within 5s — either it's a same-page
            # action (linkreplace, linkappend) or navigation broke.
            # Give a short buffer then report the actual state.
            page.wait_for_timeout(300)
            after = get_current_passage(page)
            return after != before
    except Exception:
        return False


def take_screenshot(page: Page, path: str) -> None:
    """Save a full-page PNG screenshot to the given path."""
    page.screenshot(path=path, full_page=True)


def get_console_messages(page: Page) -> list[ConsoleMessage]:
    """Collect all console messages captured on the page so far."""
    raw = getattr(page, "_console_messages", [])
    return [
        ConsoleMessage(
            type=getattr(m, "type", "unknown"),
            text=getattr(m, "text", str(m)),
            url=getattr(m, "url", "") or "",
        )
        for m in raw
    ]


def get_page_text(page: Page) -> str:
    """Extract text content from the .passage DOM element."""
    try:
        el = page.query_selector(".passage")
        if el:
            return el.inner_text() or ""
    except Exception:
        pass
    return ""


def check_media_loads(page: Page) -> list[str]:
    """Return descriptions of img/audio/video elements that failed to load."""
    failed: list[str] = []
    try:
        for tag in ("img", "audio", "video"):
            els = page.query_selector_all(f".passage {tag}")
            for el in els:
                src = el.get_attribute("src") or "(no src)"
                # Check natural dimensions for images; use evaluate for audio/video
                if tag == "img":
                    natural_w = el.evaluate("el => el.naturalWidth")
                    if natural_w == 0:
                        failed.append(f"{tag}: {src}")
                else:
                    # For audio/video, check readyState
                    ready = el.evaluate("el => el.readyState")
                    if ready < 2:  # HAVE_CURRENT_DATA
                        failed.append(f"{tag}: {src}")
    except Exception:
        pass
    return failed

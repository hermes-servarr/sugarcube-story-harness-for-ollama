"""Compile production artifacts and assert observable SugarCube behavior."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import CompileArtifact


_TEMP_ENVIRONMENT_LOCK = threading.RLock()


@dataclass(frozen=True)
class BrowserChoiceExpectation:
    label: str
    target: str
    state_after: tuple[tuple[str, Any], ...] = ()
    return_label: str = ""
    state_after_return: tuple[tuple[str, Any], ...] = ()
    occurrence: int = 0
    hidden_after_return: bool = False
    accept_dialog: bool = False


@dataclass(frozen=True)
class BrowserGuardExpectation:
    label: str
    state_key: str
    state_value: Any
    visible: bool


@dataclass(frozen=True)
class BrowserFormExpectation:
    selector: str
    value: str
    state_key: str
    expected_value: Any


@dataclass(frozen=True)
class BrowserScenario:
    passage_id: str
    story_start: str = ""
    expected_text: tuple[str, ...] = ()
    initial_state: tuple[tuple[str, Any], ...] = ()
    setup_entities: tuple[tuple[str, Any], ...] = ()
    choices: tuple[BrowserChoiceExpectation, ...] = ()
    guards: tuple[BrowserGuardExpectation, ...] = ()
    forms: tuple[BrowserFormExpectation, ...] = ()
    submit_label: str = ""
    hostile_marker: str = ""
    expected_choice_counts: tuple[tuple[str, int], ...] = ()
    allowed_initial_targets: tuple[str, ...] = ()
    random_runs: int = 0
    verify_state: bool = True


@dataclass(frozen=True)
class BrowserEvaluation:
    tweego_compile: bool
    browser_load: bool
    choice_reachability: bool | None
    choice_effect_execution: bool | None
    runtime_state_transaction: bool | None
    continuity_after_navigation: bool | None
    form_binding: bool | None
    hostile_text_safe: bool | None
    runtime_errors: tuple[str, ...] = ()
    details: tuple[str, ...] = ()


def evaluate_compile_artifact(
    artifact: CompileArtifact,
    scenario: BrowserScenario,
    *,
    tweego_path: Path,
    story_format_path: Path,
    browser_path: Path | None = None,
) -> BrowserEvaluation:
    """Compile a minimal complete story and exercise it in isolated pages."""
    with tempfile.TemporaryDirectory(prefix="sugarcube-browser-gate-") as raw_dir:
        directory = Path(raw_dir)
        source = directory / "fixture.twee"
        html = directory / "fixture.html"
        source.write_text(_story_source(artifact, scenario), encoding="utf-8")
        environment = os.environ.copy()
        environment["TWEEGO_PATH"] = str(story_format_path)
        compiled = subprocess.run(
            [str(tweego_path), "--format", "sugarcube-2", "--output", str(html), str(source)],
            capture_output=True,
            text=True,
            env=environment,
            timeout=60,
        )
        if compiled.returncode != 0:
            error = (compiled.stderr or compiled.stdout or "Tweego failed").strip()
            return BrowserEvaluation(
                tweego_compile=False,
                browser_load=False,
                choice_reachability=None,
                choice_effect_execution=None,
                runtime_state_transaction=None,
                continuity_after_navigation=None,
                form_binding=None,
                hostile_text_safe=None,
                runtime_errors=(error,),
            )
        return _run_browser(html, scenario, browser_path=browser_path)


def _run_browser(
    html: Path,
    scenario: BrowserScenario,
    *,
    browser_path: Path | None,
) -> BrowserEvaluation:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for browser evaluation") from exc

    errors: list[str] = []
    details: list[str] = []
    load_ok = True
    choice_ok = True
    effect_ok = True
    transaction_ok = True
    continuity_ok = True
    form_ok = True
    hostile_ok = True

    with _writable_temp_environment(), sync_playwright() as playwright:
        launch = {"headless": True}
        if browser_path is not None:
            launch["executable_path"] = str(browser_path)
        browser = playwright.chromium.launch(**launch)

        def page_for_start():
            context = browser.new_context()
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: errors.append(message.text)
                if message.type == "error" else None,
            )
            page.goto(html.as_uri(), wait_until="load")
            page.wait_for_selector("#passages .passage", timeout=15_000)
            if scenario.story_start and scenario.story_start != scenario.passage_id:
                page.evaluate(
                    "passage => SugarCube.Engine.play(passage)", scenario.passage_id
                )
                page.wait_for_function(
                    "passage => SugarCube.State.passage === passage",
                    arg=scenario.passage_id,
                    timeout=15_000,
                )
            if scenario.allowed_initial_targets:
                page.wait_for_function(
                    "targets => targets.includes(SugarCube.State.passage)",
                    arg=list(scenario.allowed_initial_targets),
                    timeout=15_000,
                )
            return context, page

        try:
            context, page = page_for_start()
            body = page.locator("#passages").inner_text()
            for expected in scenario.expected_text:
                if expected not in body:
                    load_ok = False
                    details.append(f"missing visible text: {expected}")
            initial_passage = page.evaluate("SugarCube.State.passage")
            allowed_initial = set(scenario.allowed_initial_targets)
            if (
                initial_passage != scenario.passage_id
                and initial_passage not in allowed_initial
            ):
                load_ok = False
                details.append("start passage identity differs")
            if scenario.hostile_marker:
                hostile_ok = scenario.hostile_marker in body
                hostile_ok = hostile_ok and page.locator("#passages script").count() == 0
                hostile_ok = hostile_ok and page.evaluate(
                    "typeof window.__HARNESS_HOSTILE_EXECUTED === 'undefined'"
                )
                if not hostile_ok:
                    details.append("hostile/Unicode marker was altered or executed")
            for label, expected_count in scenario.expected_choice_counts:
                actual_count = page.get_by_text(label, exact=True).count()
                if actual_count != expected_count:
                    choice_ok = False
                    details.append(
                        f"choice {label} count={actual_count}, expected={expected_count}"
                    )
            context.close()

            if scenario.random_runs:
                observed = []
                for _ in range(scenario.random_runs):
                    context, page = page_for_start()
                    observed.append(page.evaluate("SugarCube.State.passage"))
                    context.close()
                unexpected = set(observed) - allowed_initial
                if unexpected:
                    choice_ok = False
                    details.append(
                        f"random route reached disallowed targets: {sorted(unexpected)}"
                    )
                details.append(f"random targets observed: {observed}")

            for guard in scenario.guards:
                context, page = page_for_start()
                page.evaluate(
                    "([key, value, passage]) => { SugarCube.State.variables[key] = value; SugarCube.Engine.play(passage); }",
                    [guard.state_key, guard.state_value, scenario.passage_id],
                )
                locator = page.get_by_text(guard.label, exact=True)
                actual = locator.count() > 0 and locator.first.is_visible()
                if actual != guard.visible:
                    choice_ok = False
                    details.append(
                        f"guard {guard.label}: visible={actual}, expected={guard.visible}"
                    )
                context.close()

            for choice in scenario.choices:
                context, page = page_for_start()
                before = dict(scenario.initial_state)
                locator = page.get_by_text(choice.label, exact=True)
                if locator.count() <= choice.occurrence or not locator.nth(choice.occurrence).is_visible():
                    choice_ok = False
                    details.append(f"choice unavailable: {choice.label}")
                    context.close()
                    continue
                locator.nth(choice.occurrence).click()
                if choice.accept_dialog:
                    page.locator("#restart-ok").click()
                try:
                    page.wait_for_function(
                        "target => SugarCube.State.passage === target",
                        arg=choice.target,
                        timeout=15_000,
                    )
                except Exception:
                    actual_target = page.evaluate("SugarCube.State.passage")
                    choice_ok = False
                    details.append(
                        f"choice {choice.label} reached {actual_target!r}, expected {choice.target!r}"
                    )
                    context.close()
                    continue
                if scenario.verify_state:
                    expected_after = dict(choice.state_after)
                    actual_after = page.evaluate(
                        "keys => Object.fromEntries(keys.map(key => [key, SugarCube.State.variables[key]]))",
                        list(expected_after),
                    )
                    if actual_after != expected_after:
                        effect_ok = False
                        details.append(f"choice {choice.label} state differs: {actual_after!r}")
                    untouched = set(before) - set(expected_after)
                    actual_untouched = page.evaluate(
                        "keys => Object.fromEntries(keys.map(key => [key, SugarCube.State.variables[key]]))",
                        list(untouched),
                    )
                    if actual_untouched != {key: before[key] for key in untouched}:
                        transaction_ok = False
                        details.append(f"choice {choice.label} changed unauthorized state")
                if choice.return_label:
                    page.get_by_text(choice.return_label, exact=True).click()
                    page.wait_for_function(
                        "target => SugarCube.State.passage === target",
                        arg=scenario.passage_id,
                    )
                    expected_return = dict(choice.state_after_return or choice.state_after)
                    after_return = page.evaluate(
                        "keys => Object.fromEntries(keys.map(key => [key, SugarCube.State.variables[key]]))",
                        list(expected_return),
                    )
                    if after_return != expected_return:
                        continuity_ok = False
                        details.append(f"choice {choice.label} state did not survive return")
                    if choice.hidden_after_return:
                        remaining = page.get_by_text(choice.label, exact=True)
                        if remaining.count() and remaining.first.is_visible():
                            continuity_ok = False
                            details.append(f"choice {choice.label} remained visible after return")
                context.close()

            if scenario.forms:
                context, page = page_for_start()
                for form in scenario.forms:
                    locator = page.locator(form.selector)
                    if locator.count() != 1:
                        form_ok = False
                        details.append(f"form selector missing: {form.selector}")
                        continue
                    tag = locator.evaluate("element => element.tagName.toLowerCase()")
                    if tag == "select":
                        locator.select_option(label=form.value)
                    else:
                        locator.fill(form.value)
                if scenario.submit_label:
                    page.get_by_text(scenario.submit_label, exact=True).click()
                for form in scenario.forms:
                    actual = page.evaluate("key => SugarCube.State.variables[key]", form.state_key)
                    if actual != form.expected_value:
                        form_ok = False
                        details.append(
                            f"form {form.state_key}: {actual!r} != {form.expected_value!r}"
                        )
                context.close()
        except Exception as exc:
            load_ok = False
            choice_ok = False
            effect_ok = False
            transaction_ok = False
            continuity_ok = False
            form_ok = False
            hostile_ok = False
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            browser.close()

    if errors:
        load_ok = False
    return BrowserEvaluation(
        tweego_compile=True,
        browser_load=load_ok,
        choice_reachability=(
            choice_ok
            if (
                scenario.choices
                or scenario.guards
                or scenario.expected_choice_counts
                or scenario.random_runs
            )
            else None
        ),
        choice_effect_execution=(effect_ok if scenario.choices and scenario.verify_state else None),
        runtime_state_transaction=(
            transaction_ok if scenario.choices and scenario.verify_state else None
        ),
        continuity_after_navigation=(
            continuity_ok if any(choice.return_label for choice in scenario.choices) else None
        ),
        form_binding=form_ok if scenario.forms else None,
        hostile_text_safe=hostile_ok if scenario.hostile_marker else None,
        runtime_errors=tuple(errors),
        details=tuple(details),
    )


def _story_source(artifact: CompileArtifact, scenario: BrowserScenario) -> str:
    story_data = json.dumps({
        "ifid": "4D92B0B0-1A64-4F57-B6A0-2BA91D2FD001",
        "format": "SugarCube",
        "format-version": "2.37.3",
        "start": scenario.story_start or scenario.passage_id,
        "tag-colors": {},
        "zoom": 1,
    }, separators=(",", ":"))
    state_lines = [
        f"<<set ${key} to {_sugarcube_literal(value)}>>"
        for key, value in scenario.initial_state
    ]
    if scenario.setup_entities:
        entities = json.dumps(dict(scenario.setup_entities), ensure_ascii=False)
        state_lines.append(f"<<run setup.entities = {entities}>>")
    targets = sorted(set(artifact.link_targets))
    target_passages = []
    for target in targets:
        if target == scenario.passage_id:
            continue
        target_passages.append(
            f":: {target}\nTARGET: {target}\n\n[[Return|{scenario.passage_id}]]\n"
        )
    return "\n\n".join((
        ":: StoryTitle\nProduction Browser Fixture",
        f":: StoryData\n{story_data}",
        ":: StoryInit\n" + "\n".join(state_lines),
        artifact.twee_source.rstrip(),
        *target_passages,
    )) + "\n"


def _sugarcube_literal(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


@contextmanager
def _writable_temp_environment():
    """Keep Playwright artifacts off inherited read-only Windows temp paths."""
    # os.environ is process-wide. Keep the lock held across the caller's use of
    # the temporary values so concurrent background playtests cannot snapshot,
    # overwrite, and restore one another's environment out of order.
    with _TEMP_ENVIRONMENT_LOCK:
        keys = ("TMPDIR", "TEMP", "TMP")
        previous = {key: os.environ.get(key) for key in keys}
        writable = tempfile.gettempdir()
        try:
            for key in keys:
                os.environ[key] = writable
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


__all__ = [
    "BrowserChoiceExpectation",
    "BrowserEvaluation",
    "BrowserFormExpectation",
    "BrowserGuardExpectation",
    "BrowserScenario",
    "evaluate_compile_artifact",
]

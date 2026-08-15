import os
from copy import deepcopy
from pathlib import Path

import pytest


AXE_SOURCE = Path(__file__).resolve().parents[1] / "ui" / "node_modules" / "axe-core" / "axe.min.js"


def _launch_chromium(runtime):
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    options = {"headless": True}
    if executable:
        options["executable_path"] = executable
    return runtime.chromium.launch(**options)


def _assert_no_serious_accessibility_violations(page, state: str) -> None:
    if not AXE_SOURCE.is_file():
        pytest.fail("run npm ci in ui/ so the pinned axe-core audit is available")
    if not page.evaluate("typeof globalThis.axe !== 'undefined'"):
        page.add_script_tag(path=str(AXE_SOURCE))
    result = page.evaluate("""async () => await axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] }
    })""")
    violations = [
        {
            "id": item["id"],
            "impact": item["impact"],
            "help": item["help"],
            "targets": [node["target"] for node in item["nodes"]],
        }
        for item in result["violations"]
        if item["impact"] in {"serious", "critical"}
    ]
    assert not violations, f"{state}: {violations}"


@pytest.mark.e2e
def test_next_ui_shell_loads_without_runtime_errors():
    base_url = os.environ.get("NEXT_UI_BASE_URL", "")
    if not base_url:
        pytest.skip("set NEXT_UI_BASE_URL to run the served UI smoke test")
    playwright = pytest.importorskip("playwright.sync_api")
    errors: list[str] = []

    with playwright.sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text)
            if message.type == "error" else None,
        )
        response = page.goto(f"{base_url.rstrip('/')}/next", wait_until="networkidle")

        assert response is not None and response.ok
        assert page.get_by_role("heading", name="Initialize story", exact=True).is_visible(), errors
        assert page.get_by_role("navigation", name="Primary navigation").is_visible()
        assert page.get_by_role("link", name="Legacy UI").get_attribute("href") == "/legacy"
        assert page.locator('button[data-workspace="write"]').is_visible()
        _assert_no_serious_accessibility_violations(page, "initialization")
        page.get_by_label("Story title").fill("Browser Story")
        page.get_by_label("Premise").fill("A navigator searches for a vanished island.")
        page.get_by_role("button", name="Initialize story").click()
        page.get_by_role("heading", name="Story", exact=True).wait_for(state="visible")

        page.get_by_role("button", name="Settings", exact=True).click()
        page.get_by_role("heading", name="Experience profile").wait_for(state="visible")
        page.get_by_label("Named mode").select_option("sandbox")
        page.get_by_role("button", name="Preview migration").click()
        save_profile = page.get_by_role("button", name="Save profile revision")
        save_profile.wait_for(state="visible")
        save_profile.click()
        page.get_by_text("Experience profile revision 2 saved").wait_for(state="visible")
        assert page.locator("#mode-badge").inner_text().strip().lower() == "sandbox"
        _assert_no_serious_accessibility_violations(page, "settings")

        page.get_by_role("button", name="Story", exact=True).click()
        page.get_by_role("heading", name="World Topology").wait_for(state="visible")
        location_form = page.get_by_role("form", name="Add location")
        location_form.locator('input[name="id"]').fill("harbor")
        location_form.locator('input[name="name"]').fill("Harbor")
        location_form.locator('input[name="region_id"]').fill("coast")
        location_form.get_by_role("button", name="Add immutable revision").click()
        page.get_by_role("heading", name="harbor", exact=True).wait_for(state="visible")
        location_form.locator('input[name="id"]').fill("island")
        location_form.locator('input[name="name"]').fill("Island")
        location_form.locator('input[name="region_id"]').fill("coast")
        location_form.get_by_role("button", name="Add immutable revision").click()
        page.get_by_role("heading", name="island", exact=True).wait_for(state="visible")
        route_form = page.get_by_role("form", name="Add route")
        route_form.locator('input[name="id"]').fill("ferry")
        route_form.locator('select[name="source"]').select_option("harbor")
        route_form.locator('select[name="destination"]').select_option("island")
        route_form.get_by_role("button", name="Add immutable revision").click()
        page.get_by_role("heading", name="ferry", exact=True).wait_for(state="visible")
        fixture_form = page.get_by_role("form", name="Add simulation fixture")
        fixture_form.locator('input[name="id"]').fill("storm_watch")
        fixture_form.locator('input[name="label"]').fill("Storm watch")
        fixture_form.locator('select[name="start_location"]').select_option("harbor")
        fixture_form.locator('input[name="character_id"]').fill("captain")
        fixture_form.locator('input[name="energy"]').fill("7")
        fixture_form.locator('input[name="faction_id"]').fill("wardens")
        fixture_form.locator('input[name="influence"]').fill("0.7")
        fixture_form.get_by_role("button", name="Add fixture revision").click()
        page.get_by_role("button", name="Run fixture").click()
        page.locator(".simulation-panel").wait_for(state="visible")
        assert page.locator(".simulation-panel").get_by_text("1", exact=True).count() >= 1
        page.get_by_role("button", name="Travel to Island").click()
        page.locator(".simulation-panel").get_by_text("island", exact=True).wait_for(state="visible")
        _assert_no_serious_accessibility_violations(page, "sandbox simulation")

        page.get_by_role("button", name="World", exact=True).click()
        character_form = page.locator(".world-layout form.compact-form").nth(0)
        character_form.locator('input[name="id"]').fill("captain")
        character_form.locator('input[name="name"]').fill("Captain Vale")
        character_form.locator('textarea[name="description"]').fill("Harbor master")
        character_form.get_by_role("button", name="Create character").click()
        page.get_by_text("character: captain", exact=True).wait_for(state="visible")
        markdown = page.get_by_label("Markdown")
        markdown.fill(markdown.input_value() + "\nKeeps the tide ledger.\n")
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.get_by_role("button", name="Media", exact=True).click()
        page.get_by_role("heading", name="World", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Save with fingerprint").click()
        page.get_by_text("Character saved", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Media", exact=True).click()
        page.get_by_role("heading", name="Media", exact=True).wait_for(state="visible")
        _assert_no_serious_accessibility_violations(page, "world and media")

        # Keyboard navigation, narrow layout, and 200% zoom remain functional.
        page.keyboard.press("g")
        page.keyboard.press("t")
        page.get_by_role("heading", name="Tests", exact=True).wait_for(state="visible")
        assert page.locator("#workspace").evaluate("element => element === document.activeElement")
        page.set_viewport_size({"width": 720, "height": 900})
        assert page.get_by_role("navigation", name="Primary navigation").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.evaluate("document.documentElement.style.zoom = '2'")
        assert page.get_by_role("heading", name="Tests", exact=True).is_visible()
        assert page.get_by_role("button", name="Story", exact=True).is_visible()
        _assert_no_serious_accessibility_violations(page, "tests at narrow 200 percent zoom")
        assert not errors, errors
        browser.close()


@pytest.mark.e2e
def test_next_ui_plan_review_reload_diagnostics_conflict_commit_and_fact_review():
    base_url = os.environ.get("NEXT_UI_BASE_URL", "")
    if not base_url:
        pytest.skip("set NEXT_UI_BASE_URL to run the served UI workflow")
    playwright = pytest.importorskip("playwright.sync_api")
    errors: list[str] = []
    plan = {
        "schema_version": 1, "plan_id": "browser_review_plan", "revision": 1,
        "passage_mode": "normal",
        "narrative_slots": [{"id": "body", "kind": "paragraph", "speaker": ""}],
        "choice_slots": [
            {"id": "continue", "destination": "next_passage", "conditions": [{"target": "weather_safe", "operation": "truthy", "value": None}], "effects": [], "weight": 1, "restart": False},
            {"id": "wait", "destination": "wait_here", "conditions": [], "effects": [], "weight": 1, "restart": False},
        ],
        "allowed_state_refs": ["weather_safe"], "allowed_entity_refs": [], "allowed_effects": [],
        "required_components": [], "mechanic_slots": [], "fixed_effects": [],
        "eligibility": [], "form_fields": [], "exits": [],
        "loop_binding": None, "context_fingerprint": "", "experience_profile_fingerprint": "",
        "repeatable": False, "reentry_policy": "forbid", "time_cost": None,
        "cooldown": None, "expiry": None,
    }
    current = {
        "draft": {
            "draft_id": "draft_browser_review", "revision": 1, "plan": plan,
            "fill": {
                "schema_version": 1, "plan_id": "browser_review_plan", "plan_revision": 1, "revision": 1,
                "narrative": [{"slot_id": "body", "kind": "paragraph", "speaker": "", "parts": [{"kind": "text", "text": "The harbor waits."}]}],
                "choices": [
                    {"slot_id": "continue", "text": "Continue", "hint": "Move on."},
                    {"slot_id": "wait", "text": "Wait", "hint": "Stay."},
                ],
                "summary": "A harbor choice.", "beats": ["Choose."], "continuity_proposals": [],
            },
        },
        "lifecycle_state": "validated",
        "diagnostics": [{"code": "choice_copy_too_similar", "level": "warning", "message": "Revise the second choice.", "path": ["fill", "choices", 1, "text"]}],
        "compile_artifact": {
            "schema_version": 1, "twee_source": ":: browser_review\nThe harbor waits.",
            "state_reads": [], "state_writes": [], "link_targets": ["next_passage", "wait_here"],
            "media_placeholders": [], "diagnostics": [], "compiler_version": "browser-fixture-v1",
            "source_draft_fingerprint": "a" * 64, "source_map": [],
        },
        "passage_id": "browser_review", "arc_name": "main", "parent_fingerprint": "",
    }
    commit_attempts = 0
    compile_attempts = 0
    playtest_request = {}
    hold_playtest = False
    playtest_polls = 0
    playtest_job = {
        "job_id": "playtest_browser", "status": "completed",
        "draft_id": "draft_browser_review", "draft_revision": 1,
        "draft_fingerprint": "a" * 64,
        "created_at": "2026-08-14T00:00:00Z", "updated_at": "2026-08-14T00:00:01Z",
        "result": {
            "passed": True, "tweego_compile": True, "browser_load": True,
            "choice_reachability": True, "choice_effect_execution": None,
            "runtime_state_transaction": None, "continuity_after_navigation": None,
            "form_binding": None, "hostile_text_safe": None,
            "runtime_errors": [], "details": [],
        },
        "error_code": "", "error_message": "",
    }

    with playwright.sync_playwright() as runtime:
        browser = _launch_chromium(runtime)
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

        def typed_generate(route):
            route.fulfill(status=200, json=current)

        def draft_routes(route):
            nonlocal current, commit_attempts, compile_attempts, playtest_request
            url = route.request.url
            if url.endswith("/edit"):
                body = route.request.post_data_json
                current = deepcopy(current)
                current["draft"]["revision"] = 2
                current["draft"]["fill"] = body["fill"]
                current["draft"]["fill"]["revision"] = 2
                current["lifecycle_state"] = "edited"
                route.fulfill(status=200, json=current)

            elif url.endswith("/validate"):
                assert len(route.request.post_data_json["expected_draft_fingerprint"]) == 64
                current = deepcopy(current)
                current["lifecycle_state"] = "validated"
                route.fulfill(status=200, json=current)
            elif url.endswith("/compile"):
                compile_attempts += 1
                route.fulfill(status=200, json={
                    "draft_id": current["draft"]["draft_id"],
                    "draft_revision": current["draft"]["revision"],
                    "draft_fingerprint": "a" * 64,
                    "artifact": current["compile_artifact"],
                    "persisted_artifact_match": compile_attempts > 1,
                })
            elif url.endswith("/playtest"):
                playtest_request = route.request.post_data_json
                route.fulfill(status=202, json={**playtest_job, "status": "queued", "result": None})
            elif url.endswith("/commit"):
                commit_attempts += 1
                if commit_attempts == 1:
                    current = deepcopy(current)
                    current["parent_fingerprint"] = "fresh-parent"
                    route.fulfill(status=409, json={"detail": {"code": "parent_fingerprint_conflict", "message": "Parent changed"}})
                else:
                    assert route.request.post_data_json["expected_parent_fingerprint"] == "fresh-parent"
                    route.fulfill(status=200, json={"status": "committed", "passage_id": "browser_review", "pending_facts": [
                        {"key": "harbor_bell", "value": "The harbor bell is cracked.", "evidence_slot_ids": ["body"]},
                        {"key": "tide_clock", "value": "The tide clock runs slow.", "evidence_slot_ids": ["body"]},
                    ]})
            elif "/facts/" in url:
                route.fulfill(status=200, json={"status": "recorded", "key": url.split("/facts/")[1].split("/")[0]})
            else:
                route.fulfill(status=200, json=current)

        def poll_playtest(route):
            nonlocal playtest_polls
            playtest_polls += 1
            route.fulfill(status=200, json={**playtest_job, "status": "queued", "result": None} if hold_playtest else playtest_job)

        page.route("**/api/typed/generate", typed_generate)
        page.route("**/api/drafts/draft_browser_review**", draft_routes)
        page.route("**/api/playtests/playtest_browser", poll_playtest)
        page.goto(f"{base_url.rstrip('/')}/next", wait_until="networkidle")
        if page.get_by_role("heading", name="Initialize story", exact=True).is_visible():
            page.get_by_label("Story title").fill("Review Story")
            page.get_by_label("Premise").fill("A plan review fixture.")
            page.get_by_role("button", name="Initialize story").click()
            page.get_by_role("heading", name="Story", exact=True).wait_for(state="visible")

        page.get_by_role("button", name="Write", exact=True).click()
        page.get_by_label("Plan ID").fill("browser_review_plan")
        page.get_by_label("Author direction").fill("Write a tense harbor decision.")
        structure = page.get_by_label("Passage structure")
        structure.select_option("form")
        form_group = page.get_by_role("group", name="Form fields")
        form_group.get_by_role("button", name="Add form field").click()
        assert form_group.get_by_label("Kind").locator("option").all_text_contents() == [
            "textbox", "numberbox", "textarea", "checkbox", "radiobutton", "listbox", "cycle",
        ]
        form_group.get_by_role("button", name="Remove field").click()
        structure.select_option("room")
        room_group = page.get_by_role("group", name="Room exits")
        room_group.get_by_role("button", name="Add room exit").click()
        room_group.get_by_role("button", name="Remove exit").click()
        structure.select_option("loop")
        page.get_by_label("Enable trusted loop").check()
        page.get_by_label("Enable trusted loop").uncheck()
        structure.select_option("random")
        page.get_by_label("Random weight").first.fill("3")
        structure.select_option("random_event")
        page.get_by_label("Event chance (%)").fill("37")
        structure.select_option("conditional")
        page.get_by_label("Fallback passage").fill("locked_harbor")
        structure.select_option("ending")
        page.get_by_label("Restart ending").first.check()
        page.get_by_label("Restart ending").first.uncheck()
        structure.select_option("normal")
        page.get_by_label("State references").fill("weather_safe, gold")
        first_choice = page.get_by_role("group", name="Trusted choice slots").locator("article").first
        first_choice.get_by_role("button", name="Add condition").click()
        first_choice.get_by_role("group", name="Choice guards").get_by_label("State target").fill("weather_safe")
        first_choice.get_by_role("button", name="Add effect").click()
        choice_effect = first_choice.get_by_role("group", name="Choice effects")
        choice_effect.get_by_label("Component ID").fill("fare")
        choice_effect.get_by_label("State target").fill("gold")
        choice_effect.get_by_label("Operation").select_option("subtract")
        choice_effect.get_by_label("Value").fill("2")
        _assert_no_serious_accessibility_violations(page, "structured passage mechanics")
        page.get_by_role("button", name="Save plan for review").click()
        try:
            page.get_by_role("heading", name="Review passage plan", exact=True).wait_for(state="visible")
        except playwright.TimeoutError as exc:
            raise AssertionError(f"review plan did not render; browser errors: {errors}") from exc
        assert page.get_by_text("continue → next_passage", exact=False).is_visible()
        assert page.get_by_text("1 guards · 1 effects", exact=False).is_visible()
        _assert_no_serious_accessibility_violations(page, "passage plan review")
        page.get_by_role("button", name="Approve plan and generate").click()
        page.get_by_text("choice_copy_too_similar", exact=True).wait_for(state="visible")
        _assert_no_serious_accessibility_violations(page, "draft diagnostics")

        page.get_by_role("button", name="choice_copy_too_similar").click()
        assert page.get_by_role("tab", name="Choices").get_attribute("aria-selected") == "true"
        wait_input = page.locator('[data-diagnostic-slot="wait"] input')
        page.wait_for_function(
            "element => element === document.activeElement",
            arg=wait_input.element_handle(),
        )
        wait_input.fill("Remain at the harbor")
        assert page.get_by_role("button", name="Commit exact revision").is_disabled()
        choices_tab = page.get_by_role("tab", name="Choices")
        choices_tab.focus()
        choices_tab.press("ArrowRight")
        assert page.get_by_role("tab", name="Mechanics").get_attribute("aria-selected") == "true"
        assert page.get_by_text("State reads", exact=True).is_visible()
        page.get_by_role("tab", name="Preview").click()
        page.get_by_label("weather_safe").fill("true")
        page.get_by_text("Advanced: compiled Twee and source mapping", exact=True).click()
        assert page.get_by_text(":: browser_review", exact=False).is_visible()
        assert page.get_by_role("list", name="Draft review stages").get_by_text("Playtest", exact=True).is_visible()
        page.get_by_role("tab", name="Choices").click()
        page.get_by_role("button", name="Save revision").click()
        page.get_by_text("Saved as a new immutable revision", exact=True).wait_for(state="visible")

        page.reload(wait_until="networkidle")
        page.get_by_text("Draft draft_browser_review · revision 2", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Validate").click()
        page.get_by_role("button", name="Compile exact revision").click()
        page.get_by_text("Compiler output differs from the persisted preview", exact=True).wait_for(state="visible")
        assert page.get_by_role("list", name="Draft review stages").get_by_text("failed", exact=True).count() >= 1
        assert page.get_by_role("button", name="Run isolated playtest").is_disabled()
        page.get_by_role("button", name="Compile exact revision").click()
        page.get_by_text("Exact draft compilation reproduced", exact=True).wait_for(state="visible")
        page.get_by_role("tab", name="Preview").click()
        page.get_by_label("weather_safe").fill("true")
        page.get_by_role("group", name="Preview width").get_by_role("button", name="Mobile").click()
        assert page.locator('[data-preview-width="mobile"]').is_visible()
        page.get_by_role("button", name="Test choice Continue").click()
        page.locator(".toast.ok").get_by_text("Choice continue passed", exact=True).wait_for(state="visible")
        assert playtest_request["choice_slot_ids"] == ["continue"]
        assert playtest_request["initial_state"] == {"weather_safe": True}
        page.get_by_role("button", name="Run isolated playtest").click()
        page.locator(".toast.ok").get_by_text("Isolated playtest passed", exact=True).wait_for(state="visible")
        assert playtest_request["initial_state"] == {"weather_safe": True}
        assert "choice_slot_ids" not in playtest_request
        assert page.get_by_role("list", name="Draft review stages").get_by_text("passed", exact=True).count() >= 4
        hold_playtest = True
        page.get_by_role("button", name="Run isolated playtest").click()
        page.get_by_role("button", name="Story", exact=True).click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('h2')].some((node) => ['Story', 'World Topology'].includes(node.textContent?.trim()))"
        )
        polls_after_navigation = playtest_polls
        page.wait_for_timeout(1200)
        assert playtest_polls == polls_after_navigation
        hold_playtest = False
        page.get_by_role("button", name="Write", exact=True).click()
        page.get_by_text("Draft draft_browser_review · revision 2", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Commit exact revision").click()
        page.get_by_text("The trusted parent or plan changed.", exact=False).wait_for(state="visible")
        assert page.get_by_role("button", name="Commit exact revision").is_disabled()
        page.reload(wait_until="networkidle")
        page.get_by_text("Draft draft_browser_review · revision 2", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Commit exact revision").click()
        page.get_by_role("heading", name="Review proposed facts", exact=True).wait_for(state="visible")
        _assert_no_serious_accessibility_violations(page, "continuity fact review")
        page.get_by_role("button", name="Reject", exact=True).first.click()
        page.get_by_role("button", name="Accept into continuity lore", exact=True).click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('h2')].some((node) => ['Story', 'World Topology'].includes(node.textContent?.trim()))"
        )
        unexpected_errors = [item for item in errors if "409 (Conflict)" not in item]
        assert not unexpected_errors, unexpected_errors
        browser.close()

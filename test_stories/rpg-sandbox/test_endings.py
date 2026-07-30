"""Test all three endings of Shadows of Thornwood.

This script navigates through the complete quest chain to reach the Final
Confrontation, then tests each of the three ending paths:
1. Seal the breach (Ending Seal)
2. Claim the power (Ending Power)
3. Ritual of Binding (Ending Ritual - requires INT >= 13)
"""
import os, time, json
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/data/.playwright")
from playwright.sync_api import sync_playwright

HTML_PATH = "/opt/data/rpg-sandbox/build/story.html"


def click_link(page, text):
    link = page.query_selector(f'.passage a:has-text("{text}")')
    if not link:
        link = page.query_selector(f'a:has-text("{text}")')
    if link:
        link.click()
        page.wait_for_timeout(500)
        return True
    return False


def get_state(page):
    return page.evaluate("() => window.SugarCube ? JSON.parse(JSON.stringify(window.SugarCube.State.variables)) : null")


def get_passage(page):
    return page.evaluate("() => window.SugarCube ? window.SugarCube.State.passage : ''")


def play_to_final_confrontation(page, class_choice="Mage"):
    """Play through all 3 quests to reach the Final Confrontation."""
    page.goto(f"file://{HTML_PATH}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(1)

    # Character creation - use Mage for INT >= 13 (needed for ritual ending)
    if class_choice == "Mage":
        click_link(page, "Choose Your Character")
        time.sleep(0.3)
        click_link(page, "Choose Mage")
        time.sleep(0.3)
        click_link(page, "Enter Thornwood")
    else:
        click_link(page, "Skip to a predefined character")
        time.sleep(0.3)
        click_link(page, "Enter Thornwood")
    time.sleep(0.5)

    # Talk to Mara - start wolf quest
    click_link(page, "Visit Elder Mara")
    time.sleep(0.5)
    click_link(page, "handle the wolves")
    time.sleep(0.3)

    # Go to forest and kill 5 wolves
    click_link(page, "Go South to the Forest")
    time.sleep(0.3)
    click_link(page, "Follow the main path deeper")
    time.sleep(0.3)

    for i in range(5):
        if not click_link(page, "Fight the wolves"):
            click_link(page, "Continue fighting")
        time.sleep(0.3)

    state = get_state(page)
    assert state and state.get("quest_wolf_kills", 0) >= 5, f"Failed to kill 5 wolves: {state.get('quest_wolf_kills') if state else 'no state'}"

    # Return to Mara - complete wolf quest, get new quests
    click_link(page, "Return to the entrance")
    time.sleep(0.3)
    click_link(page, "Return to Thornwood")
    time.sleep(0.3)
    click_link(page, "Visit Elder Mara")
    time.sleep(0.5)
    state = get_state(page)
    passage = get_passage(page)
    print(f"  Mara passage: {passage}, wolf_kills: {state.get('quest_wolf_kills') if state else 'none'}")
    # Click the return link (may be "find Tomas" or "Return to the square")
    if not click_link(page, "find Tomas"):
        click_link(page, "I'll find Tomas")
    time.sleep(0.3)
    state = get_state(page)
    print(f"  After Mara: quest_lost_traveler={state.get('quest_lost_traveler') if state else 'none'}, quest_artifact={state.get('quest_artifact') if state else 'none'}")

    # Go to forest, find Tomas at river
    click_link(page, "Go South to the Forest")
    time.sleep(0.3)
    click_link(page, "Follow the river path")
    time.sleep(0.5)

    # Return to town with Tomas
    click_link(page, "Help Tomas back to town")
    time.sleep(0.5)

    # Tell Elara - she's in the Tavern, link says "woman" if not met yet
    elara_link = page.query_selector('.passage a:has-text("Elara")')
    if not elara_link:
        click_link(page, "Enter the Tavern")
        time.sleep(0.3)
        elara_link = page.query_selector('.passage a:has-text("Elara")')
        if not elara_link:
            elara_link = page.query_selector('.passage a:has-text("woman")')
    if elara_link:
        elara_link.click()
        time.sleep(0.5)

    state = get_state(page)
    assert state and state.get("quest_lost_traveler") == "completed", f"Lost traveler quest not completed: {state.get('quest_lost_traveler') if state else 'no state'}"

    # Return to square, go to forest, take hidden trail to shrine
    click_link(page, "Return to the square")
    time.sleep(0.3)
    click_link(page, "Go South to the Forest")
    time.sleep(0.3)
    if not click_link(page, "Take the hidden trail to the shrine"):
        click_link(page, "Follow the main path deeper")
        time.sleep(0.3)
        click_link(page, "Take the hidden trail to the shrine")
    time.sleep(0.5)

    # Take amulet
    click_link(page, "Take the amulet")
    time.sleep(0.5)

    state = get_state(page)
    assert state and state.get("amulet_recovered"), "Amulet not recovered"

    # Return to Mara to learn her secret
    click_link(page, "Return to the forest entrance")
    time.sleep(0.3)
    click_link(page, "Return to Thornwood")
    time.sleep(0.3)
    click_link(page, "Visit Elder Mara")
    time.sleep(0.5)

    # Mara should acknowledge the amulet
    click_link(page, "Return to the square")
    time.sleep(0.3)

    # Navigate to Castle Ruins -> Final Confrontation
    click_link(page, "Go North to the Old Keep")
    time.sleep(0.5)
    click_link(page, "Descend into the crypts")
    time.sleep(0.5)

    # In the crypt, use amulet to seal
    click_link(page, "Use the amulet to seal the breach")
    time.sleep(0.5)

    passage = get_passage(page)
    assert passage == "Final Confrontation", f"Expected Final Confrontation, got {passage}"
    print(f"  Reached Final Confrontation! (class: {class_choice})")
    return True


def test_ending(page, ending_name, ending_link_text, expected_passage):
    """Test a single ending by clicking the appropriate link."""
    # Click the ending choice
    if not click_link(page, ending_link_text):
        print(f"  FAIL: Could not find '{ending_link_text}' link")
        return False

    time.sleep(0.5)
    passage = get_passage(page)

    if passage == expected_passage:
        state = get_state(page)
        print(f"  PASS: {ending_name} -> {passage}")
        if state:
            print(f"    XP: {state.get('xp')}, Level: {state.get('level')}, Gold: {state.get('gold')}")
        return True
    else:
        print(f"  FAIL: Expected {expected_passage}, got {passage}")
        return False


def run_ending_tests():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        print("\n=== ENDING TEST: Seal the Breach ===")
        context.clear_cookies()
        page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch(e) {} }")
        play_to_final_confrontation(page, class_choice="Warrior")
        results.append(("Seal the Breach", test_ending(page, "Seal", "Seal the breach", "Ending Seal")))

        print("\n=== ENDING TEST: Claim the Power ===")
        # Need a fresh page to clear SugarCube state completely
        page.close()
        page = context.new_page()
        page.on("pageerror", lambda err: js_errors.append(str(err)))
        play_to_final_confrontation(page, class_choice="Warrior")
        results.append(("Claim the Power", test_ending(page, "Power", "Claim the power", "Ending Power")))

        print("\n=== ENDING TEST: Ritual of Binding (requires INT >= 13) ===")
        page.close()
        page = context.new_page()
        page.on("pageerror", lambda err: js_errors.append(str(err)))
        play_to_final_confrontation(page, class_choice="Mage")  # Mage has INT 15
        # Check if the ritual link appears (requires INT >= 13)
        ritual_link = page.query_selector('.passage a:has-text("Attempt the ritual")')
        if ritual_link:
            results.append(("Ritual of Binding", test_ending(page, "Ritual", "Attempt the ritual", "Ending Ritual")))
        else:
            print("  SKIP: Ritual link not found (INT may be too low)")
            results.append(("Ritual of Binding", False))

        print("\n=== JS Error Check ===")
        if js_errors:
            print(f"  FAIL: {len(js_errors)} JS errors: {js_errors[:3]}")
            results.append(("No JS Errors", False))
        else:
            print("  PASS: No JS errors")
            results.append(("No JS Errors", True))

        browser.close()

    print("\n" + "=" * 50)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"ENDING TESTS: {passed}/{total} passed")
    for name, result in results:
        print(f"  [{'PASS' if result else 'FAIL'}] {name}")
    return passed == total


if __name__ == "__main__":
    success = run_ending_tests()
    exit(0 if success else 1)

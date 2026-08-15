import { describe, expect, it } from "vitest";

import { initialPlanMechanics, serializePlanMechanics } from "./PlanMechanicsEditor";

describe("structured PassagePlan mechanics", () => {
  it("serializes every harness-owned mechanic without a raw JSON escape hatch", () => {
    const state = initialPlanMechanics();
    state.narrative_slots = [{ id: "line", kind: "dialogue", speaker: "Captain" }];
    state.allowed_state_refs = ["weather_safe", "gold", "items", "item"];
    state.allowed_entity_refs = ["captain"];
    state.required_components = ["inventory"];
    state.choice_slots = [{
      id: "sail", destination: "open_sea", weight: 3, restart: false,
      conditions: [{ target: "weather_safe", operation: "truthy", value: "" }],
      effects: [{ component_id: "fare", target: "gold", operation: "subtract", value: "2", source: "" }],
    }];
    state.fixed_effects = [{ component_id: "clock", target: "gold", operation: "add", value: "-1", source: "" }];
    state.allowed_effects = [{ component_id: "copy_gold", target: "gold", operation: "set", value: "", source: "gold" }];
    state.mechanic_slots = [{ id: "reward", required: false, allowed_operations: ["add"], allowed_targets: ["gold"] }];
    state.form_fields = [{
      id: "ship_name", kind: "listbox", label: "Ship", default: "\"northstar\"",
      unchecked_value: "", checked_value: "", autofocus: false, autocheck: false,
      checked: false, once: true, autoselect: true,
      options: [{ label: "Northstar", value: "northstar", selected: true }],
    }];
    state.exits = [{ label: "North", destination: "north_room" }];
    state.loop_binding = { variable: "item", collection: "items" };
    state.repeatable = true;
    state.reentry_policy = "refresh";
    state.time_cost = "2";
    state.cooldown = "3";
    state.expiry = "10";
    state.eligibility = [{ target: "gold", operation: "gte", value: "2" }];
    state.fallback_passage = "harbor";
    state.event_odds = 37;

    expect(serializePlanMechanics(state)).toMatchObject({
      narrative_slots: [{ id: "line", kind: "dialogue", speaker: "Captain" }],
      choice_slots: [{
        id: "sail", destination: "open_sea", weight: 3,
        conditions: [{ target: "weather_safe", operation: "truthy", value: null }],
        effects: [{ component_id: "fare", target: "gold", operation: "subtract", value: 2, source: "" }],
      }],
      fixed_effects: [{ component_id: "clock", target: "gold", operation: "add", value: -1, source: "" }],
      allowed_effects: [{ component_id: "copy_gold", target: "gold", operation: "set", value: null, source: "gold" }],
      form_fields: [{ id: "ship_name", kind: "listbox", default: "northstar" }],
      exits: [{ label: "North", destination: "north_room" }],
      loop_binding: { variable: "item", collection: "items" },
      repeatable: true,
      reentry_policy: "refresh",
      time_cost: 2,
      cooldown: 3,
      expiry: 10,
      eligibility: [{ target: "gold", operation: "gte", value: 2 }],
      fallback_passage: "harbor",
      event_odds: 37,
    });
  });
});

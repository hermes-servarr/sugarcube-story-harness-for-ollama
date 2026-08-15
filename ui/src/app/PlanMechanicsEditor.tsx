import type { PassagePlan } from "../types";

type ConditionOperation = "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "truthy" | "falsy";
type StateOperation = "set" | "add" | "subtract" | "toggle";
type NarrativeKind = "paragraph" | "dialogue" | "thought";
type FormKind = "textbox" | "numberbox" | "textarea" | "checkbox" | "radiobutton" | "listbox" | "cycle";

export interface ConditionDraft { target: string; operation: ConditionOperation; value: string }
export interface EffectDraft { component_id: string; target: string; operation: StateOperation; value: string; source: string }
export interface NarrativeSlotDraft { id: string; kind: NarrativeKind; speaker: string }
export interface ChoiceSlotDraft {
  id: string;
  destination: string;
  weight: number;
  restart: boolean;
  conditions: ConditionDraft[];
  effects: EffectDraft[];
}
export interface MechanicSlotDraft { id: string; required: boolean; allowed_operations: StateOperation[]; allowed_targets: string[] }
export interface FormOptionDraft { label: string; value: string; selected: boolean }
export interface FormFieldDraft {
  id: string;
  kind: FormKind;
  label: string;
  default: string;
  unchecked_value: string;
  checked_value: string;
  options: FormOptionDraft[];
  autofocus: boolean;
  autocheck: boolean;
  checked: boolean;
  once: boolean;
  autoselect: boolean;
}
export interface RouteDraft { label: string; destination: string }
export interface PlanMechanicsState {
  narrative_slots: NarrativeSlotDraft[];
  choice_slots: ChoiceSlotDraft[];
  allowed_state_refs: string[];
  allowed_entity_refs: string[];
  allowed_effects: EffectDraft[];
  fixed_effects: EffectDraft[];
  required_components: string[];
  mechanic_slots: MechanicSlotDraft[];
  form_fields: FormFieldDraft[];
  exits: RouteDraft[];
  loop_binding: { variable: string; collection: string } | null;
  repeatable: boolean;
  reentry_policy: "forbid" | "allow" | "refresh";
  time_cost: string;
  cooldown: string;
  eligibility: ConditionDraft[];
  expiry: string;
  fallback_passage: string;
  event_odds: number;
}

export const initialPlanMechanics = (): PlanMechanicsState => ({
  narrative_slots: [{ id: "body", kind: "paragraph", speaker: "" }],
  choice_slots: [
    { id: "continue", destination: "next_passage", weight: 1, restart: false, conditions: [], effects: [] },
    { id: "wait", destination: "wait_here", weight: 1, restart: false, conditions: [], effects: [] },
  ],
  allowed_state_refs: [],
  allowed_entity_refs: [],
  allowed_effects: [],
  fixed_effects: [],
  required_components: [],
  mechanic_slots: [],
  form_fields: [],
  exits: [],
  loop_binding: null,
  repeatable: false,
  reentry_policy: "forbid",
  time_cost: "",
  cooldown: "",
  eligibility: [],
  expiry: "",
  fallback_passage: "",
  event_odds: 100,
});

function valueFromInput(value: string): unknown {
  if (!value.trim()) return null;
  try { return JSON.parse(value); } catch { return value; }
}

function optionalInteger(value: string): number | null {
  return value.trim() ? Number(value) : null;
}

function effectValue(effect: EffectDraft) {
  return {
    component_id: effect.component_id,
    target: effect.target,
    operation: effect.operation,
    value: valueFromInput(effect.value),
    source: effect.source,
  };
}

function conditionValue(condition: ConditionDraft) {
  return {
    target: condition.target,
    operation: condition.operation,
    value: ["truthy", "falsy"].includes(condition.operation) ? null : valueFromInput(condition.value),
  };
}

export function serializePlanMechanics(value: PlanMechanicsState): Pick<PassagePlan,
  "narrative_slots" | "choice_slots" | "allowed_state_refs" | "allowed_entity_refs" |
  "allowed_effects" | "fixed_effects" | "required_components" | "mechanic_slots" |
  "form_fields" | "exits" | "loop_binding" | "repeatable" | "reentry_policy" |
  "time_cost" | "cooldown" | "eligibility" | "expiry"
  | "fallback_passage" | "event_odds"
> {
  return {
    narrative_slots: value.narrative_slots,
    choice_slots: value.choice_slots.map((choice) => ({
      ...choice,
      conditions: choice.conditions.map(conditionValue),
      effects: choice.effects.map(effectValue),
    })),
    allowed_state_refs: value.allowed_state_refs,
    allowed_entity_refs: value.allowed_entity_refs,
    allowed_effects: value.allowed_effects.map(effectValue),
    fixed_effects: value.fixed_effects.map(effectValue),
    required_components: value.required_components,
    mechanic_slots: value.mechanic_slots,
    form_fields: value.form_fields.map((field) => ({
      ...field,
      default: valueFromInput(field.default),
    })),
    exits: value.exits,
    loop_binding: value.loop_binding,
    repeatable: value.repeatable,
    reentry_policy: value.reentry_policy,
    time_cost: optionalInteger(value.time_cost),
    cooldown: optionalInteger(value.cooldown),
    eligibility: value.eligibility.map(conditionValue),
    expiry: optionalInteger(value.expiry),
    fallback_passage: value.fallback_passage,
    event_odds: value.event_odds,
  };
}

function updateAt<T>(items: T[], index: number, update: Partial<T>): T[] {
  return items.map((item, itemIndex) => itemIndex === index ? { ...item, ...update } : item);
}

function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, itemIndex) => itemIndex !== index);
}

function csv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function ConditionEditor({ title, items, onChange }: { title: string; items: ConditionDraft[]; onChange: (items: ConditionDraft[]) => void }) {
  return <fieldset className="mechanic-group wide"><legend>{title}</legend>
    {items.map((item, index) => <div className="mechanic-row" key={index}>
      <label>State target<input required pattern="[a-z][a-z0-9_]{0,63}" value={item.target} onChange={(event) => onChange(updateAt(items, index, { target: event.target.value }))} /></label>
      <label>Condition<select value={item.operation} onChange={(event) => onChange(updateAt(items, index, { operation: event.target.value as ConditionOperation }))}>{["eq", "ne", "gt", "gte", "lt", "lte", "truthy", "falsy"].map((operation) => <option key={operation}>{operation}</option>)}</select></label>
      <label>Value<input disabled={["truthy", "falsy"].includes(item.operation)} value={item.value} placeholder="JSON value" onChange={(event) => onChange(updateAt(items, index, { value: event.target.value }))} /></label>
      <button type="button" onClick={() => onChange(removeAt(items, index))}>Remove</button>
    </div>)}
    <button type="button" onClick={() => onChange([...items, { target: "state_flag", operation: "truthy", value: "" }])}>Add condition</button>
  </fieldset>;
}

function EffectEditor({ title, items, onChange }: { title: string; items: EffectDraft[]; onChange: (items: EffectDraft[]) => void }) {
  return <fieldset className="mechanic-group wide"><legend>{title}</legend>
    {items.map((item, index) => <div className="mechanic-row effect-row" key={index}>
      <label>Component ID<input required pattern="[a-z][a-z0-9_]{0,63}" value={item.component_id} onChange={(event) => onChange(updateAt(items, index, { component_id: event.target.value }))} /></label>
      <label>State target<input required pattern="[a-z][a-z0-9_]{0,63}" value={item.target} onChange={(event) => onChange(updateAt(items, index, { target: event.target.value }))} /></label>
      <label>Operation<select value={item.operation} onChange={(event) => onChange(updateAt(items, index, { operation: event.target.value as StateOperation }))}>{["set", "add", "subtract", "toggle"].map((operation) => <option key={operation}>{operation}</option>)}</select></label>
      <label>Value<input disabled={item.operation === "toggle" || Boolean(item.source)} value={item.value} placeholder="JSON value" onChange={(event) => onChange(updateAt(items, index, { value: event.target.value }))} /></label>
      <label>Or source state<input disabled={item.operation === "toggle"} pattern="[a-z][a-z0-9_]{0,63}" value={item.source} onChange={(event) => onChange(updateAt(items, index, { source: event.target.value }))} /></label>
      <button type="button" onClick={() => onChange(removeAt(items, index))}>Remove</button>
    </div>)}
    <button type="button" onClick={() => onChange([...items, { component_id: `effect_${items.length + 1}`, target: "state_value", operation: "set", value: "true", source: "" }])}>Add effect</button>
  </fieldset>;
}

function ChoiceEditor({ mode, items, onChange }: { mode: string; items: ChoiceSlotDraft[]; onChange: (items: ChoiceSlotDraft[]) => void }) {
  return <fieldset className="mechanic-group wide"><legend>Trusted choice slots</legend>
    <div className="plan-stack">{items.map((choice, index) => <article className="plan-card" key={index}>
      <div className="mechanic-row">
        <label>Slot ID<input required pattern="[a-z][a-z0-9_]{0,63}" value={choice.id} onChange={(event) => onChange(updateAt(items, index, { id: event.target.value }))} /></label>
        <label>Destination<input value={choice.destination} onChange={(event) => onChange(updateAt(items, index, { destination: event.target.value }))} /></label>
        {mode === "random" && <label>Random weight<input type="number" min="1" value={choice.weight} onChange={(event) => onChange(updateAt(items, index, { weight: Number(event.target.value) }))} /></label>}
        {mode === "ending" && <label className="checkbox-label"><input type="checkbox" checked={choice.restart} onChange={(event) => onChange(updateAt(items, index, { restart: event.target.checked }))} /> Restart ending</label>}
        <button type="button" disabled={items.length <= 1} onClick={() => onChange(removeAt(items, index))}>Remove choice</button>
      </div>
      <ConditionEditor title="Choice guards" items={choice.conditions} onChange={(conditions) => onChange(updateAt(items, index, { conditions }))} />
      <EffectEditor title="Choice effects" items={choice.effects} onChange={(effects) => onChange(updateAt(items, index, { effects }))} />
    </article>)}</div>
    <button type="button" onClick={() => onChange([...items, { id: `choice_${items.length + 1}`, destination: "next_passage", weight: 1, restart: false, conditions: [], effects: [] }])}>Add choice slot</button>
  </fieldset>;
}

function FormFieldEditor({ items, onChange }: { items: FormFieldDraft[]; onChange: (items: FormFieldDraft[]) => void }) {
  return <fieldset className="mechanic-group wide"><legend>Form fields</legend>
    <div className="plan-stack">{items.map((field, index) => <article className="plan-card" key={index}>
      <div className="mechanic-row">
        <label>Field ID<input required pattern="[a-z][a-z0-9_]{0,63}" value={field.id} onChange={(event) => onChange(updateAt(items, index, { id: event.target.value }))} /></label>
        <label>Kind<select value={field.kind} onChange={(event) => onChange(updateAt(items, index, { kind: event.target.value as FormKind }))}>{["textbox", "numberbox", "textarea", "checkbox", "radiobutton", "listbox", "cycle"].map((kind) => <option key={kind}>{kind}</option>)}</select></label>
        <label>Label<input value={field.label} onChange={(event) => onChange(updateAt(items, index, { label: event.target.value }))} /></label>
        <label>Default<input value={field.default} placeholder="JSON value" onChange={(event) => onChange(updateAt(items, index, { default: event.target.value }))} /></label>
        <label>Unchecked value<input value={field.unchecked_value} onChange={(event) => onChange(updateAt(items, index, { unchecked_value: event.target.value }))} /></label>
        <label>Checked value<input value={field.checked_value} onChange={(event) => onChange(updateAt(items, index, { checked_value: event.target.value }))} /></label>
        {["autofocus", "autocheck", "checked", "once", "autoselect"].map((flag) => <label className="checkbox-label" key={flag}><input type="checkbox" checked={field[flag as keyof FormFieldDraft] as boolean} onChange={(event) => onChange(updateAt(items, index, { [flag]: event.target.checked }))} /> {flag}</label>)}
        <button type="button" onClick={() => onChange(removeAt(items, index))}>Remove field</button>
      </div>
      <fieldset className="mechanic-group"><legend>Options</legend>{field.options.map((option, optionIndex) => <div className="mechanic-row" key={optionIndex}>
        <label>Option label<input required value={option.label} onChange={(event) => onChange(updateAt(items, index, { options: updateAt(field.options, optionIndex, { label: event.target.value }) }))} /></label>
        <label>Value<input value={option.value} onChange={(event) => onChange(updateAt(items, index, { options: updateAt(field.options, optionIndex, { value: event.target.value }) }))} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={option.selected} onChange={(event) => onChange(updateAt(items, index, { options: updateAt(field.options, optionIndex, { selected: event.target.checked }) }))} /> Selected</label>
        <button type="button" onClick={() => onChange(updateAt(items, index, { options: removeAt(field.options, optionIndex) }))}>Remove option</button>
      </div>)}<button type="button" onClick={() => onChange(updateAt(items, index, { options: [...field.options, { label: `Option ${field.options.length + 1}`, value: `option_${field.options.length + 1}`, selected: false }] }))}>Add option</button></fieldset>
    </article>)}</div>
    <button type="button" onClick={() => onChange([...items, { id: `field_${items.length + 1}`, kind: "textbox", label: "", default: "", unchecked_value: "", checked_value: "", options: [], autofocus: false, autocheck: false, checked: false, once: false, autoselect: false }])}>Add form field</button>
  </fieldset>;
}

export function PlanMechanicsEditor({ mode, value, onChange }: { mode: string; value: PlanMechanicsState; onChange: (value: PlanMechanicsState) => void }) {
  const set = <K extends keyof PlanMechanicsState>(key: K, next: PlanMechanicsState[K]) => onChange({ ...value, [key]: next });
  return <details className="wide mechanics-authoring" open><summary>Structured passage authority</summary>
    <p>These controls are harness-owned. Generated prose may fill the approved slots but cannot alter destinations, guards, effects, forms, routes, or lifecycle rules.</p>
    <fieldset className="mechanic-group"><legend>Narrative slots</legend><div className="plan-stack">{value.narrative_slots.map((slot, index) => <div className="mechanic-row plan-card" key={index}>
      <label>Slot ID<input required pattern="[a-z][a-z0-9_]{0,63}" value={slot.id} onChange={(event) => set("narrative_slots", updateAt(value.narrative_slots, index, { id: event.target.value }))} /></label>
      <label>Kind<select value={slot.kind} onChange={(event) => { const kind = event.target.value as NarrativeKind; set("narrative_slots", updateAt(value.narrative_slots, index, { kind, speaker: kind === "dialogue" ? slot.speaker : "" })); }}>{["paragraph", "dialogue", "thought"].map((kind) => <option key={kind}>{kind}</option>)}</select></label>
      <label>Fixed speaker<input disabled={slot.kind !== "dialogue"} value={slot.speaker} onChange={(event) => set("narrative_slots", updateAt(value.narrative_slots, index, { speaker: event.target.value }))} /></label>
      <button type="button" disabled={value.narrative_slots.length <= 1} onClick={() => set("narrative_slots", removeAt(value.narrative_slots, index))}>Remove slot</button>
    </div>)}</div><button type="button" onClick={() => set("narrative_slots", [...value.narrative_slots, { id: `narrative_${value.narrative_slots.length + 1}`, kind: "paragraph", speaker: "" }])}>Add narrative slot</button></fieldset>
    <ChoiceEditor mode={mode} items={value.choice_slots} onChange={(items) => set("choice_slots", items)} />
    <fieldset className="mechanic-group"><legend>Reference allowlists</legend><div className="mechanic-row">
      <label>State references<span>comma-separated stable IDs</span><input value={value.allowed_state_refs.join(", ")} onChange={(event) => set("allowed_state_refs", csv(event.target.value))} /></label>
      <label>Entity references<span>comma-separated stable IDs</span><input value={value.allowed_entity_refs.join(", ")} onChange={(event) => set("allowed_entity_refs", csv(event.target.value))} /></label>
      <label>Required components<span>comma-separated component names</span><input value={value.required_components.join(", ")} onChange={(event) => set("required_components", csv(event.target.value))} /></label>
    </div></fieldset>
    <ConditionEditor title="Passage eligibility" items={value.eligibility} onChange={(items) => set("eligibility", items)} />
    {mode === "conditional" && <fieldset className="mechanic-group"><legend>Conditional routing</legend><label>Fallback passage<input required value={value.fallback_passage} onChange={(event) => set("fallback_passage", event.target.value)} /></label></fieldset>}
    {mode === "random_event" && <fieldset className="mechanic-group"><legend>Random event</legend><label>Event chance (%)<input type="number" min="1" max="100" required value={value.event_odds} onChange={(event) => set("event_odds", Number(event.target.value))} /></label></fieldset>}
    <EffectEditor title="Fixed plan effects" items={value.fixed_effects} onChange={(items) => set("fixed_effects", items)} />
    <EffectEditor title="Allowlisted effect templates" items={value.allowed_effects} onChange={(items) => set("allowed_effects", items)} />
    <fieldset className="mechanic-group"><legend>Mechanic proposal slots</legend><div className="plan-stack">{value.mechanic_slots.map((slot, index) => <div className="mechanic-row plan-card" key={index}>
      <label>Slot ID<input required pattern="[a-z][a-z0-9_]{0,63}" value={slot.id} onChange={(event) => set("mechanic_slots", updateAt(value.mechanic_slots, index, { id: event.target.value }))} /></label>
      <label>Allowed targets<input value={slot.allowed_targets.join(", ")} onChange={(event) => set("mechanic_slots", updateAt(value.mechanic_slots, index, { allowed_targets: csv(event.target.value) }))} /></label>
      <fieldset className="toggle-grid"><legend>Allowed operations</legend>{["set", "add", "subtract", "toggle"].map((operation) => <label key={operation}><input type="checkbox" checked={slot.allowed_operations.includes(operation as StateOperation)} onChange={(event) => set("mechanic_slots", updateAt(value.mechanic_slots, index, { allowed_operations: event.target.checked ? [...slot.allowed_operations, operation as StateOperation] : slot.allowed_operations.filter((item) => item !== operation) }))} />{operation}</label>)}</fieldset>
      <label className="checkbox-label" title="Required proposal slots are enabled only with the deliberately deferred typed_staged strategy"><input type="checkbox" disabled checked={slot.required} /> Required (typed_staged unavailable)</label>
      <button type="button" onClick={() => set("mechanic_slots", removeAt(value.mechanic_slots, index))}>Remove slot</button>
    </div>)}</div><button type="button" onClick={() => set("mechanic_slots", [...value.mechanic_slots, { id: `mechanic_${value.mechanic_slots.length + 1}`, required: false, allowed_operations: [], allowed_targets: [] }])}>Add proposal slot</button></fieldset>
    {(mode === "form" || value.form_fields.length > 0) && <FormFieldEditor items={value.form_fields} onChange={(items) => set("form_fields", items)} />}
    {(mode === "room" || value.exits.length > 0) && <fieldset className="mechanic-group"><legend>Room exits</legend>{value.exits.map((route, index) => <div className="mechanic-row" key={index}><label>Label<input required value={route.label} onChange={(event) => set("exits", updateAt(value.exits, index, { label: event.target.value }))} /></label><label>Destination<input required value={route.destination} onChange={(event) => set("exits", updateAt(value.exits, index, { destination: event.target.value }))} /></label><button type="button" onClick={() => set("exits", removeAt(value.exits, index))}>Remove exit</button></div>)}<button type="button" onClick={() => set("exits", [...value.exits, { label: `Exit ${value.exits.length + 1}`, destination: "next_room" }])}>Add room exit</button></fieldset>}
    {(mode === "loop" || value.loop_binding) && <fieldset className="mechanic-group"><legend>Loop binding</legend><label className="checkbox-label"><input type="checkbox" checked={Boolean(value.loop_binding)} onChange={(event) => set("loop_binding", event.target.checked ? { variable: "item", collection: "items" } : null)} /> Enable trusted loop</label>{value.loop_binding && <div className="mechanic-row"><label>Loop variable<input required pattern="[a-z][a-z0-9_]{0,63}" value={value.loop_binding.variable} onChange={(event) => set("loop_binding", { ...value.loop_binding!, variable: event.target.value })} /></label><label>Collection state<input required pattern="[a-z][a-z0-9_]{0,63}" value={value.loop_binding.collection} onChange={(event) => set("loop_binding", { ...value.loop_binding!, collection: event.target.value })} /></label></div>}</fieldset>}
    <fieldset className="mechanic-group"><legend>Lifecycle and timing</legend><div className="mechanic-row">
      <label className="checkbox-label"><input type="checkbox" checked={value.repeatable} onChange={(event) => set("repeatable", event.target.checked)} /> Repeatable</label>
      <label>Re-entry policy<select value={value.reentry_policy} onChange={(event) => set("reentry_policy", event.target.value as PlanMechanicsState["reentry_policy"])}><option>forbid</option><option>allow</option><option>refresh</option></select></label>
      <label>Time cost<input type="number" min="0" value={value.time_cost} onChange={(event) => set("time_cost", event.target.value)} /></label>
      <label>Cooldown<input type="number" min="0" value={value.cooldown} onChange={(event) => set("cooldown", event.target.value)} /></label>
      <label>Expiry<input type="number" min="0" value={value.expiry} onChange={(event) => set("expiry", event.target.value)} /></label>
    </div></fieldset>
  </details>;
}

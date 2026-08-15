import {
  Component,
  type ErrorInfo,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiClient, ApiFailure } from "../api";
import type {
  BenchmarkRunDetail,
  BenchmarkRunSummary,
  Diagnostic,
  DraftPlaytestJob,
  DraftRecord,
  ExperienceMigrationPreview,
  ExperienceProfile,
  ExperienceProfileState,
  HarnessConfig,
  MediaSlot,
  LocationNode,
  OllamaStatus,
  PassageEntry,
  PassagePlanRecord,
  PassagePlan,
  StoryGraph,
  SimulationState,
  SimulationFixture,
  TopologyState,
  TopologyRoute,
  ValidationResult,
  WorldSheet,
  ContinuityProposal,
} from "../types";
import {
  initialPlanMechanics,
  PlanMechanicsEditor,
  serializePlanMechanics,
  type PlanMechanicsState,
} from "./PlanMechanicsEditor";

type Workspace = "story" | "write" | "world" | "media" | "tests" | "settings";
type Notice = { id: number; message: string; tone: "ok" | "error" };
type EditablePart = DraftRecord["draft"]["fill"]["narrative"][number]["parts"][number];

const api = new ApiClient();
const workspaceItems: Array<[Workspace, string]> = [
  ["story", "Story"], ["write", "Write"], ["world", "World"],
  ["media", "Media"], ["tests", "Tests"], ["settings", "Settings"],
];

function errorText(error: unknown) {
  if (error instanceof ApiFailure) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : String(error);
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info); }
  render() {
    if (!this.state.error) return this.props.children;
    return <main className="error-card"><h1>Story Harness Next</h1><strong>The interface stopped safely.</strong><p>{this.state.error.message}</p><button onClick={() => location.reload()}>Reload</button> <a href="/legacy">Open legacy UI</a></main>;
  }
}

function WorkspaceHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <header className="workspace-head"><div><span className="eyebrow">Workspace</span><h2>{title}</h2><p>{description}</p></div>{action}</header>;
}

function InitializationWorkspace({ config, onInitialized, notify }: { config: HarnessConfig; onInitialized: (title: string) => void; notify: (message: string, tone?: Notice["tone"]) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError(""); const data = new FormData(event.currentTarget);
    try {
      const title = String(data.get("title"));
      await api.initializeStory({ title, premise: data.get("premise"), tone: data.get("tone"), themes: data.get("themes"), world_overview: data.get("world_overview"), opening_situation: data.get("opening_situation"), story_points: data.get("story_points"), characters: [], locations: [] });
      onInitialized(title); notify("Story foundation initialized");
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  };
  return <><WorkspaceHeader title="Initialize story" description="Capture author intent before planning or generation. These files remain editable after setup." />{error && <Failure message={error} />}<form className="panel form-grid" onSubmit={(event) => void submit(event)}><label>Story title<input name="title" required defaultValue={config.story_title === "Untitled Story" ? "" : config.story_title} /></label><label>Tone<input name="tone" /></label><label className="wide">Premise<textarea name="premise" required rows={5} /></label><label>Themes<textarea name="themes" rows={3} /></label><label>World overview<textarea name="world_overview" rows={3} /></label><label className="wide">Opening situation<textarea name="opening_situation" rows={3} /></label><label className="wide">Story points<textarea name="story_points" rows={5} placeholder="One beat per line" /></label><div className="wide callout">Initialization writes explicit premise and planning sources; it does not generate or commit passages.</div><button className="primary" disabled={busy}>{busy ? "Initializing…" : "Initialize story"}</button></form></>;
}

function PanelTitle({ title, meta }: { title: string; meta?: ReactNode }) {
  return <div className="panel-title"><h3>{title}</h3><span>{meta}</span></div>;
}

function Empty({ children }: { children: ReactNode }) { return <div className="empty"><p>{children}</p></div>; }

function useLoad<T>(load: () => Promise<T>, dependencies: React.DependencyList = []) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    let live = true;
    setError("");
    load().then((result) => live && setValue(result)).catch((reason) => live && setError(errorText(reason)));
    return () => { live = false; };
    // The caller supplies stable primitive dependencies; load itself is deliberately excluded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, nonce]);
  return { value, error, reload: () => setNonce((item) => item + 1) };
}

function StoryWorkspace() {
  const graphState = useLoad(async () => { const [graph, plan] = await Promise.all([api.graph(), api.plan()]); return { graph, plan }; });
  const [passage, setPassage] = useState<(PassageEntry & { raw: string }) | null>(null);
  const [passageError, setPassageError] = useState("");
  const [planError, setPlanError] = useState("");
  if (graphState.error) return <Failure message={graphState.error} retry={graphState.reload} />;
  if (!graphState.value) return <div className="loading">Loading story…</div>;
  const passages = Object.entries(graphState.value.graph.passages || {});
  const inspect = async (id: string) => {
    setPassageError("");
    try { setPassage(await api.passage(id)); } catch (error) { setPassageError(errorText(error)); }
  };
  const mutatePlan = async (action: () => Promise<unknown>) => {
    setPlanError("");
    try { await action(); graphState.reload(); return true; }
    catch (reason) {
      setPlanError(errorText(reason));
      if (reason instanceof ApiFailure && reason.code === "story_plan_conflict") graphState.reload();
      return false;
    }
  };
  const listValue = (data: FormData, name: string) => String(data.get(name) || "").split(",").map((item) => item.trim()).filter(Boolean);
  const createBeat = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setPlanError(""); const form = event.currentTarget; const data = new FormData(form); try { await api.createBeat(String(data.get("text")), String(data.get("act") || ""), graphState.value!.plan.story_fingerprint); form.reset(); graphState.reload(); } catch (reason) { setPlanError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "story_plan_conflict") graphState.reload(); } };
  const createArc = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setPlanError(""); const form = event.currentTarget; const data = new FormData(form); try { await api.createArc(String(data.get("name")), String(data.get("goal") || ""), graphState.value!.plan.story_fingerprint); form.reset(); graphState.reload(); } catch (reason) { setPlanError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "story_plan_conflict") graphState.reload(); } };
  return <><WorkspaceHeader title="Story" description="Plan author intent and read branch structure through graph-independent accessible outlines." action={<button onClick={graphState.reload}>Refresh</button>} />
    <div className="two-column"><section className="panel"><PanelTitle title="Passage outline" meta={`${passages.length} passages`} />
      <ol className="passage-list">{passages.map(([id, item]) => <li key={id}><button onClick={() => void inspect(id)}><strong>{item.title || id}</strong><span>{item.passage_type || item.type || "normal"}</span></button></li>)}</ol>
      {!passages.length && <Empty>No passages yet. Start in Write to create the first typed draft.</Empty>}
    </section><section className="panel detail">{passageError ? <Failure message={passageError} /> : passage ? <PassageDetail passage={passage} /> : <Empty>Choose a passage to inspect its source metadata and outgoing choices.</Empty>}</section></div>
    {planError && <Failure message={planError} />}<div className="two-column planning-panels"><section className="panel"><PanelTitle title="Story beats" meta={graphState.value.plan.beats.length} /><div className="plan-stack">{graphState.value.plan.beats.length ? graphState.value.plan.beats.map((beat) => <form className="compact-form plan-card" key={beat.id} onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void mutatePlan(() => api.updateBeat(beat.id, String(data.get("text")), String(data.get("act") || ""), graphState.value!.plan.story_fingerprint)); }}><h4>{beat.id} · {beat.status}</h4><label className="wide">Beat<input name="text" required defaultValue={beat.text} /></label><label>Act<input name="act" defaultValue={beat.act} /></label><div className="actions"><button className="primary">Save</button><button type="button" className="danger" onClick={() => { if (window.confirm(`Delete beat ${beat.id}? Arc and passage references will also be removed.`)) void mutatePlan(() => api.deleteBeat(beat.id, graphState.value!.plan.story_fingerprint)); }}>Delete</button></div></form>) : <Empty>No planned beats.</Empty>}</div><form className="compact-form" onSubmit={(event) => void createBeat(event)}><h4>Add beat</h4><label className="wide">Beat<input name="text" required /></label><label>Act<input name="act" /></label><button className="primary">Add beat</button></form></section><section className="panel"><PanelTitle title="Arcs and scenes" meta={graphState.value.plan.arcs.length} /><div className="plan-stack">{graphState.value.plan.arcs.length ? graphState.value.plan.arcs.map((arc) => <details className="plan-card" key={arc.arc}><summary><strong>{arc.arc}</strong> · {arc.scenes.length} scenes · {arc.passage_count} passages</summary><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void mutatePlan(() => api.updateArc(arc.arc, { goal: String(data.get("goal") || ""), summary: String(data.get("summary") || ""), status: String(data.get("status") || "planned"), beat_ids: listValue(data, "beat_ids") }, graphState.value!.plan.story_fingerprint)); }}><h4>Arc plan</h4><label className="wide">Goal<input name="goal" defaultValue={arc.goal} /></label><label className="wide">Summary<textarea name="summary" rows={3} defaultValue={arc.summary} /></label><label>Status<input name="status" defaultValue={arc.status} /></label><label>Beat IDs<input name="beat_ids" defaultValue={arc.beat_ids.join(", ")} /></label><button className="primary">Save arc</button></form><div className="scene-list">{arc.scenes.map((scene) => <form className="compact-form" key={scene.id} onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void mutatePlan(() => api.updateScene(arc.arc, scene.id, { title: String(data.get("title") || ""), summary: String(data.get("summary") || ""), status: String(data.get("status") || "planned"), keywords: listValue(data, "keywords"), characters: listValue(data, "characters"), beat_ids: listValue(data, "beat_ids") }, graphState.value!.plan.story_fingerprint)); }}><h4>{scene.id}</h4><label>Title<input name="title" defaultValue={scene.title} /></label><label>Status<input name="status" defaultValue={scene.status} /></label><label className="wide">Summary<textarea name="summary" rows={2} defaultValue={scene.summary} /></label><label>Keywords<input name="keywords" defaultValue={scene.keywords.join(", ")} /></label><label>Characters<input name="characters" defaultValue={scene.characters.join(", ")} /></label><label>Beat IDs<input name="beat_ids" defaultValue={scene.beat_ids.join(", ")} /></label><div className="actions"><button className="primary">Save scene</button><button type="button" className="danger" onClick={() => { if (window.confirm(`Delete scene ${scene.id}?`)) void mutatePlan(() => api.deleteScene(arc.arc, scene.id, graphState.value!.plan.story_fingerprint)); }}>Delete</button></div></form>)}</div><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); void mutatePlan(() => api.createScene(arc.arc, { title: String(data.get("title") || ""), summary: String(data.get("summary") || ""), keywords: listValue(data, "keywords"), characters: listValue(data, "characters"), beat_ids: listValue(data, "beat_ids") }, graphState.value!.plan.story_fingerprint)).then((ok) => { if (ok) form.reset(); }); }}><h4>Add scene</h4><label>Title<input name="title" required /></label><label>Keywords<input name="keywords" placeholder="comma separated" /></label><label className="wide">Summary<textarea name="summary" rows={2} /></label><label>Characters<input name="characters" /></label><label>Beat IDs<input name="beat_ids" /></label><button className="primary">Add scene</button></form></details>) : <Empty>No planned arcs.</Empty>}</div><form className="compact-form" onSubmit={(event) => void createArc(event)}><h4>Add arc</h4><label>Name<input name="name" required /></label><label>Goal<input name="goal" /></label><button className="primary">Add arc</button></form></section></div></>;
}

function PassageDetail({ passage }: { passage: PassageEntry & { raw: string } }) {
  return <><PanelTitle title={String(passage.title || passage.id || "Passage")} meta={String(passage.passage_type || passage.type || "normal")} />
    <dl className="facts"><dt>File</dt><dd>{String(passage.file || "—")}</dd><dt>Passage ID</dt><dd>{String(passage.id || "—")}</dd></dl>
    <h4>Outgoing choices</h4><ul>{passage.choices?.length ? passage.choices.map((choice, index) => <li key={index}>{choice.text || "Choice"} → {choice.target || choice.child || "unresolved"}</li>) : <li>None</li>}</ul></>;
}

function SystemicStoryWorkspace({ mode, notify }: { mode: "hybrid" | "sandbox"; notify: (message: string, tone?: Notice["tone"]) => void }) {
  type AuthoredTopology = TopologyState & { topology: NonNullable<TopologyState["topology"]> };
  const loaded = useLoad(async () => {
    const [topology, systems, encounters, fixtures] = await Promise.all([
      api.topology(), api.systems(), api.encounters(), api.simulationFixtures(),
    ]);
    return { topology, systems, encounters, fixtures };
  });
  const [topology, setTopology] = useState<AuthoredTopology | null>(null);
  const [simulation, setSimulation] = useState<SimulationState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { if (loaded.value) setTopology(loaded.value.topology.topology ? loaded.value.topology as AuthoredTopology : null); }, [loaded.value]);
  if (loaded.error) return <Failure message={loaded.error} retry={loaded.reload} />;
  if (!loaded.value) return <div className="loading">Loading world topology…</div>;
  const world = loaded.value;
  const handleTopologyError = (reason: unknown) => {
    setError(errorText(reason));
    if (reason instanceof ApiFailure && reason.code === "topology_conflict") loaded.reload();
  };

  const addLocation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy("location"); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    try {
      const next = await api.addLocation(topology?.topology.revision || 0, { id: data.get("id"), name: data.get("name"), region_id: data.get("region_id"), tags: [], actions: [], encounter_table_refs: [] });
      setTopology(next as AuthoredTopology); form.reset(); notify("Location revision saved");
    } catch (reason) { handleTopologyError(reason); } finally { setBusy(""); }
  };
  const addRoute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!topology) return; setBusy("route"); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    try {
      const next = await api.addRoute(topology.topology.revision, { id: data.get("id"), source: data.get("source"), destination: data.get("destination"), eligibility: [], resource_cost: {}, travel_effects: [], risk_tags: [], time_cost: Number(data.get("time_cost")) });
      setTopology(next as AuthoredTopology); form.reset(); notify("Route revision saved");
    } catch (reason) { handleTopologyError(reason); } finally { setBusy(""); }
  };
  const editLocation = async (event: FormEvent<HTMLFormElement>, location: LocationNode) => {
    event.preventDefault(); if (!topology) return; setBusy(location.id); setError(""); const data = new FormData(event.currentTarget);
    try { setTopology(await api.updateLocation(location.id, topology.topology.revision, { ...location, name: String(data.get("name")), region_id: String(data.get("region_id")), tags: String(data.get("tags") || "").split(",").map((item) => item.trim()).filter(Boolean) }) as AuthoredTopology); notify("Location revision saved"); }
    catch (reason) { handleTopologyError(reason); } finally { setBusy(""); }
  };
  const editRoute = async (event: FormEvent<HTMLFormElement>, route: TopologyRoute) => {
    event.preventDefault(); if (!topology) return; setBusy(route.id); setError(""); const data = new FormData(event.currentTarget);
    try { setTopology(await api.updateRoute(route.id, topology.topology.revision, { ...route, source: String(data.get("source")), destination: String(data.get("destination")), time_cost: Number(data.get("time_cost")) }) as AuthoredTopology); notify("Route revision saved"); }
    catch (reason) { handleTopologyError(reason); } finally { setBusy(""); }
  };
  const startSimulation = async (fixtureId?: string) => {
    if (!topology || (!fixtureId && topology.topology.locations.length === 0)) return; setBusy("simulation"); setError("");
    try { setSimulation(await api.createSimulation(fixtureId ? { fixture_id: fixtureId } : { start_location: topology.topology.locations[0].id, seed: 1, world_state: {}, resources: {} })); notify("Disposable simulation started"); }
    catch (reason) { setError(errorText(reason)); } finally { setBusy(""); }
  };
  const act = async (kind: string, actionId: string) => {
    if (!simulation) return; setBusy(actionId); setError("");
    try { setSimulation(await api.applySimulationAction(simulation.session.session_id, simulation.session.revision, kind, actionId)); }
    catch (reason) { setError(errorText(reason)); } finally { setBusy(""); }
  };
  const addSystemRule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy("system"); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    const rawValue = String(data.get("value") || "");
    const value = rawValue === "true" ? true : rawValue === "false" ? false : rawValue !== "" && Number.isFinite(Number(rawValue)) ? Number(rawValue) : rawValue;
    const rule = { id: String(data.get("id")), trigger: String(data.get("trigger")), priority: Number(data.get("priority") || 0), conditions: [], cooldown_ticks: 0, occurrence_limit: null, effects: [{ component_id: `${String(data.get("id"))}_effect`, target: String(data.get("target")), operation: String(data.get("operation")), value }] };
    try { await api.updateSystems([...world.systems.catalog.rules, rule], world.systems.fingerprint); form.reset(); loaded.reload(); notify("System rule revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "system_catalog_conflict") loaded.reload(); }
    finally { setBusy(""); }
  };
  const addEncounter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy("encounter"); setError("");
    const form = event.currentTarget; const data = new FormData(form); const id = String(data.get("id"));
    const locationIds = String(data.get("location_ids") || "").split(",").map((item) => item.trim()).filter(Boolean);
    const template = { id, label: String(data.get("label")), weight: Number(data.get("weight") || 1), location_ids: locationIds, required_tags: [], eligibility: [], cooldown_ticks: Number(data.get("cooldown_ticks") || 0), occurrence_limit: null, variation_slots: ["body", "continue"], plan: { plan_id: `${id}_plan`, revision: 1, passage_mode: "normal", narrative_slots: [{ id: "body", kind: "paragraph", speaker: "" }], choice_slots: [{ id: "continue", destination: String(data.get("destination")) }], allowed_state_refs: [], allowed_entity_refs: [], required_components: [], repeatable: true, reentry_policy: "refresh" } };
    try { await api.updateEncounters([...world.encounters.catalog.templates, template], world.encounters.fingerprint); form.reset(); loaded.reload(); notify("Encounter template revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "encounter_catalog_conflict") loaded.reload(); }
    finally { setBusy(""); }
  };
  const editSystemRule = async (event: FormEvent<HTMLFormElement>, rule: Record<string, unknown> & { id: string }) => {
    event.preventDefault(); setBusy(rule.id); setError(""); const data = new FormData(event.currentTarget);
    try { await api.updateSystems(world.systems.catalog.rules.map((item) => item.id === rule.id ? { ...item, trigger: String(data.get("trigger")), priority: Number(data.get("priority") || 0) } : item), world.systems.fingerprint); loaded.reload(); notify("System rule revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "system_catalog_conflict") loaded.reload(); } finally { setBusy(""); }
  };
  const editEncounter = async (event: FormEvent<HTMLFormElement>, template: Record<string, unknown> & { id: string }) => {
    event.preventDefault(); setBusy(template.id); setError(""); const data = new FormData(event.currentTarget);
    try { await api.updateEncounters(world.encounters.catalog.templates.map((item) => item.id === template.id ? { ...item, label: String(data.get("label")), weight: Number(data.get("weight") || 1), cooldown_ticks: Number(data.get("cooldown_ticks") || 0), location_ids: String(data.get("location_ids") || "").split(",").map((part) => part.trim()).filter(Boolean) } : item), world.encounters.fingerprint); loaded.reload(); notify("Encounter template revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "encounter_catalog_conflict") loaded.reload(); } finally { setBusy(""); }
  };
  const addSimulationFixture = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!topology) return; setBusy("fixture"); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    const characterId = String(data.get("character_id") || "").trim();
    const factionId = String(data.get("faction_id") || "").trim();
    const startLocation = String(data.get("start_location"));
    const initialEnergy = Number(data.get("energy") || 5);
    const fixture: SimulationFixture = {
      id: String(data.get("id")), label: String(data.get("label")), start_location: startLocation,
      seed: Number(data.get("seed") || 1), world_state: {}, resources: {},
      character_stat_definitions: characterId ? [{ id: "energy", value_type: "int", default: initialEnergy, minimum: 0, maximum: 10, visibility: "model", allowed_operations: ["set", "add", "clamp"], decay_per_tick: null, description: "Current energy" }] : [],
      characters: characterId ? [{ character_id: characterId, revision: 1, current_location: startLocation, activity: "idle", stats: { energy: initialEnergy } }] : [],
      factions: factionId ? [{ faction_id: factionId, influence: Number(data.get("influence") || 0), disposition: Number(data.get("disposition") || 0), resources: {}, relationships: {} }] : [],
    };
    try { await api.updateSimulationFixtures([...world.fixtures.catalog.fixtures, fixture], world.fixtures.fingerprint); form.reset(); loaded.reload(); notify("Simulation fixture revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "simulation_fixture_catalog_conflict") loaded.reload(); }
    finally { setBusy(""); }
  };
  const editSimulationFixture = async (event: FormEvent<HTMLFormElement>, fixture: SimulationFixture) => {
    event.preventDefault(); setBusy(fixture.id); setError(""); const data = new FormData(event.currentTarget);
    const next = { ...fixture, label: String(data.get("label")), start_location: String(data.get("start_location")), seed: Number(data.get("seed") || 1) };
    try { await api.updateSimulationFixtures(world.fixtures.catalog.fixtures.map((item) => item.id === fixture.id ? next : item), world.fixtures.fingerprint); loaded.reload(); notify("Simulation fixture revision saved"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "simulation_fixture_catalog_conflict") loaded.reload(); } finally { setBusy(""); }
  };
  const deleteSimulationFixture = async (fixture: SimulationFixture) => {
    if (!window.confirm(`Delete simulation fixture ${fixture.id}?`)) return; setBusy(fixture.id); setError("");
    try { await api.updateSimulationFixtures(world.fixtures.catalog.fixtures.filter((item) => item.id !== fixture.id), world.fixtures.fingerprint); loaded.reload(); notify("Simulation fixture revision deleted"); }
    catch (reason) { setError(errorText(reason)); if (reason instanceof ApiFailure && reason.code === "simulation_fixture_catalog_conflict") loaded.reload(); } finally { setBusy(""); }
  };
  const locations = topology?.topology.locations || [], routes = topology?.topology.routes || [];
  return <><WorkspaceHeader title={mode === "sandbox" ? "World Topology" : "Hybrid Topology"} description="Author traversable places and inspect deterministic, disposable runtime traces without rewriting story canon." action={topology && <button disabled={!!busy || locations.length === 0} title={locations.length === 0 ? "Add a location before starting a simulation" : undefined} onClick={() => void startSimulation()}>Start simulation</button>} />
    {error && <Failure message={error} />}
    <div className="system-strip" aria-label="System state"><span>Topology r{topology?.topology.revision || 0}</span><span>{locations.length} locations</span><span>{routes.length} routes</span><span>{loaded.value.systems.catalog.rules.length} rules</span><span>{loaded.value.encounters.catalog.templates.length} encounters</span><span>{simulation ? `Tick ${simulation.session.clock.tick}` : "No active session"}</span></div>
    <div className="two-column"><section className="panel"><PanelTitle title="Locations" meta={locations.length} />{locations.length ? <div className="plan-stack">{locations.map((location) => <form className="compact-form plan-card" key={location.id} onSubmit={(event) => void editLocation(event, location)}><h4>{location.id}</h4><label>Name<input name="name" required defaultValue={location.name} /></label><label>Region ID<input name="region_id" required pattern="[a-z][a-z0-9_]{0,63}" defaultValue={location.region_id} /></label><label className="wide">Tags<input name="tags" defaultValue={location.tags.join(", ")} /></label><div className="actions wide"><button className="primary" disabled={!!busy}>Save</button><button type="button" className="danger" disabled={!!busy} onClick={() => { if (topology && window.confirm(`Delete location ${location.id}?`)) { setBusy(location.id); void api.deleteLocation(location.id, topology.topology.revision).then((next) => { setTopology(next as AuthoredTopology); notify("Location revision deleted"); }).catch(handleTopologyError).finally(() => setBusy("")); } }}>Delete</button></div></form>)}</div> : <Empty>Add the first stable location to initialize topology.</Empty>}
      <form aria-label="Add location" className="compact-form" onSubmit={(event) => void addLocation(event)}><h4>Add location</h4><label>ID<input name="id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>Name<input name="name" required /></label><label>Region ID<input name="region_id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><button className="primary" disabled={!!busy}>{busy === "location" ? "Saving…" : "Add immutable revision"}</button></form>
    </section><section className="panel"><PanelTitle title="Routes" meta={routes.length} />{routes.length ? <div className="plan-stack">{routes.map((route) => <form className="compact-form plan-card" key={route.id} onSubmit={(event) => void editRoute(event, route)}><h4>{route.id}</h4><label>From<select name="source" defaultValue={route.source}>{locations.map((item) => <option key={item.id}>{item.id}</option>)}</select></label><label>To<select name="destination" defaultValue={route.destination}>{locations.map((item) => <option key={item.id}>{item.id}</option>)}</select></label><label>Time cost<input name="time_cost" type="number" min="0" defaultValue={route.time_cost} /></label><div className="actions"><button className="primary" disabled={!!busy}>Save</button><button type="button" className="danger" disabled={!!busy} onClick={() => { if (topology && window.confirm(`Delete route ${route.id}?`)) { setBusy(route.id); void api.deleteRoute(route.id, topology.topology.revision).then((next) => { setTopology(next as AuthoredTopology); notify("Route revision deleted"); }).catch(handleTopologyError).finally(() => setBusy("")); } }}>Delete</button></div></form>)}</div> : <Empty>Add two locations before connecting them.</Empty>}
      {locations.length >= 2 && <form aria-label="Add route" className="compact-form" onSubmit={(event) => void addRoute(event)}><h4>Add route</h4><label>ID<input name="id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>From<select name="source">{locations.map((item) => <option key={item.id}>{item.id}</option>)}</select></label><label>To<select name="destination">{locations.map((item) => <option key={item.id}>{item.id}</option>)}</select></label><label>Time cost<input name="time_cost" type="number" min="0" defaultValue="1" /></label><button className="primary" disabled={!!busy}>{busy === "route" ? "Saving…" : "Add immutable revision"}</button></form>}
    </section></div>
    <div className="two-column systemic-catalogs"><section className="panel"><PanelTitle title="System rules" meta={world.systems.catalog.rules.length} />{world.systems.catalog.rules.length ? <div className="plan-stack">{world.systems.catalog.rules.map((rule) => <form className="compact-form plan-card" key={rule.id} onSubmit={(event) => void editSystemRule(event, rule)}><h4>{rule.id}</h4><label>Trigger<select name="trigger" defaultValue={rule.trigger}>{["tick", "local_action", "travel", "enter_location", "encounter"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<input name="priority" type="number" defaultValue={rule.priority} /></label><div className="actions wide"><button className="primary" disabled={!!busy}>Save</button><button type="button" className="danger" disabled={!!busy} onClick={() => { if (window.confirm(`Delete system rule ${rule.id}?`)) { setBusy(rule.id); void api.updateSystems(world.systems.catalog.rules.filter((item) => item.id !== rule.id), world.systems.fingerprint).then(() => { loaded.reload(); notify("System rule revision deleted"); }).catch((reason) => setError(errorText(reason))).finally(() => setBusy("")); } }}>Delete</button></div></form>)}</div> : <Empty>No authored system rules. The runtime still enforces route/action mechanics.</Empty>}<form className="compact-form" onSubmit={(event) => void addSystemRule(event)}><h4>Add bounded rule</h4><label>ID<input name="id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>Trigger<select name="trigger"><option>tick</option><option>local_action</option><option>travel</option><option>enter_location</option><option>encounter</option></select></label><label>State target<input name="target" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>Operation<select name="operation"><option>set</option><option>add</option><option>subtract</option><option>toggle</option></select></label><label>Value<input name="value" /></label><label>Priority<input name="priority" type="number" defaultValue="0" /></label><button className="primary" disabled={!!busy}>{busy === "system" ? "Saving…" : "Add rule revision"}</button></form></section><section className="panel"><PanelTitle title="Encounter templates" meta={world.encounters.catalog.templates.length} />{world.encounters.catalog.templates.length ? <div className="plan-stack">{world.encounters.catalog.templates.map((template) => <form className="compact-form plan-card" key={template.id} onSubmit={(event) => void editEncounter(event, template)}><h4>{template.id}</h4><label>Label<input name="label" required defaultValue={template.label} /></label><label>Weight<input name="weight" type="number" min="1" defaultValue={template.weight} /></label><label>Cooldown ticks<input name="cooldown_ticks" type="number" min="0" defaultValue={Number(template.cooldown_ticks || 0)} /></label><label>Location IDs<input name="location_ids" defaultValue={Array.isArray(template.location_ids) ? template.location_ids.join(", ") : ""} /></label><div className="actions wide"><button className="primary" disabled={!!busy}>Save</button><button type="button" className="danger" disabled={!!busy} onClick={() => { if (window.confirm(`Delete encounter ${template.id}?`)) { setBusy(template.id); void api.updateEncounters(world.encounters.catalog.templates.filter((item) => item.id !== template.id), world.encounters.fingerprint).then(() => { loaded.reload(); notify("Encounter template revision deleted"); }).catch((reason) => setError(errorText(reason))).finally(() => setBusy("")); } }}>Delete</button></div></form>)}</div> : <Empty>No reusable encounter templates.</Empty>}<form className="compact-form" onSubmit={(event) => void addEncounter(event)}><h4>Add reusable encounter</h4><label>ID<input name="id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>Label<input name="label" required /></label><label>Location IDs<input name="location_ids" placeholder="comma separated" /></label><label>Continue to passage<input name="destination" required pattern={"[A-Za-z0-9][A-Za-z0-9_\\x2d]{0,79}"} /></label><label>Weight<input name="weight" type="number" min="1" defaultValue="1" /></label><label>Cooldown ticks<input name="cooldown_ticks" type="number" min="0" defaultValue="0" /></label><button className="primary" disabled={!!busy}>{busy === "encounter" ? "Saving…" : "Add template revision"}</button></form></section></div>
    <section className="panel"><PanelTitle title="Simulation fixtures" meta={`${world.fixtures.catalog.fixtures.length} named states`} />
      {world.fixtures.catalog.fixtures.length ? <div className="plan-stack">{world.fixtures.catalog.fixtures.map((fixture) => <form className="compact-form plan-card" key={fixture.id} onSubmit={(event) => void editSimulationFixture(event, fixture)}><h4>{fixture.id}</h4><label>Label<input name="label" required defaultValue={fixture.label} /></label><label>Start location<select name="start_location" defaultValue={fixture.start_location}>{locations.map((location) => <option key={location.id}>{location.id}</option>)}</select></label><label>Seed<input name="seed" type="number" defaultValue={fixture.seed} /></label><div className="wide fixture-summary"><span>{fixture.characters.length} characters</span><span>{fixture.factions.length} factions</span></div><div className="actions wide"><button className="primary" disabled={!!busy}>Save</button><button type="button" disabled={!!busy} onClick={() => void startSimulation(fixture.id)}>Run fixture</button><button type="button" className="danger" disabled={!!busy} onClick={() => void deleteSimulationFixture(fixture)}>Delete</button></div></form>)}</div> : <Empty>No named fixture yet. Ad-hoc simulation remains available from the workspace header.</Empty>}
      {topology && <form aria-label="Add simulation fixture" className="compact-form" onSubmit={(event) => void addSimulationFixture(event)}><h4>Add named initial state</h4><label>ID<input name="id" required pattern="[a-z][a-z0-9_]{0,63}" /></label><label>Label<input name="label" required /></label><label>Start location<select name="start_location">{locations.map((location) => <option key={location.id}>{location.id}</option>)}</select></label><label>Seed<input name="seed" type="number" defaultValue="1" /></label><label>Character ID<input name="character_id" pattern="[a-z][a-z0-9_]{0,63}" placeholder="optional" /></label><label>Character energy<input name="energy" type="number" min="0" max="10" defaultValue="5" /></label><label>Faction ID<input name="faction_id" pattern="[a-z][a-z0-9_]{0,63}" placeholder="optional" /></label><label>Faction influence<input name="influence" type="number" min="0" max="1" step="0.1" defaultValue="0" /></label><label>Faction disposition<input name="disposition" type="number" min="-1" max="1" step="0.1" defaultValue="0" /></label><button className="primary" disabled={!!busy}>{busy === "fixture" ? "Saving…" : "Add fixture revision"}</button></form>}
    </section>
    {simulation && <section className="panel simulation-panel"><PanelTitle title="Disposable simulation" meta={`revision ${simulation.session.revision}`} /><div className="metric-row"><div><strong>{simulation.session.current_location}</strong><span>Current location</span></div><div><strong>{simulation.session.clock.tick}</strong><span>Clock tick</span></div><div><strong>{simulation.session.visits.length}</strong><span>Visits</span></div><div><strong>{simulation.session.characters.length}</strong><span>Characters</span></div><div><strong>{simulation.session.factions.length}</strong><span>Factions</span></div></div><h4>Eligible opportunities</h4>{simulation.opportunities.length ? <div className="opportunity-grid">{simulation.opportunities.map((item) => <button key={item.id} disabled={!!busy} onClick={() => void act(item.kind, item.source_id)}><strong>{item.label}</strong><span>{item.kind.replaceAll("_", " ")}</span></button>)}</div> : <Empty>No eligible action exists in this fixture state.</Empty>}<details><summary>Runtime state and visit trace</summary><pre>{JSON.stringify({ completed_anchors: simulation.session.completed_anchor_ids || [], characters: simulation.session.characters, factions: simulation.session.factions, visits: simulation.session.visits }, null, 2)}</pre></details></section>}
  </>;
}

function draftLocator(record: DraftRecord) { return `${record.draft.draft_id}:${record.draft.revision}`; }

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, nested]) => [key, canonical(nested)]));
  return value;
}

async function fingerprint(value: unknown) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(canonical(value))));
  return [...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("");
}

function editableParts(parts: EditablePart[]) {
  return parts.map((part) => part.kind === "text" ? String(part.text || "") : `{{${String(part.kind)}:${String(part.target)}}}`).join("");
}

function parseEditableParts(value: string) {
  const parts: EditablePart[] = [];
  const marker = /\{\{(state_ref|entity_ref):([a-z][a-z0-9_]{0,63})\}\}/g;
  let cursor = 0;
  for (const match of value.matchAll(marker)) {
    if (match.index > cursor) parts.push({ kind: "text", text: value.slice(cursor, match.index) });
    parts.push({ kind: match[1] as "state_ref" | "entity_ref", target: match[2] });
    cursor = match.index + match[0].length;
  }
  if (cursor < value.length) parts.push({ kind: "text", text: value.slice(cursor) });
  return parts.filter((part) => part.kind !== "text" || String(part.text).trim());
}

function planFromForm(form: HTMLFormElement, mechanics: PlanMechanicsState, revision = 1, fixedPlanId = ""): PassagePlan {
  const data = new FormData(form);
  return {
    schema_version: 1,
    plan_id: fixedPlanId || String(data.get("plan_id")),
    revision,
    passage_mode: String(data.get("passage_mode")) as PassagePlan["passage_mode"],
    ...serializePlanMechanics(mechanics),
    context_fingerprint: "",
    experience_profile_fingerprint: "",
  };
}

function WriteWorkspace({ notify, onCommitted }: { notify: (message: string, tone?: Notice["tone"]) => void; onCommitted: () => void }) {
  const [draft, setDraft] = useState<DraftRecord | null>(null);
  const [draftHash, setDraftHash] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [factReview, setFactReview] = useState<{ draftId: string; revision: number; proposals: ContinuityProposal[] } | null>(() => {
    try { return JSON.parse(sessionStorage.getItem("harness.next.pending_facts") || "null"); }
    catch { return null; }
  });
  useEffect(() => {
    let live = true;
    const stored = sessionStorage.getItem("harness.next.draft");
    if (!stored) { setLoading(false); return () => { live = false; }; }
    const [id] = stored.split(":");
    api.latestDraft(id).then(async (record) => {
      if (!live) return;
      if (record.lifecycle_state === "committed" && record.draft.fill.continuity_proposals?.length) {
        const review = { draftId: id, revision: record.draft.revision, proposals: record.draft.fill.continuity_proposals };
        setFactReview(review); sessionStorage.setItem("harness.next.pending_facts", JSON.stringify(review)); sessionStorage.removeItem("harness.next.draft");
      } else if (["committed", "rejected"].includes(record.lifecycle_state)) {
        sessionStorage.removeItem("harness.next.draft");
      } else {
        const nextHash = await fingerprint(record.draft);
        if (!live) return;
        setDraft(record); setDraftHash(nextHash); sessionStorage.setItem("harness.next.draft", draftLocator(record));
      }
    }).catch((reason) => { if (live) setError(errorText(reason)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  if (loading) return <div className="loading">Restoring draft…</div>;
  if (error) return <Failure message={error} retry={() => { setError(""); setDraft(null); sessionStorage.removeItem("harness.next.draft"); }} />;
  if (factReview) return <FactReview review={factReview} notify={notify} onReview={(next) => { if (next.proposals.length) { setFactReview(next); sessionStorage.setItem("harness.next.pending_facts", JSON.stringify(next)); } else { setFactReview(null); sessionStorage.removeItem("harness.next.pending_facts"); onCommitted(); } }} />;
  if (!draft) return <DraftGenerator onGenerated={async (record) => { setDraft(record); setDraftHash(await fingerprint(record.draft)); sessionStorage.setItem("harness.next.draft", draftLocator(record)); notify("Typed draft generated"); }} />;
  const close = () => { setDraft(null); setDraftHash(""); sessionStorage.removeItem("harness.next.draft"); };
  return <DraftEditor record={draft} draftHash={draftHash} onRecord={async (record) => { setDraft(record); setDraftHash(await fingerprint(record.draft)); sessionStorage.setItem("harness.next.draft", draftLocator(record)); }} onClose={close} notify={notify} onCommitted={(proposals) => { const review = { draftId: draft.draft.draft_id, revision: draft.draft.revision, proposals }; close(); if (proposals.length) { setFactReview(review); sessionStorage.setItem("harness.next.pending_facts", JSON.stringify(review)); } else onCommitted(); }} />;
}

function FactReview({ review, notify, onReview }: { review: { draftId: string; revision: number; proposals: ContinuityProposal[] }; notify: (message: string, tone?: Notice["tone"]) => void; onReview: (review: { draftId: string; revision: number; proposals: ContinuityProposal[] }) => void }) {
  const [busy, setBusy] = useState(""); const [error, setError] = useState("");
  const decide = async (proposal: ContinuityProposal, action: "accept" | "reject") => { setBusy(proposal.key); setError(""); try { await api.decideDraftFact(review.draftId, review.revision, proposal.key, action); notify(`${action === "accept" ? "Accepted" : "Rejected"} continuity fact ${proposal.key}`); onReview({ ...review, proposals: review.proposals.filter((item) => item.key !== proposal.key) }); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } };
  return <><WorkspaceHeader title="Review proposed facts" description={`Committed draft ${review.draftId} · revision ${review.revision}. Proposals never enter canon without your separate decision.`} />{error && <Failure message={error} />}<section className="panel"><PanelTitle title="Continuity proposals" meta={review.proposals.length} /><div className="plan-stack">{review.proposals.map((proposal) => <article className="plan-card" key={proposal.key}><h4>{proposal.key}</h4><p>{proposal.value}</p><small>Evidence: {proposal.evidence_slot_ids.join(", ") || "not cited"}</small><div className="actions"><button disabled={!!busy} onClick={() => void decide(proposal, "reject")}>Reject</button><button className="primary" disabled={!!busy} onClick={() => void decide(proposal, "accept")}>{busy === proposal.key ? "Saving…" : "Accept into continuity lore"}</button></div></article>)}</div></section></>;
}

function DraftGenerator({ onGenerated }: { onGenerated: (record: DraftRecord) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [planRecord, setPlanRecord] = useState<PassagePlanRecord | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [pending, setPending] = useState({ passage_id: "new_scene", arc_name: "main", plan_id: "new_scene_plan", passage_mode: "normal", author_task: "", strategy: "typed_fill" });
  const [mechanics, setMechanics] = useState<PlanMechanicsState>(() => initialPlanMechanics());
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    const nextPending = { passage_id: String(data.get("passage_id")), arc_name: String(data.get("arc_name")), plan_id: planRecord?.plan.plan_id || String(data.get("plan_id")), passage_mode: String(data.get("passage_mode")), author_task: String(data.get("author_task")), strategy: String(data.get("strategy")) };
    try {
      const plan = planFromForm(form, mechanics, planRecord ? planRecord.plan.revision + 1 : 1, planRecord?.plan.plan_id || "");
      const stored = planRecord ? await api.revisePassagePlan(planRecord, plan, nextPending.arc_name) : await api.createPassagePlan(plan, nextPending.arc_name);
      setPlanRecord(stored); setPending(nextPending); setReviewing(true);
    }
    catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  };
  const approveAndGenerate = async () => {
    if (!planRecord) return; setBusy(true); setError("");
    try {
      const approved = await api.approvePassagePlan(planRecord); setPlanRecord(approved);
      await onGenerated(await api.generateDraft({ plan_id: approved.plan.plan_id, plan_revision: approved.plan.revision, expected_plan_fingerprint: approved.fingerprint, context: { premise: "", parent_passage_id: "", parent_prose: "", parent_summary: "", story_recall: "", world_facts: [], entity_facts: [], open_threads: [], inspiration: "" }, author_task: pending.author_task, passage_id: pending.passage_id, arc_name: pending.arc_name, parent_passage_id: "", branch_name: "main", strategy: pending.strategy }));
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  };
  if (reviewing && planRecord) return <><WorkspaceHeader title="Review passage plan" description="The trusted structure is an immutable revision. The model will receive only the bounded copy slots you approve." />{error && <Failure message={error} />}<section className="panel"><PanelTitle title={planRecord.plan.plan_id} meta={`revision ${planRecord.plan.revision}`} /><dl className="facts"><dt>Passage</dt><dd>{pending.passage_id}</dd><dt>Mode</dt><dd>{planRecord.plan.passage_mode}</dd><dt>Narrative slots</dt><dd>{planRecord.plan.narrative_slots.length}</dd><dt>Choice slots</dt><dd>{planRecord.plan.choice_slots.length}</dd><dt>State references</dt><dd>{planRecord.plan.allowed_state_refs.join(", ") || "none"}</dd><dt>Fixed effects</dt><dd>{planRecord.plan.fixed_effects.length}</dd><dt>Proposal slots</dt><dd>{planRecord.plan.mechanic_slots.length}</dd><dt>Form fields</dt><dd>{planRecord.plan.form_fields.length}</dd><dt>Room exits</dt><dd>{planRecord.plan.exits.length}</dd><dt>Loop binding</dt><dd>{planRecord.plan.loop_binding ? `${planRecord.plan.loop_binding.variable} in ${planRecord.plan.loop_binding.collection}` : "none"}</dd></dl><h4>Trusted destinations</h4><ul>{planRecord.plan.choice_slots.map((choice) => <li key={choice.id}>{choice.id} → {choice.destination} · weight {choice.weight} · {choice.conditions.length} guards · {choice.effects.length} effects{choice.restart ? " · restart" : ""}</li>)}</ul><h4>Author direction</h4><p>{pending.author_task}</p><div className="actions"><button disabled={busy} onClick={() => setReviewing(false)}>Revise plan</button><button className="primary" disabled={busy} onClick={() => void approveAndGenerate()}>{busy ? "Approving and generating…" : "Approve plan and generate"}</button></div></section></>;
  return <><WorkspaceHeader title="Write" description="Create a harness-owned plan, then let the model fill only bounded copy slots." />{error && <Failure message={error} />}
    <form className="panel form-grid" onSubmit={(event) => void submit(event)}>
      <label>Passage ID<input name="passage_id" required pattern={"[A-Za-z0-9][A-Za-z0-9_\\x2d]{0,79}"} defaultValue={pending.passage_id} /></label>
      <label>Arc name<input name="arc_name" required defaultValue={pending.arc_name} /></label>
      <label>Plan ID<input name="plan_id" required disabled={Boolean(planRecord)} pattern="[a-z][a-z0-9_]{0,63}" defaultValue={pending.plan_id} /></label>
      <label>Passage structure<select name="passage_mode" value={pending.passage_mode} onChange={(event) => setPending((current) => ({ ...current, passage_mode: event.target.value }))}>{["normal", "conditional", "event", "random_event", "dialogue", "dialogue_loop", "ending", "form", "hub", "loop", "random", "room", "widget", "include"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <PlanMechanicsEditor mode={pending.passage_mode} value={mechanics} onChange={setMechanics} />
      <label className="wide">Author direction<textarea name="author_task" required rows={6} defaultValue={pending.author_task} placeholder="Describe the scene, tone, and immediate decision." /></label>
      <label>Strategy<select name="strategy" defaultValue={pending.strategy}><option value="typed_fill">Typed fill</option><option value="flat_fill">Flat fill</option></select></label>
      <button className="primary" disabled={busy} type="submit">{busy ? "Saving plan…" : planRecord ? "Save revised plan for review" : "Save plan for review"}</button>
    </form></>;
}

function DraftEditor({ record, draftHash, onRecord, onClose, onCommitted, notify }: { record: DraftRecord; draftHash: string; onRecord: (record: DraftRecord) => void | Promise<void>; onClose: () => void; onCommitted: (proposals: ContinuityProposal[]) => void; notify: (message: string, tone?: Notice["tone"]) => void }) {
  const draftTabs = ["copy", "choices", "mechanics", "preview"] as const;
  const [tab, setTab] = useState("copy");
  const [fill, setFill] = useState(() => structuredClone(record.draft.fill));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [artifact, setArtifact] = useState(record.compile_artifact);
  const [playtestJob, setPlaytestJob] = useState<DraftPlaytestJob | null>(null);
  const [stateFixture, setStateFixture] = useState<Record<string, string>>({});
  const [previewWidth, setPreviewWidth] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [artifactMatches, setArtifactMatches] = useState<boolean | null>(record.compile_artifact ? true : null);
  const [commitBlocked, setCommitBlocked] = useState(false);
  const editorLive = useRef(true);
  useEffect(() => () => { editorLive.current = false; }, []);
  useEffect(() => { setFill(structuredClone(record.draft.fill)); setArtifact(record.compile_artifact); setArtifactMatches(record.compile_artifact ? true : null); setPlaytestJob(null); setStateFixture({}); setPreviewWidth("desktop"); setCommitBlocked(false); }, [record]);
  const dirty = JSON.stringify(canonical(fill)) !== JSON.stringify(canonical(record.draft.fill));
  useEffect(() => { document.body.dataset.dirty = dirty ? "true" : "false"; return () => { delete document.body.dataset.dirty; }; }, [dirty]);
  useEffect(() => { const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); }; addEventListener("beforeunload", beforeUnload); return () => removeEventListener("beforeunload", beforeUnload); }, [dirty]);
  const narrative = fill.narrative;
  const choices = fill.choices;
  const mutateNarrative = (index: number, value: string) => setFill((current) => ({ ...current, narrative: current.narrative.map((slot, slotIndex) => slotIndex === index ? { ...slot, parts: parseEditableParts(value) } : slot) }));
  const mutateChoice = (index: number, value: string) => setFill((current) => ({ ...current, choices: current.choices.map((slot, slotIndex) => slotIndex === index ? { ...slot, text: value } : slot) }));
  const focusDiagnostic = (item: Diagnostic) => {
    const path = item.path || [];
    const group = path.includes("choices") ? "choices" : "narrative";
    const groupIndex = path.indexOf(group);
    const index = Number(path[groupIndex + 1] ?? 0);
    const slot = String((group === "choices" ? choices[index] : narrative[index])?.slot_id || "");
    setTab(group === "choices" ? "choices" : "copy");
    requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-diagnostic-slot="${CSS.escape(slot)}"] input, [data-diagnostic-slot="${CSS.escape(slot)}"] textarea`)?.focus());
  };
  const moveDraftTab = (event: ReactKeyboardEvent<HTMLButtonElement>, current: number) => {
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const target = event.key === "Home" ? 0 : event.key === "End" ? draftTabs.length - 1 : delta ? (current + delta + draftTabs.length) % draftTabs.length : -1;
    if (target < 0) return;
    event.preventDefault();
    setTab(draftTabs[target]);
    requestAnimationFrame(() => document.getElementById(`draft-tab-${draftTabs[target]}`)?.focus());
  };
  const action = async (name: "save" | "validate" | "compile" | "playtest" | "commit" | "reject", choiceSlotId?: string) => {
    setBusy(name); setError("");
    try {
      if (name === "save") { const next = await api.editDraft({ ...record, draft: { ...record.draft, fill } }, draftHash); await onRecord(next); notify("Saved as a new immutable revision"); }
      else if (name === "validate") { const next = await api.validateDraft(record, draftHash); await onRecord(next); notify("Draft validated"); }
      else if (name === "compile") { const result = await api.compileDraft(record, draftHash); setArtifact(result.artifact); setArtifactMatches(result.persisted_artifact_match); notify(result.persisted_artifact_match ? "Exact draft compilation reproduced" : "Compiler output differs from the persisted preview", result.persisted_artifact_match ? "ok" : "error"); }
      else if (name === "playtest") {
        const initialState = Object.fromEntries(Object.entries(stateFixture).filter(([, value]) => value.trim()).map(([key, value]) => {
          try { return [key, JSON.parse(value)]; } catch { return [key, value]; }
        }));
        let job = await api.startDraftPlaytest(record, draftHash, initialState, choiceSlotId ? [choiceSlotId] : undefined);
        if (!editorLive.current) return;
        setPlaytestJob(job);
        for (let attempt = 0; attempt < 240 && ["queued", "running"].includes(job.status); attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          if (!editorLive.current) return;
          job = await api.draftPlaytest(job.job_id); setPlaytestJob(job);
        }
        if (!editorLive.current) return;
        if (["queued", "running"].includes(job.status)) throw new Error("Playtest did not finish within two minutes.");
        if (job.status === "failed") throw new Error(`${job.error_code}: ${job.error_message}`);
        const target = choiceSlotId ? `Choice ${choiceSlotId}` : "Isolated playtest";
        notify(job.result?.passed ? `${target} passed` : `${target} found failures`, job.result?.passed ? "ok" : "error");
      }
      else if (name === "commit") { const result = await api.commitDraft(record, draftHash); notify(`Committed ${result.passage_id}`); onCommitted(result.pending_facts || []); }
      else if (confirm("Reject this immutable draft revision?")) { await api.rejectDraft(record, draftHash); notify("Draft rejected"); onClose(); }
    } catch (reason) {
      if (!editorLive.current) return;
      setError(errorText(reason));
      if (reason instanceof ApiFailure && ["draft_superseded", "draft_fingerprint_conflict"].includes(reason.code)) {
        const latest = await api.latestDraft(record.draft.draft_id);
        await onRecord(latest);
        notify("Loaded the latest persisted draft revision", "error");
      } else if (reason instanceof ApiFailure && ["parent_fingerprint_conflict", "parent_expectation_conflict", "parent_missing", "plan_revision_conflict"].includes(reason.code)) {
        setCommitBlocked(true);
        notify("The trusted parent or plan changed. Regenerate or explicitly revise the plan before committing.", "error");
      }
    } finally { if (editorLive.current) setBusy(""); }
  };
  const plan = record.draft.plan;
  const compileFailed = artifactMatches === false || (artifact?.diagnostics || []).some((item) => item.level === "error");
  const playtestState = !playtestJob ? "not run" : ["queued", "running"].includes(playtestJob.status) ? "running" : playtestJob.status === "completed" && playtestJob.result?.passed ? "passed" : "failed";
  const reviewStages = [
    ["Plan", "passed"],
    ["Narrative", record.diagnostics.some((item) => item.stage === "narrative" && item.level === "error") ? "failed" : "passed"],
    ["Mechanics", record.diagnostics.some((item) => item.stage === "mechanics" && item.level === "error") ? "failed" : "passed"],
    ["Compile", !artifact ? "not run" : compileFailed ? "failed" : "passed"],
    ["Playtest", playtestState],
  ] as const;
  return <><WorkspaceHeader title="Write" description={`Draft ${record.draft.draft_id} · revision ${record.draft.revision}`} action={<span className="lifecycle">{record.lifecycle_state}</span>} />{error && <Failure message={error} />}
    <p className="sr-only" role="status" aria-live="polite">{busy ? `${busy} in progress` : `${record.lifecycle_state} draft ready`}</p>
    <div className="write-layout"><section className="panel tabs-panel"><div className="tabs" role="tablist" aria-label="Draft editor">{draftTabs.map((item, index) => <button id={`draft-tab-${item}`} key={item} role="tab" aria-selected={tab === item} aria-controls={`draft-panel-${item}`} tabIndex={tab === item ? 0 : -1} onKeyDown={(event) => moveDraftTab(event, index)} onClick={() => setTab(item)}>{item === "copy" ? "Write" : item[0].toUpperCase() + item.slice(1)}</button>)}</div>
      {tab === "copy" && <div className="tab-body" role="tabpanel" id="draft-panel-copy" aria-labelledby="draft-tab-copy">{narrative.map((slot, index) => <label data-diagnostic-slot={String(slot.slot_id)} key={String(slot.slot_id)}>{String(slot.slot_id || `Narrative ${index + 1}`)}<textarea rows={9} value={editableParts(slot.parts || [])} onChange={(event) => mutateNarrative(index, event.target.value)} /></label>)}</div>}
      {tab === "choices" && <div className="tab-body" role="tabpanel" id="draft-panel-choices" aria-labelledby="draft-tab-choices">{choices.map((choice, index) => <label data-diagnostic-slot={String(choice.slot_id)} key={String(choice.slot_id)}>{String(choice.slot_id)}<input value={String(choice.text)} onChange={(event) => mutateChoice(index, event.target.value)} /><small>{String(choice.hint || "No hint")}</small></label>)}</div>}
      {tab === "mechanics" && <div className="tab-body" role="tabpanel" id="draft-panel-mechanics" aria-labelledby="draft-tab-mechanics"><dl className="facts"><dt>Mode</dt><dd>{plan.passage_mode}</dd><dt>Choice authority</dt><dd>{plan.choice_slots.length} fixed slots</dd><dt>State reads</dt><dd>{plan.allowed_state_refs.join(", ") || "none"}</dd><dt>State writes</dt><dd>{plan.fixed_effects.map((effect) => `${effect.operation} ${effect.target}`).join(", ") || "none"}</dd><dt>Eligibility rules</dt><dd>{plan.eligibility.length}</dd><dt>Required components</dt><dd>{plan.required_components.join(", ") || "none"}</dd><dt>Mechanic proposal slots</dt><dd>{plan.mechanic_slots.map((slot) => slot.id).join(", ") || "none"}</dd><dt>Form fields</dt><dd>{plan.form_fields.map((field) => `${field.label || field.id} (${field.kind})`).join(", ") || "none"}</dd><dt>Room exits</dt><dd>{plan.exits.map((exit) => `${exit.label} → ${exit.destination}`).join(", ") || "none"}</dd><dt>Loop binding</dt><dd>{plan.loop_binding ? `${plan.loop_binding.variable} in ${plan.loop_binding.collection}` : "none"}</dd><dt>Reentry</dt><dd>{plan.repeatable ? `repeatable · ${plan.reentry_policy}` : plan.reentry_policy}</dd></dl></div>}
      {tab === "preview" && <div className="tab-body preview" role="tabpanel" id="draft-panel-preview" aria-labelledby="draft-tab-preview"><div className="preview-toolbar" role="group" aria-label="Preview width">{(["desktop", "tablet", "mobile"] as const).map((width) => <button key={width} type="button" aria-pressed={previewWidth === width} onClick={() => setPreviewWidth(width)}>{width[0].toUpperCase() + width.slice(1)}</button>)}</div><div className={`preview-device ${previewWidth}`} data-preview-width={previewWidth}>{narrative.map((slot, index) => <p key={index}>{editableParts(slot.parts || []).replace(/\{\{(?:state|entity)_ref:([^}]+)\}\}/g, "[$1]")}</p>)}<ul className="preview-choices">{choices.map((choice, index) => <li key={index}><span>{String(choice.text)}</span><button type="button" disabled={!!busy || dirty || !artifact || artifactMatches === false} onClick={() => void action("playtest", String(choice.slot_id))}>Test choice {String(choice.text)}</button></li>)}</ul></div>{plan.allowed_state_refs.length > 0 && <fieldset><legend>Isolated playtest state fixture</legend>{plan.allowed_state_refs.map((reference) => <label key={reference}>{reference}<input value={stateFixture[reference] || ""} placeholder="JSON value" onChange={(event) => setStateFixture((current) => ({ ...current, [reference]: event.target.value }))} /></label>)}<small>Blank values are omitted. JSON primitives are parsed; other text is used as a string.</small></fieldset>}{artifact && <details><summary>Advanced: compiled Twee and source mapping</summary><p>Compiler {artifact.compiler_version} · draft {artifact.source_draft_fingerprint.slice(0, 12)}…</p><pre>{artifact.twee_source}</pre><p>{artifact.source_map.length} source-map entries · {artifact.link_targets.length} trusted link targets</p></details>}</div>}
      <div className="actions"><button disabled={!!busy} onClick={() => void action("reject")}>Reject draft</button><button onClick={onClose}>Close draft</button><button disabled={!!busy || !dirty} onClick={() => void action("save")}>{busy === "save" ? "Saving…" : "Save revision"}</button><button disabled={!!busy || dirty} title={dirty ? "Save the visible edits before validation" : undefined} onClick={() => void action("validate")}>{busy === "validate" ? "Validating…" : "Validate"}</button><button disabled={!!busy || dirty} onClick={() => void action("compile")}>{busy === "compile" ? "Compiling…" : "Compile exact revision"}</button><button disabled={!!busy || dirty || !artifact || artifactMatches === false} onClick={() => void action("playtest")}>{busy === "playtest" ? "Playtesting…" : "Run isolated playtest"}</button><button className="primary" disabled={!!busy || dirty || record.lifecycle_state !== "validated" || artifactMatches === false || commitBlocked} title={commitBlocked ? "Reload or regenerate after the trusted parent or plan changed" : undefined} onClick={() => void action("commit")}>{busy === "commit" ? "Committing…" : "Commit exact revision"}</button></div>
    </section><aside className="panel inspector"><PanelTitle title="Review" meta={`${record.diagnostics?.length || 0} diagnostics`} /><ol className="review-stages" aria-label="Draft review stages">{reviewStages.map(([stage, state]) => <li key={stage}><strong>{stage}</strong><span className={`stage-state ${state.replace(" ", "-")}`}>{state}</span></li>)}</ol>{playtestJob?.result && <div className={playtestJob.result.passed ? "callout" : "error-card"}><strong>Isolated playtest {playtestJob.result.passed ? "passed" : "failed"}</strong><p>Compile: {String(playtestJob.result.tweego_compile)} · browser load: {String(playtestJob.result.browser_load)} · choice reachability: {String(playtestJob.result.choice_reachability ?? "not assessed")}</p></div>}{record.diagnostics?.length ? <DiagnosticList items={record.diagnostics} onSelect={focusDiagnostic} /> : <Empty>No compiler diagnostics for this revision.</Empty>}</aside></div></>;
}

function DiagnosticList({ items, onSelect }: { items: Diagnostic[]; onSelect?: (item: Diagnostic) => void }) {
  return <ul className="diagnostics">{items.map((item, index) => <li key={`${item.code}-${index}`}><span className={`severity ${item.level || "warning"}`}>{item.level || "warning"}</span>{onSelect ? <button className="diagnostic-button" onClick={() => onSelect(item)}><strong>{item.code || "diagnostic"}</strong><span>{item.message || "No message"}</span></button> : <div><strong>{item.code || "diagnostic"}</strong><p>{item.message || "No message"}</p></div>}</li>)}</ul>;
}

function WorldWorkspace({ notify }: { notify: (message: string, tone?: Notice["tone"]) => void }) {
  const state = useLoad(async () => { const [characters, lore] = await Promise.all([api.characters(), api.lore()]); return { characters, lore }; });
  const [sheet, setSheet] = useState<WorldSheet | null>(null);
  const [content, setContent] = useState("");
  const [kind, setKind] = useState<"character" | "lore">("character");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const dirty = !!sheet && content !== sheet.content;
  useEffect(() => { document.body.dataset.dirty = dirty ? "true" : "false"; return () => { delete document.body.dataset.dirty; }; }, [dirty]);
  useEffect(() => { const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); }; addEventListener("beforeunload", beforeUnload); return () => removeEventListener("beforeunload", beforeUnload); }, [dirty]);
  if (state.error) return <Failure message={state.error} retry={state.reload} />;
  if (!state.value) return <div className="loading">Loading world…</div>;
  const inspectCharacter = async (id: string) => { if (dirty && !confirm("Discard unsaved world edits?")) return; setError(""); try { const next = await api.character(id); setKind("character"); setSheet(next); setContent(next.content); } catch (reason) { setError(errorText(reason)); } };
  const inspectLore = async (category: string, id: string) => { if (dirty && !confirm("Discard unsaved world edits?")) return; setError(""); try { const next = await api.loreEntry(category, id); setKind("lore"); setSheet(next); setContent(next.content); } catch (reason) { setError(errorText(reason)); } };
  const save = async () => { if (!sheet) return; setBusy("save"); setError(""); try { const saved = kind === "character" ? await api.saveCharacter(sheet.id, content, sheet.content_fingerprint) : await api.saveLore(String(sheet.category), sheet.id, content, sheet.content_fingerprint); setSheet({ ...sheet, content, content_fingerprint: saved.content_fingerprint }); notify(`${kind === "character" ? "Character" : "Lore"} saved`); state.reload(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } };
  const createCharacter = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setBusy("character"); setError(""); const form = event.currentTarget; const data = new FormData(form); try { const made = await api.createCharacter({ id: data.get("id"), name: data.get("name"), description: data.get("description"), tags: [] }); form.reset(); state.reload(); await inspectCharacter(made.id); notify("Character created"); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } };
  const createLore = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setBusy("lore"); setError(""); const form = event.currentTarget; const data = new FormData(form); try { const made = await api.createLore({ category: data.get("category"), id: data.get("id"), title: data.get("title"), description: data.get("description") }); form.reset(); state.reload(); await inspectLore(made.category, made.id); notify("Lore created"); } catch (reason) { setError(errorText(reason)); } finally { setBusy(""); } };
  return <><WorkspaceHeader title="World" description="Edit canonical character and lore sheets with stale-write protection. Runtime simulation state remains separate." />{error && <Failure message={error} />}<div className="world-layout"><section className="panel"><PanelTitle title="Characters" meta={state.value.characters.length} /><ul className="entity-list selectable-list">{state.value.characters.length ? state.value.characters.map((item, index) => <li key={String(item.id || index)}><button onClick={() => void inspectCharacter(String(item.id))}><strong>{String(item.name || item.id)}</strong><span>{String(item.summary || "")}</span></button></li>) : <li>None yet</li>}</ul><form className="compact-form" onSubmit={(event) => void createCharacter(event)}><h4>New character</h4><label>ID<input name="id" required /></label><label>Name<input name="name" required /></label><label className="wide">Description<textarea name="description" rows={3} /></label><button className="primary" disabled={!!busy}>{busy === "character" ? "Creating…" : "Create character"}</button></form></section>
    <section className="panel"><PanelTitle title="Lore" meta={state.value.lore.length} /><ul className="entity-list selectable-list">{state.value.lore.length ? state.value.lore.map((item, index) => <li key={`${String(item.category)}:${String(item.id || index)}`}><button onClick={() => void inspectLore(String(item.category), String(item.id))}><strong>{String(item.title || item.id)}</strong><span>{String(item.category || "")}</span></button></li>) : <li>None yet</li>}</ul><form className="compact-form" onSubmit={(event) => void createLore(event)}><h4>New lore</h4><label>Category<input name="category" required /></label><label>ID<input name="id" required /></label><label>Title<input name="title" required /></label><label>Description<textarea name="description" rows={3} /></label><button className="primary" disabled={!!busy}>{busy === "lore" ? "Creating…" : "Create lore"}</button></form></section>
    <section className="panel world-editor"><PanelTitle title={sheet ? `${kind}: ${sheet.id}` : "Canonical sheet"} meta={dirty ? "unsaved" : sheet ? "saved" : "select an entity"} />{sheet ? <><label>Markdown<textarea rows={24} value={content} onChange={(event) => setContent(event.target.value)} /></label><div className="actions"><button disabled={!dirty || !!busy} onClick={() => setContent(sheet.content)}>Revert</button><button className="primary" disabled={!dirty || !!busy} onClick={() => void save()}>{busy === "save" ? "Saving…" : "Save with fingerprint"}</button></div></> : <Empty>Select or create a character or lore entry.</Empty>}</section></div></>;
}

function MediaWorkspace({ notify }: { notify: (message: string, tone?: Notice["tone"]) => void }) {
  const state = useLoad(async () => { const [slots, files] = await Promise.all([api.mediaSlots(), api.mediaFiles()]); return { slots, files }; });
  const [selected, setSelected] = useState<MediaSlot | null>(null);
  const [draft, setDraft] = useState<MediaSlot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (state.error) return <Failure message={state.error} retry={state.reload} />;
  if (!state.value) return <div className="loading">Loading media…</div>;
  const choose = (slot: MediaSlot) => { setSelected(slot); setDraft(structuredClone(slot)); setError(""); };
  const refreshSelected = async (id: string) => { const slots = await api.mediaSlots(); const next = slots.find((item) => item.id === id) || null; setSelected(next); setDraft(next ? structuredClone(next) : null); state.reload(); };
  const saveMeta = async () => { if (!selected || !draft || !selected.id) return; setBusy(true); setError(""); try { await api.updateMediaSlot(selected.id, { expected_slot_fingerprint: selected.fingerprint, description: draft.description || "", alt: draft.alt || "", caption: draft.caption || "", type: draft.type || "image", keywords: draft.keywords || [] }); await refreshSelected(selected.id); notify("Media metadata saved"); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } };
  const resolvePath = async (path: string) => { if (!selected?.id || !selected.fingerprint) return; setBusy(true); setError(""); try { if (path) await api.resolveMediaSlot(selected.id, path, String(selected.fingerprint)); else await api.unresolveMediaSlot(selected.id, String(selected.fingerprint)); await refreshSelected(selected.id); notify(path ? "Media slot resolved" : "Media slot unresolved"); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } };
  const importFile = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setBusy(true); setError(""); const form = event.currentTarget; const data = new FormData(form); try { const result = await api.importMedia(String(data.get("src_path") || ""), String(data.get("dest_name") || "")); form.reset(); state.reload(); notify(`Imported ${result.rel_path}`); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } };
  const preview = selected?.id && selected.status === "resolved" ? api.mediaPreviewUrl(selected.id) : "";
  return <><WorkspaceHeader title="Media" description="Resolve assets and edit accessible media metadata with stale-write protection." />{error && <Failure message={error} />}<div className="two-column"><section className="panel"><PanelTitle title="Media slots" meta={state.value.slots.length} />{state.value.slots.length ? <ul className="entity-list selectable-list">{state.value.slots.map((slot, index) => <li key={slot.id || slot.slot_id || index}><button onClick={() => choose(slot)}><strong>{slot.id || slot.slot_id}</strong><span>{slot.status || "pending"}</span></button></li>)}</ul> : <Empty>No media slots have been declared. Add one from passage metadata.</Empty>}<form className="compact-form" onSubmit={(event) => void importFile(event)}><h4>Import project media</h4><label className="wide">Source path<input name="src_path" required /></label><label>Library name<input name="dest_name" placeholder="Keep original name" /></label><button className="primary" disabled={busy}>{busy ? "Importing…" : "Import file"}</button></form></section><section className="panel"><PanelTitle title={selected?.id || selected?.slot_id || "Media inspector"} meta={selected?.status || "select a slot"} />{draft && selected ? <div className="form-grid media-form"><label>Type<select value={String(draft.type || "image")} onChange={(event) => setDraft({ ...draft, type: event.target.value })}>{["image", "audio", "video"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Resolved asset<select value={String(draft.resolved_path || "")} disabled={busy} onChange={(event) => void resolvePath(event.target.value)}><option value="">Unresolved</option>{state.value.files.map((file) => <option key={file.rel_path} value={file.rel_path}>{file.name} · {file.type}</option>)}</select></label>{preview && <div className="wide media-preview">{draft.type === "audio" ? <audio controls src={preview} /> : draft.type === "video" ? <video controls src={preview} /> : <img src={preview} alt={String(draft.alt || draft.description || "Selected media preview")} />}</div>}<label className="wide">Description<textarea rows={3} value={String(draft.description || "")} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label><label className="wide">Alt text<input value={String(draft.alt || "")} onChange={(event) => setDraft({ ...draft, alt: event.target.value })} /></label><label className="wide">Caption<input value={String(draft.caption || "")} onChange={(event) => setDraft({ ...draft, caption: event.target.value })} /></label><div className="actions wide"><button className="primary" disabled={busy} onClick={() => void saveMeta()}>{busy ? "Saving…" : "Save metadata"}</button></div></div> : <Empty>Select a media slot to edit metadata or resolution.</Empty>}</section></div></>;
}

function TestsWorkspace() {
  const state = useLoad(async () => { const [validation, runs] = await Promise.all([api.validation(), api.benchmarkRuns()]); return { validation, runs }; });
  const [detail, setDetail] = useState<BenchmarkRunDetail | null>(null);
  const [detailError, setDetailError] = useState("");
  if (state.error) return <Failure message={state.error} retry={state.reload} />;
  if (!state.value) return <div className="loading">Loading test evidence…</div>;
  const errors = state.value.validation.errors || [], warnings = state.value.validation.warnings || [];
  const inspect = async (run: BenchmarkRunSummary) => { setDetailError(""); try { setDetail(await api.benchmarkRun(run.id)); } catch (error) { setDetailError(errorText(error)); } };
  return <><WorkspaceHeader title="Tests" description="Story health and immutable model-benchmark evidence remain separate, inspectable test types." action={<button onClick={state.reload}>Run again</button>} />
    <div className="metric-row"><div><strong>{errors.length}</strong><span>Errors</span></div><div><strong>{warnings.length}</strong><span>Warnings</span></div><div><strong>{state.value.validation.valid === false ? "Blocked" : "Ready"}</strong><span>Commit posture</span></div></div>
    <div className="two-column"><section className="panel"><PanelTitle title="Story diagnostics" meta={errors.length + warnings.length} />{errors.length + warnings.length ? <DiagnosticList items={[...errors, ...warnings]} /> : <Empty>No validation diagnostics.</Empty>}</section>
      <section className="panel"><PanelTitle title={detail ? String(detail.manifest.benchmark_name || detail.id) : "Model benchmark"} meta={detail ? `${detail.pagination.total} requests` : `${state.value.runs.length} runs`} />{detailError ? <Failure message={detailError} /> : detail ? <><pre className="benchmark-summary">{detail.summary || "No summary artifact."}</pre><details><summary>Provenance manifest</summary><pre>{JSON.stringify(detail.manifest, null, 2)}</pre></details><button onClick={() => setDetail(null)}>Back to runs</button></> : <ul className="entity-list">{state.value.runs.length ? state.value.runs.map((run) => <li key={run.id}><button className="benchmark-run" onClick={() => void inspect(run)}><strong>{run.benchmark_name || run.run_id}</strong><span>{run.result_count} original requests</span></button></li>) : <li>No persisted runs in the configured benchmark directory.</li>}</ul>}</section></div></>;
}

function SettingsWorkspace({ config, onConfig, notify }: { config: HarnessConfig; onConfig: (config: HarnessConfig) => void; notify: (message: string, tone?: Notice["tone"]) => void }) {
  const profileState = useLoad(() => api.experienceProfile());
  const capabilityState = useLoad(() => api.capabilityCards());
  const [candidate, setCandidate] = useState<ExperienceProfile | null>(null);
  const [presets, setPresets] = useState<ExperienceProfileState["presets"] | null>(null);
  const [preview, setPreview] = useState<ExperienceMigrationPreview | null>(null);
  const [error, setError] = useState("");
  const [overridesText, setOverridesText] = useState("[]");
  const [overridesError, setOverridesError] = useState("");
  const [busy, setBusy] = useState(false);
  const [modelBusy, setModelBusy] = useState("");
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const storedRevision = profileState.value?.profile.revision ?? 0;
  useEffect(() => {
    if (!profileState.value) return;
    const next = { ...profileState.value.profile, revision: profileState.value.profile.revision + 1 };
    setCandidate(next);
    setPresets(profileState.value.presets);
    setOverridesText(JSON.stringify(next.overrides, null, 2));
    setOverridesError("");
    setPreview(null);
  }, [profileState.value]);

  const change = <K extends keyof ExperienceProfile,>(key: K, value: ExperienceProfile[K]) => {
    setCandidate((current) => current ? { ...current, [key]: value } : current);
    setPreview(null);
  };
  const selectPreset = (mode: ExperienceProfile["mode"]) => {
    if (!presets) return;
    const next = { ...presets[mode], revision: storedRevision + 1, overrides: candidate?.overrides || [] };
    setCandidate(next);
    setOverridesText(JSON.stringify(next.overrides, null, 2));
    setOverridesError("");
    setPreview(null);
  };
  const parseOverrides = () => {
    const parsed = JSON.parse(overridesText) as ExperienceProfile["overrides"];
    if (!Array.isArray(parsed)) throw new Error("Overrides must be a JSON array.");
    if (parsed.some((override) => !override || !["arc", "region", "scenario"].includes(override.scope_kind) || !override.scope_id)) {
      throw new Error("Each override needs a valid scope_kind and non-empty scope_id.");
    }
    return parsed;
  };
  const changeOverrides = (text: string) => {
    setOverridesText(text);
    setPreview(null);
    try { JSON.parse(text); setOverridesError(""); }
    catch { setOverridesError("Overrides are not valid JSON."); }
  };
  const requestPreview = async () => {
    if (!candidate) return;
    setBusy(true); setError("");
    try {
      const profile = { ...candidate, overrides: parseOverrides() };
      setCandidate(profile);
      setOverridesError("");
      setPreview(await api.previewExperienceProfile(storedRevision, profile));
    } catch (reason) { setOverridesError(errorText(reason)); setError(errorText(reason)); }
    finally { setBusy(false); }
  };
  const saveProfile = async () => {
    if (!candidate || !preview) return;
    setBusy(true); setError("");
    try {
      const saved = await api.saveExperienceProfile(storedRevision, candidate, preview.preview_fingerprint);
      onConfig({ ...config, experience_mode: saved.profile.mode });
      notify(`Experience profile revision ${saved.profile.revision} saved`);
      profileState.reload();
    } catch (reason) {
      if (reason instanceof ApiFailure && reason.status === 409) {
        setError("The experience profile changed elsewhere. Reloaded the latest revision; review and preview again.");
        profileState.reload();
      } else setError(errorText(reason));
    }
    finally { setBusy(false); }
  };
  const submitSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError("");
    try { const next = await api.updateConfig(Object.fromEntries(new FormData(event.currentTarget))); onConfig(next); notify("Runtime settings saved"); }
    catch (reason) { setError(errorText(reason)); }
  };
  const checkModels = async () => {
    setModelBusy("status"); setError("");
    try { setOllama(await api.ollamaStatus()); }
    catch (reason) { setError(errorText(reason)); }
    finally { setModelBusy(""); }
  };
  const smokeTestModel = async (model: string) => {
    setModelBusy(model); setError("");
    try {
      const score = await api.testModel(model);
      setOllama((current) => current ? { ...current, scores: { ...current.scores, [model]: score } } : current);
      notify(score.ok ? `${model} responded` : `${model}: ${score.error}`, score.ok ? "ok" : "error");
    } catch (reason) { setError(errorText(reason)); }
    finally { setModelBusy(""); }
  };

  if (profileState.error) return <Failure message={profileState.error} retry={profileState.reload} />;
  return <><WorkspaceHeader title="Settings" description="Experience behavior is revisioned separately from reversible runtime and UI choices." />{error && <Failure message={error} />}
    {!candidate ? <div className="loading">Loading experience profile…</div> : <section className="panel form-grid" aria-labelledby="experience-title" aria-busy={busy}>
      <div className="panel-title wide"><h3 id="experience-title">Experience profile</h3><span>current revision {storedRevision}{profileState.value?.source === "compatibility_default" ? " · compatibility default" : ""}</span></div>
      <label>Named mode<select aria-describedby="experience-mode-help" value={candidate.mode} onChange={(event) => selectPreset(event.target.value as ExperienceProfile["mode"])}>{["story_driven", "hybrid", "sandbox"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select><span id="experience-mode-help">Selecting a mode applies its named defaults and retains explicit overrides.</span></label>
      <label>Story guidance<select value={candidate.story_guidance} onChange={(event) => change("story_guidance", event.target.value as ExperienceProfile["story_guidance"])}>{["off", "light", "anchors", "directed"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Narrative pressure <output>{candidate.narrative_pressure.toFixed(1)}</output><input type="range" min="0" max="1" step="0.1" value={candidate.narrative_pressure} onChange={(event) => change("narrative_pressure", Number(event.target.value))} /></label>
      <label>World reactivity <output>{candidate.world_reactivity.toFixed(1)}</output><input type="range" min="0" max="1" step="0.1" value={candidate.world_reactivity} onChange={(event) => change("world_reactivity", Number(event.target.value))} /></label>
      <label>Time model<select value={candidate.time_model} onChange={(event) => change("time_model", event.target.value as ExperienceProfile["time_model"])}>{["none", "turn", "phase", "day", "authored_clock"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Goal model<select value={candidate.goal_model} onChange={(event) => change("goal_model", event.target.value as ExperienceProfile["goal_model"])}>{["authored", "mixed", "player_directed"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Ending policy<select value={candidate.ending_policy} onChange={(event) => change("ending_policy", event.target.value as ExperienceProfile["ending_policy"])}>{["required", "optional", "none"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Character simulation<select value={candidate.character_simulation} onChange={(event) => change("character_simulation", event.target.value as ExperienceProfile["character_simulation"])}>{["none", "relationships", "persistent_stats", "full_agendas"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <fieldset className="wide toggle-grid"><legend>Persistence and structure</legend><label><input type="checkbox" checked={candidate.encounter_reuse} onChange={(event) => change("encounter_reuse", event.target.checked)} /> Encounter reuse</label><label><input type="checkbox" checked={candidate.failure_persistence} onChange={(event) => change("failure_persistence", event.target.checked)} /> Failure persistence</label><label><input type="checkbox" checked={candidate.main_plot_required} onChange={(event) => change("main_plot_required", event.target.checked)} /> Main plot required</label></fieldset>
      <label className="wide">Scoped overrides (JSON)<textarea rows={7} value={overridesText} aria-invalid={Boolean(overridesError)} aria-describedby="experience-overrides-help" onChange={(event) => changeOverrides(event.target.value)} spellCheck={false} /><span id="experience-overrides-help">{overridesError || "Each item names an arc, region, or scenario and only the fields it overrides."}</span></label>
      <div className="wide callout">A migration preview never rewrites graph topology or passage files. Any edit after preview requires a new preview.</div>
      {preview && <div className="wide" role="status" aria-live="polite"><h4>Migration preview · target revision {preview.expected_revision}</h4><ul className="diagnostics">{preview.impacts.map((impact) => <li key={impact.code}><span className={`severity ${impact.severity}`} aria-label={`${impact.severity} severity`}>{impact.severity}</span><div><strong>{impact.code.replaceAll("_", " ")}</strong><p>{impact.message}{impact.count ? ` (${impact.count})` : ""}</p></div></li>)}</ul></div>}
      <div className="actions wide"><button type="button" disabled={busy || Boolean(overridesError)} onClick={() => void requestPreview()}>{busy ? "Working…" : "Preview migration"}</button><button className="primary" type="button" disabled={busy || !preview} onClick={() => void saveProfile()}>Save profile revision</button></div>
    </section>}
    <section className="panel" aria-labelledby="capability-cards-title">
      <div className="panel-title"><h3 id="capability-cards-title">Measured capability cards</h3><span>{capabilityState.value?.cards.length ?? 0} exact artifacts</span></div>
      {capabilityState.error ? <Failure message={capabilityState.error} retry={capabilityState.reload} /> : !capabilityState.value ? <div className="loading">Loading capability evidence…</div> : capabilityState.value.cards.length ? <ul className="entity-list">{capabilityState.value.cards.map((entry) => {
        const eligible = entry.card.strategies.filter((item) => item.default_eligible).map((item) => item.strategy);
        const mechanical = entry.card.strategies.filter((item) => item.mechanically_qualified).map((item) => item.strategy);
        const valid = entry.evidence_valid && entry.source_valid && !entry.expired;
        return <li key={entry.card.card_id}><span><strong>{entry.card.card_id}</strong>{` · ${entry.card.identity.quantization} · ${entry.card.identity.model_digest.slice(0, 12)}…`}<br />{valid ? `mechanically qualified: ${mechanical.join(", ") || "none"}` : "invalidated evidence"}{` · default eligible: ${eligible.join(", ") || "none"}`}</span></li>;
      })}</ul> : <p>No capability evidence has been registered.</p>}
      <p className="callout">Only an unexpired exact digest/runtime/profile/settings match with completed narrative review may influence a future default. Explicit legacy fallback remains available.</p>
    </section>
    <form className="panel form-grid settings-secondary" onSubmit={(event) => void submitSettings(event)}><div className="panel-title wide"><h3>Runtime and model</h3><button type="button" disabled={Boolean(modelBusy)} onClick={() => void checkModels()}>{modelBusy === "status" ? "Checking…" : "Check Ollama"}</button></div><label>Ollama URL<input name="ollama_base_url" type="url" defaultValue={config.ollama_base_url} /></label><label>Model<input name="ollama_model" list="ollama-models" defaultValue={config.ollama_model} /><datalist id="ollama-models">{ollama?.models.map((model) => <option key={model} value={model} />)}</datalist></label><label>Model mode<select name="model_mode" defaultValue={config.model_mode}>{["auto", "standard", "compact"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Ingestion profile<input name="ingestion_profile" defaultValue={config.ingestion_profile} /></label><label>Temperature<input name="temperature" type="number" min="0" max="2" step="0.05" defaultValue={config.temperature} /></label><label>Repeat penalty<input name="repeat_penalty" type="number" min="0" step="0.05" defaultValue={config.repeat_penalty} /></label><label>Prediction tokens<input name="num_predict" type="number" min="1" defaultValue={config.num_predict} /></label><label>Context tokens<input name="num_ctx" type="number" min="128" defaultValue={config.num_ctx} /></label><label>Generation strategy<select name="generation_strategy" defaultValue={config.generation_strategy}>{["legacy_delimited", "legacy_json", "typed_fill", "flat_fill"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Default authoring UI<select name="authoring_ui" defaultValue={config.authoring_ui}><option value="legacy">Legacy</option><option value="next">Next</option></select></label>{ollama && <div className="wide" role="status"><h4>Ollama {ollama.status}</h4>{ollama.error && <p>{ollama.error}</p>}{ollama.models.length ? <ul className="entity-list">{ollama.models.map((model) => { const score = ollama.scores[model]; return <li key={model}><span><strong>{model}</strong>{model === ollama.current ? " · configured" : ""}{score ? ` · ${score.ok ? "responsive" : score.error}` : " · untested"}</span><button type="button" disabled={Boolean(modelBusy)} onClick={() => void smokeTestModel(model)}>{modelBusy === model ? "Testing…" : "Smoke test"}</button></li>; })}</ul> : <p>No installed models reported.</p>}</div>}<div className="wide callout">Changing the default UI or model does not migrate drafts or story files. Model smoke tests are cached separately from benchmark evidence. <a href="/legacy">Open legacy now</a>.</div><button className="primary" type="submit">Save runtime settings</button></form></>;
}

function Failure({ message, retry }: { message: string; retry?: () => void }) { return <div className="error-card" role="alert"><strong>Request failed</strong><p>{message}</p>{retry && <button onClick={retry}>Try again</button>}</div>; }

function Application() {
  const initialWorkspace = location.hash.slice(1) as Workspace;
  const [active, setActive] = useState<Workspace>(workspaceItems.some(([id]) => id === initialWorkspace) ? initialWorkspace : "story");
  const configState = useLoad(() => api.config());
  const projectState = useLoad(() => api.projectStatus());
  const [config, setConfig] = useState<HarnessConfig | null>(null);
  const [needsInitialization, setNeedsInitialization] = useState<boolean | null>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  useEffect(() => { if (configState.value) setConfig(configState.value); }, [configState.value]);
  useEffect(() => { if (projectState.value) setNeedsInitialization(projectState.value.is_empty); }, [projectState.value]);
  const notify = (message: string, tone: Notice["tone"] = "ok") => { const id = Date.now() + Math.random(); setNotices((items) => [...items, { id, message, tone }]); setTimeout(() => setNotices((items) => items.filter((item) => item.id !== id)), 5000); };
  const navigate = (workspace: Workspace) => { if (document.body.dataset.dirty === "true" && !confirm("Discard unsaved edits?")) return; setActive(workspace); history.replaceState(null, "", `#${workspace}`); };
  useEffect(() => {
    let navigationPrefix = false;
    let prefixTimer = 0;
    const keyboard = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editing = target?.matches("input, textarea, select, [contenteditable=true]");
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); navigate("tests"); }
      if (event.altKey && /^[1-6]$/.test(event.key)) navigate(workspaceItems[Number(event.key) - 1][0]);
      if (!editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.key.toLowerCase() === "g") {
          navigationPrefix = true;
          clearTimeout(prefixTimer);
          prefixTimer = window.setTimeout(() => { navigationPrefix = false; }, 1200);
        } else if (navigationPrefix) {
          const destination: Record<string, Workspace> = { s: "story", w: "write", o: "world", m: "media", t: "tests" };
          const workspace = destination[event.key.toLowerCase()];
          navigationPrefix = false;
          clearTimeout(prefixTimer);
          if (workspace) { event.preventDefault(); navigate(workspace); }
        }
      }
    };
    addEventListener("keydown", keyboard); return () => { removeEventListener("keydown", keyboard); clearTimeout(prefixTimer); };
  }, []);
  useEffect(() => { document.getElementById("workspace")?.focus(); }, [active]);
  const content = useMemo(() => {
    if (!config || needsInitialization === null) return configState.error || projectState.error ? <Failure message={configState.error || projectState.error} retry={() => { configState.reload(); projectState.reload(); }} /> : <div className="loading">Loading project…</div>;
    if (active === "story" && needsInitialization) return <InitializationWorkspace config={config} notify={notify} onInitialized={(title) => { setConfig({ ...config, story_title: title }); setNeedsInitialization(false); }} />;
    if (active === "story") return config.experience_mode === "story_driven"
      ? <StoryWorkspace />
      : <SystemicStoryWorkspace mode={config.experience_mode} notify={notify} />;
    if (active === "write") return <WriteWorkspace notify={notify} onCommitted={() => navigate("story")} />;
    if (active === "world") return <WorldWorkspace notify={notify} />;
    if (active === "media") return <MediaWorkspace notify={notify} />;
    if (active === "tests") return <TestsWorkspace />;
    return <SettingsWorkspace config={config} onConfig={setConfig} notify={notify} />;
  }, [active, config, configState.error, needsInitialization, projectState.error]);
  return <div className="shell"><header className="topbar"><div><span className="eyebrow">SugarCube authoring system</span><h1 id="project-title">{config?.story_title || "Story Harness"}</h1></div><div className="status-cluster"><span id="mode-badge" className="badge">{config?.experience_mode?.replace("_", " ") || "Loading"}</span><a className="quiet-link" href="/legacy">Legacy UI</a></div></header>
    <aside className="rail"><nav aria-label="Primary navigation">{workspaceItems.map(([id, label], index) => <button key={id} data-workspace={id} aria-keyshortcuts={`Alt+${index + 1}`} aria-current={active === id ? "page" : undefined} onClick={() => navigate(id)}><span>{label}</span></button>)}</nav><div className="rail-foot"><kbd>G then S/W/O/M/T</kbd><span>Navigate</span></div></aside>
    <main id="workspace" tabIndex={-1}>{content}</main><div className="toasts" aria-live="polite">{notices.map((notice) => <div key={notice.id} className={`toast ${notice.tone}`}>{notice.message}</div>)}</div></div>;
}

export function App() { return <ErrorBoundary><Application /></ErrorBoundary>; }

import type {
  BenchmarkRunDetail,
  BenchmarkRunSummary,
  CapabilityCardsState,
  DraftRecord,
  ExperienceMigrationPreview,
  ExperienceProfile,
  ExperienceProfileRevision,
  ExperienceProfileState,
  HarnessConfig,
  MediaSlot,
  MediaFile,
  OllamaStatus,
  OllamaTestScore,
  PassageEntry,
  PassagePlanRecord,
  PassagePlan,
  StoryGraph,
  StoryPlanState,
  SimulationState,
  DraftCompileResponse,
  DraftPlaytestJob,
  TypedGenerateRequest,
  TypedCommitResponse,
  TypedFactDecisionResponse,
  SimulationFixture,
  TopologyState,
  SystemCatalogState,
  EncounterCatalogState,
  ValidationResult,
  WorldSheet,
} from "./types";

export class ApiFailure extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export class ApiClient {
  constructor(private readonly base = "") {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.base}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof payload.detail === "string"
        ? payload.detail
        : payload.detail?.message || `Request failed (${response.status})`;
      throw new ApiFailure(response.status, payload.error || payload.detail?.code || "request_failed", detail);
    }
    return payload as T;
  }

  graph = () => this.request<StoryGraph>("/api/graph");
  plan = () => this.request<StoryPlanState>("/api/plan");
  createBeat = (text: string, act: string, expectedFingerprint: string) => this.request<Record<string, unknown>>("/api/plan/beats", { method: "POST", body: JSON.stringify({ text, act, expected_story_fingerprint: expectedFingerprint }) });
  updateBeat = (id: string, text: string, act: string, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/beats/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ text, act, expected_story_fingerprint: expectedFingerprint }) });
  deleteBeat = (id: string, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/beats/${encodeURIComponent(id)}`, { method: "DELETE", body: JSON.stringify({ expected_story_fingerprint: expectedFingerprint }) });
  createArc = (name: string, goal: string, expectedFingerprint: string) => this.request<Record<string, unknown>>("/api/plan/arcs", { method: "POST", body: JSON.stringify({ name, goal, expected_story_fingerprint: expectedFingerprint }) });
  updateArc = (name: string, body: Record<string, unknown>, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/arcs/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify({ ...body, expected_story_fingerprint: expectedFingerprint }) });
  createScene = (arc: string, body: Record<string, unknown>, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/arcs/${encodeURIComponent(arc)}/scenes`, { method: "POST", body: JSON.stringify({ ...body, expected_story_fingerprint: expectedFingerprint }) });
  updateScene = (arc: string, id: string, body: Record<string, unknown>, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/arcs/${encodeURIComponent(arc)}/scenes/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ ...body, expected_story_fingerprint: expectedFingerprint }) });
  deleteScene = (arc: string, id: string, expectedFingerprint: string) => this.request<Record<string, unknown>>(`/api/plan/arcs/${encodeURIComponent(arc)}/scenes/${encodeURIComponent(id)}`, { method: "DELETE", body: JSON.stringify({ expected_story_fingerprint: expectedFingerprint }) });
  passage = (id: string) => this.request<PassageEntry & { raw: string }>(`/api/passage/${encodeURIComponent(id)}`);
  validation = () => this.request<ValidationResult>("/api/validate");
  benchmarkRuns = async () => (await this.request<{ runs: BenchmarkRunSummary[] }>("/api/benchmarks/runs")).runs;
  benchmarkRun = (id: string) => this.request<BenchmarkRunDetail>(`/api/benchmarks/runs/${encodeURIComponent(id)}`);
  config = () => this.request<HarnessConfig>("/api/config");
  capabilityCards = () => this.request<CapabilityCardsState>("/api/capability-cards");
  projectStatus = () => this.request<{ is_empty: boolean; passage_count: number; has_premise: boolean }>("/api/project-status");
  initializeStory = (body: Record<string, unknown>) => this.request<{ status: string }>("/api/init-story", { method: "POST", body: JSON.stringify(body) });
  updateConfig = (body: Partial<HarnessConfig>) => this.request<HarnessConfig>("/api/config", { method: "POST", body: JSON.stringify(body) });
  ollamaStatus = () => this.request<OllamaStatus>("/api/ollama/status");
  testModel = (model: string) => this.request<OllamaTestScore>("/api/ollama/test-model", { method: "POST", body: JSON.stringify({ model }) });
  experienceProfile = () => this.request<ExperienceProfileState>("/api/experience-profile");
  previewExperienceProfile = (expectedRevision: number, profile: ExperienceProfile) => this.request<ExperienceMigrationPreview>(
    "/api/experience-profile/preview",
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision, profile }) },
  );
  saveExperienceProfile = (expectedRevision: number, profile: ExperienceProfile, previewFingerprint: string) => this.request<ExperienceProfileRevision>(
    "/api/experience-profile/revisions",
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision, profile, preview_fingerprint: previewFingerprint }) },
  );
  topology = () => this.request<TopologyState>("/api/topology");
  systems = () => this.request<SystemCatalogState>("/api/systems");
  encounters = () => this.request<EncounterCatalogState>("/api/encounters");
  simulationFixtures = () => this.request<import("./types").SimulationFixtureCatalogState>("/api/simulation-fixtures");
  updateSystems = (rules: Array<Record<string, unknown>>, expectedFingerprint: string) => this.request<SystemCatalogState>("/api/systems", { method: "PUT", body: JSON.stringify({ rules, expected_fingerprint: expectedFingerprint }) });
  updateEncounters = (templates: Array<Record<string, unknown>>, expectedFingerprint: string) => this.request<EncounterCatalogState>("/api/encounters", { method: "PUT", body: JSON.stringify({ templates, expected_fingerprint: expectedFingerprint }) });
  updateSimulationFixtures = (fixtures: SimulationFixture[], expectedFingerprint: string) => this.request<import("./types").SimulationFixtureCatalogState>("/api/simulation-fixtures", { method: "PUT", body: JSON.stringify({ fixtures, expected_fingerprint: expectedFingerprint }) });
  addLocation = (expectedRevision: number, location: Record<string, unknown>) => this.request<TopologyState>(
    "/api/topology/locations", { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision, location }) },
  );
  addRoute = (expectedRevision: number, route: Record<string, unknown>) => this.request<TopologyState>(
    "/api/topology/routes", { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision, route }) },
  );
  updateLocation = (id: string, expectedRevision: number, location: Record<string, unknown>) => this.request<TopologyState>(`/api/topology/locations/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ expected_revision: expectedRevision, location }) });
  deleteLocation = (id: string, expectedRevision: number) => this.request<TopologyState>(`/api/topology/locations/${encodeURIComponent(id)}`, { method: "DELETE", body: JSON.stringify({ expected_revision: expectedRevision }) });
  updateRoute = (id: string, expectedRevision: number, route: Record<string, unknown>) => this.request<TopologyState>(`/api/topology/routes/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ expected_revision: expectedRevision, route }) });
  deleteRoute = (id: string, expectedRevision: number) => this.request<TopologyState>(`/api/topology/routes/${encodeURIComponent(id)}`, { method: "DELETE", body: JSON.stringify({ expected_revision: expectedRevision }) });
  createSimulation = (body: Record<string, unknown>) => this.request<SimulationState>(
    "/api/simulations", { method: "POST", body: JSON.stringify(body) },
  );
  applySimulationAction = (sessionId: string, expectedRevision: number, kind: string, actionId: string) => this.request<SimulationState>(
    `/api/simulations/${encodeURIComponent(sessionId)}/actions`,
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision, kind, action_id: actionId }) },
  );
  compileDraft = (record: DraftRecord, expectedDraftFingerprint: string) => this.request<DraftCompileResponse>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/compile`,
    { method: "POST", body: JSON.stringify({ expected_draft_fingerprint: expectedDraftFingerprint }) },
  );
  startDraftPlaytest = (record: DraftRecord, expectedDraftFingerprint: string, initialState: Record<string, unknown> = {}, choiceSlotIds?: string[]) => this.request<DraftPlaytestJob>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/playtest`,
    { method: "POST", body: JSON.stringify({ expected_draft_fingerprint: expectedDraftFingerprint, initial_state: initialState, ...(choiceSlotIds ? { choice_slot_ids: choiceSlotIds } : {}) }) },
  );
  draftPlaytest = (jobId: string) => this.request<DraftPlaytestJob>(`/api/playtests/${encodeURIComponent(jobId)}`);
  characters = async () => (await this.request<{ characters: Array<Record<string, unknown>> }>("/api/characters")).characters;
  character = (id: string) => this.request<WorldSheet>(`/api/characters/${encodeURIComponent(id)}`);
  createCharacter = (body: Record<string, unknown>) => this.request<{ status: string; id: string }>("/api/characters", { method: "POST", body: JSON.stringify(body) });
  saveCharacter = (id: string, content: string, expectedFingerprint: string) => this.request<{ status: string; id: string; content_fingerprint: string }>(`/api/characters/${encodeURIComponent(id)}`, { method: "POST", body: JSON.stringify({ content, expected_content_fingerprint: expectedFingerprint }) });
  lore = async () => (await this.request<{ lore: Array<Record<string, unknown>> }>("/api/lore")).lore;
  loreEntry = (category: string, id: string) => this.request<WorldSheet>(`/api/lore/${encodeURIComponent(category)}/${encodeURIComponent(id)}`);
  createLore = (body: Record<string, unknown>) => this.request<{ status: string; category: string; id: string }>("/api/lore", { method: "POST", body: JSON.stringify(body) });
  saveLore = (category: string, id: string, content: string, expectedFingerprint: string) => this.request<{ status: string; content_fingerprint: string }>(`/api/lore/${encodeURIComponent(category)}/${encodeURIComponent(id)}`, { method: "POST", body: JSON.stringify({ content, expected_content_fingerprint: expectedFingerprint }) });
  mediaSlots = async (): Promise<MediaSlot[]> => {
    const payload = await this.request<Record<string, MediaSlot>>("/api/media/slots");
    return Object.entries(payload).map(([id, slot]) => ({ id, ...slot }));
  };
  mediaFiles = async () => (await this.request<{ files: MediaFile[] }>("/api/media/files")).files;
  importMedia = (srcPath: string, destName: string) => this.request<{ status: string; rel_path: string }>(
    "/api/media/import", { method: "POST", body: JSON.stringify({ src_path: srcPath, dest_name: destName }) },
  );
  mediaPreviewUrl = (id: string) => `${this.base}/api/media/slots/${encodeURIComponent(id)}/preview`;
  updateMediaSlot = (id: string, body: Record<string, unknown>) => this.request<{ status: string }>(`/api/media/slots/${encodeURIComponent(id)}/meta`, { method: "POST", body: JSON.stringify(body) });
  resolveMediaSlot = (id: string, path: string, expectedFingerprint: string) => this.request<{ status: string }>(`/api/media/slots/${encodeURIComponent(id)}/resolve`, { method: "POST", body: JSON.stringify({ resolved_path: path, expected_slot_fingerprint: expectedFingerprint }) });
  unresolveMediaSlot = (id: string, expectedFingerprint: string) => this.request<{ status: string }>(`/api/media/slots/${encodeURIComponent(id)}/unresolve`, { method: "POST", body: JSON.stringify({ expected_slot_fingerprint: expectedFingerprint }) });
  generateDraft = (body: TypedGenerateRequest) => this.request<DraftRecord>("/api/typed/generate", { method: "POST", body: JSON.stringify(body) });
  createPassagePlan = (plan: PassagePlan, arcName: string) => this.request<PassagePlanRecord>("/api/plans", { method: "POST", body: JSON.stringify({ plan, arc_name: arcName }) });
  revisePassagePlan = (record: PassagePlanRecord, plan: PassagePlan, arcName: string) => this.request<PassagePlanRecord>(`/api/plans/${encodeURIComponent(record.plan.plan_id)}/revisions`, { method: "POST", body: JSON.stringify({ plan, arc_name: arcName, expected_plan_fingerprint: record.fingerprint }) });
  approvePassagePlan = (record: PassagePlanRecord) => this.request<PassagePlanRecord>(`/api/plans/${encodeURIComponent(record.plan.plan_id)}/revisions/${record.plan.revision}/approve`, { method: "POST", body: JSON.stringify({ expected_plan_fingerprint: record.fingerprint }) });
  draft = (id: string, revision: number) => this.request<DraftRecord>(`/api/drafts/${encodeURIComponent(id)}/${revision}`);
  latestDraft = (id: string) => this.request<DraftRecord>(`/api/drafts/${encodeURIComponent(id)}`);
  editDraft = (record: DraftRecord, fingerprint: string) => this.request<DraftRecord>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/edit`,
    { method: "POST", body: JSON.stringify({ expected_draft_fingerprint: fingerprint, fill: record.draft.fill }) },
  );
  validateDraft = (record: DraftRecord, fingerprint: string) => this.request<DraftRecord>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/validate`,
    { method: "POST", body: JSON.stringify({ expected_draft_fingerprint: fingerprint }) },
  );
  commitDraft = (record: DraftRecord, fingerprint: string) => this.request<TypedCommitResponse>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/commit`,
    { method: "POST", body: JSON.stringify({
      expected_plan_revision: record.draft.plan.revision,
      expected_draft_fingerprint: fingerprint,
      expected_parent_fingerprint: record.parent_fingerprint || "",
    }) },
  );
  decideDraftFact = (draftId: string, revision: number, key: string, action: "accept" | "reject") => this.request<TypedFactDecisionResponse>(
    `/api/drafts/${encodeURIComponent(draftId)}/${revision}/facts/${encodeURIComponent(key)}/decision`,
    { method: "POST", body: JSON.stringify({ action }) },
  );
  rejectDraft = (record: DraftRecord, fingerprint: string) => this.request<DraftRecord>(
    `/api/drafts/${encodeURIComponent(record.draft.draft_id)}/${record.draft.revision}/reject`,
    { method: "POST", body: JSON.stringify({ expected_draft_fingerprint: fingerprint }) },
  );
}

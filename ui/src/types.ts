import type { components } from "./generated/openapi";

export interface ApiErrorShape { error: string; detail: string }

export interface ChoiceEntry {
  text?: string;
  target?: string;
  child?: string;
}

export interface PassageEntry {
  id?: string;
  title?: string;
  file?: string;
  passage_type?: string;
  type?: string;
  choices?: ChoiceEntry[];
  [key: string]: unknown;
}

export interface StoryGraph {
  passages: Record<string, PassageEntry>;
  start_passage?: string;
  [key: string]: unknown;
}

export interface Diagnostic {
  code?: string;
  level?: string;
  message?: string;
  passage_id?: string;
  path?: Array<string | number>;
  [key: string]: unknown;
}

export interface ValidationResult {
  valid?: boolean;
  errors?: Diagnostic[];
  warnings?: Diagnostic[];
  [key: string]: unknown;
}

export interface HarnessConfig {
  story_title: string;
  ollama_model: string;
  ollama_base_url: string;
  model_mode: string;
  ingestion_profile: string;
  temperature: number;
  repeat_penalty: number;
  num_predict: number;
  num_ctx: number;
  generation_strategy: string;
  experience_mode: "story_driven" | "hybrid" | "sandbox";
  authoring_ui: "legacy" | "next";
  [key: string]: unknown;
}

export interface OllamaTestScore {
  ok: boolean;
  reply: string;
  error: string;
  oom?: boolean;
  tested_at: string;
}

export interface OllamaStatus {
  status: "ok" | "error";
  error?: string;
  models: string[];
  current: string;
  scores: Record<string, OllamaTestScore>;
}

export type ExperienceMode = components["schemas"]["ExperienceMode"];
export type StoryGuidance = components["schemas"]["StoryGuidance"];
export type TimeModel = components["schemas"]["TimeModel"];
export type GoalModel = components["schemas"]["GoalModel"];
export type EndingPolicy = components["schemas"]["EndingPolicy"];
export type CharacterSimulation = components["schemas"]["CharacterSimulation"];
export type ExperienceOverride = components["schemas"]["ExperienceOverride"];
export type ExperienceProfile = components["schemas"]["ExperienceProfile"];

export interface ExperienceProfileState {
  profile: ExperienceProfile;
  fingerprint: string;
  source: "stored" | "compatibility_default";
  presets: Record<ExperienceMode, ExperienceProfile>;
}

export interface ExperienceMigrationPreview {
  expected_revision: number;
  current_profile_fingerprint: string;
  graph_fingerprint: string;
  candidate: ExperienceProfile;
  candidate_fingerprint: string;
  preview_fingerprint: string;
  graph_rewrite_required: false;
  impacts: Array<{ code: string; severity: "info" | "warning"; message: string; count: number }>;
}

export interface ExperienceProfileRevision {
  profile: ExperienceProfile;
  fingerprint: string;
  source: "stored";
  preview: ExperienceMigrationPreview;
}

export interface LocationAction {
  id: string;
  label: string;
  eligibility: Array<Record<string, unknown>>;
  effects: Array<Record<string, unknown>>;
  time_cost: number;
  encounter_table_refs: string[];
}

export interface LocationNode {
  id: string;
  name: string;
  region_id: string;
  tags: string[];
  actions: LocationAction[];
  encounter_table_refs: string[];
}

export interface TopologyRoute {
  id: string;
  source: string;
  destination: string;
  eligibility: Array<Record<string, unknown>>;
  resource_cost: Record<string, number>;
  travel_effects: Array<Record<string, unknown>>;
  risk_tags: string[];
  time_cost: number;
}

export interface TopologyState {
  topology: { schema_version: number; revision: number; locations: LocationNode[]; routes: TopologyRoute[] } | null;
  fingerprint: string;
  diagnostics: Diagnostic[];
}

export interface SimulationState {
  session: {
    session_id: string;
    revision: number;
    current_location: string;
    clock: { model: string; tick: number };
    world_state: Record<string, unknown>;
    resources: Record<string, number>;
    completed_anchor_ids: string[];
    factions: FactionSeed[];
    character_stat_definitions: CharacterStatDefinition[];
    characters: CharacterRuntimeSeed[];
    visits: Array<{ visit_index: number; location_id: string; entered_tick: number; exited_tick?: number; selected_actions: string[] }>;
  };
  trace?: { action_kind: string; action_id: string; tick_before: number; tick_after: number } | null;
  fingerprint: string;
  opportunities: Array<{ id: string; kind: "local_action" | "travel" | "authored_anchor"; label: string; source_id: string; location_id: string }>;
}

export interface CharacterStatDefinition {
  id: string;
  value_type: "bool" | "int" | "float" | "string";
  default: unknown;
  minimum?: number | null;
  maximum?: number | null;
  visibility: "public" | "model" | "private";
  allowed_operations: Array<"set" | "add" | "clamp">;
  decay_per_tick?: number | null;
  description: string;
}

export interface CharacterRuntimeSeed {
  character_id: string;
  revision: number;
  current_location: string;
  activity: string;
  stats: Record<string, unknown>;
  [key: string]: unknown;
}

export interface FactionSeed {
  faction_id: string;
  influence: number;
  disposition: number;
  resources: Record<string, number>;
  relationships: Record<string, number>;
}

export interface SimulationFixture {
  id: string;
  label: string;
  start_location: string;
  seed: number;
  world_state: Record<string, unknown>;
  resources: Record<string, number>;
  factions: FactionSeed[];
  character_stat_definitions: CharacterStatDefinition[];
  characters: CharacterRuntimeSeed[];
}

export interface SimulationFixtureCatalogState {
  catalog: { schema_version: number; revision: number; fixtures: SimulationFixture[] };
  fingerprint: string;
}

export interface SystemCatalogState {
  catalog: { schema_version: number; revision: number; rules: Array<Record<string, unknown> & { id: string; trigger: string; priority: number }> };
  fingerprint: string;
}

export interface EncounterCatalogState {
  catalog: { schema_version: number; revision: number; templates: Array<Record<string, unknown> & { id: string; label: string; weight: number }> };
  fingerprint: string;
}

export interface WorldSheet {
  id: string;
  category?: string;
  content: string;
  content_fingerprint: string;
  appearances?: string[];
  keywords?: string[];
  tags?: string[];
}

export interface StoryPlanState {
  story_fingerprint: string;
  acts: string[];
  open_questions: string[];
  beats: Array<{ id: string; text: string; act: string; status: string; covered: boolean }>;
  arcs: Array<{
    arc: string;
    goal: string;
    summary: string;
    status: string;
    passage_count: number;
    beat_ids: string[];
    scenes: Array<{
      id: string;
      title: string;
      summary: string;
      keywords: string[];
      characters: string[];
      beat_ids: string[];
      passage_id: string;
      status: string;
    }>;
  }>;
  gaps: Record<string, string[]>;
}

export interface MediaSlot {
  id?: string;
  slot_id?: string;
  passage_id?: string;
  status?: string;
  [key: string]: unknown;
}

export interface MediaFile {
  name: string;
  rel_path: string;
  type: "image" | "audio" | "video";
  size: number;
}

export type DraftRecord = components["schemas"]["DraftRecord"];
export type DraftCompileResponse = components["schemas"]["TypedDraftCompileResponse"];
export type DraftPlaytestJob = components["schemas"]["TypedDraftPlaytestJobResponse"];
export type TypedGenerateRequest = components["schemas"]["TypedGenerateRequest"];
export type TypedCommitResponse = components["schemas"]["TypedCommitResponse"];
export type TypedFactDecisionResponse = components["schemas"]["TypedFactDecisionResponse"];
export type ContinuityProposal = components["schemas"]["ContinuityProposal"];
export type PassagePlan = components["schemas"]["PassagePlan"];
export type PassagePlanRecord = components["schemas"]["PassagePlanRecordResponse"];
export type BenchmarkRunSummary = components["schemas"]["BenchmarkRunSummaryResponse"];
export type BenchmarkRunDetail = components["schemas"]["BenchmarkRunDetailResponse"];
export type CapabilityCardsState = components["schemas"]["CapabilityCardsResponse"];

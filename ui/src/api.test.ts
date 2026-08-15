import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiFailure } from "./api";

function response(payload: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => payload } as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("ApiClient mutation contracts", () => {
  it("always sends the expected fingerprint for catalog revisions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ catalog: { fixtures: [] }, fingerprint: "next" }));
    vi.stubGlobal("fetch", fetchMock);

    await new ApiClient("/base").updateSimulationFixtures([], "current");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/base/api/simulation-fixtures");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ fixtures: [], expected_fingerprint: "current" });
  });

  it("keeps expected story fingerprints on delete requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    vi.stubGlobal("fetch", fetchMock);

    await new ApiClient().deleteBeat("beat/one", "story-fingerprint");

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/plan/beats/beat%2Fone");
    expect(init.method).toBe("DELETE");
    expect(JSON.parse(String(init.body))).toEqual({ expected_story_fingerprint: "story-fingerprint" });
  });

  it("normalizes structured backend conflicts without losing their stable code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      detail: { code: "draft_superseded", message: "A newer revision exists" },
    }, false, 409)));

    const error = await new ApiClient().latestDraft("draft_one").catch((reason) => reason);

    expect(error).toBeInstanceOf(ApiFailure);
    expect(error).toMatchObject({ status: 409, code: "draft_superseded", message: "A newer revision exists" });
  });

  it("binds compile and playtest operations to the exact draft fingerprint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ status: "queued" }));
    vi.stubGlobal("fetch", fetchMock);
    const record = { draft: { draft_id: "draft/one", revision: 3 } } as never;
    const client = new ApiClient();

    await client.compileDraft(record, "draft-fingerprint");
    await client.startDraftPlaytest(record, "draft-fingerprint", { weather_safe: true }, ["continue"]);
    await client.draftPlaytest("playtest/one");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/drafts/draft%2Fone/3/compile");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      expected_draft_fingerprint: "draft-fingerprint",
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/drafts/draft%2Fone/3/playtest");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1].body))).toEqual({
      expected_draft_fingerprint: "draft-fingerprint",
      initial_state: { weather_safe: true },
      choice_slot_ids: ["continue"],
    });
    expect(fetchMock.mock.calls[2][0]).toBe("/api/playtests/playtest%2Fone");
  });

  it("uses the generated request and fingerprint-binds validation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient();
    const context = {
      premise: "", parent_passage_id: "", parent_prose: "", parent_summary: "",
      story_recall: "", world_facts: [], entity_facts: [], open_threads: [], inspiration: "",
    };

    await client.generateDraft({
      plan_id: "plan_one", plan_revision: 2, expected_plan_fingerprint: "plan-fingerprint",
      context, author_task: "Write it.", passage_id: "scene_one", arc_name: "main",
      parent_passage_id: "", branch_name: "main", strategy: "typed_fill",
    });
    await client.validateDraft({ draft: { draft_id: "draft_one", revision: 4 } } as never, "draft-fingerprint");

    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toMatchObject({
      plan_id: "plan_one", plan_revision: 2, expected_plan_fingerprint: "plan-fingerprint",
    });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/drafts/draft_one/4/validate");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1].body))).toEqual({
      expected_draft_fingerprint: "draft-fingerprint",
    });
  });
});

# Story Harness Next UI

This is the greenfield React/TypeScript authoring interface. The existing UI
remains the default and is always available at `/legacy`.

## Development

```bash
cd ui
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000` during development.

## Production bundle

```bash
cd ui
npm ci
npm run build
```

The build is written to `harness/server/ui/` and FastAPI serves it at `/next`.
The committed bundle lets Python-only installations run the interface without
installing Node.

The production build also runs `npm run contracts:check`. This compares the
committed `openapi.json` with FastAPI's current schema and regenerates the
TypeScript declaration in `src/generated/openapi.ts` in memory. If either
artifact is stale, the build fails. After changing a backend request or typed
domain contract, refresh both artifacts with:

```bash
cd ui
npm run contracts:generate
```

The hand-authored UI facade consumes generated `ExperienceProfile` and
`PassagePlan` shapes. Response payloads for endpoints that still lack FastAPI
`response_model` declarations remain hand-authored and are an explicit
follow-up contract gap.

To make it the project default, set `authoring_ui: next` in `config.yaml` or
set `HARNESS_AUTHORING_UI=next`. Set either value to `legacy` for immediate
rollback. No story or draft migration occurs when switching interfaces.

Set `HARNESS_BENCHMARK_OUTPUTS` to a benchmark output directory if persisted
runs live outside the active story project.

The served Playwright workflows inject the pinned axe-core audit across the
major initialized, settings, sandbox, authoring, diagnostics, and review
states. Install UI development dependencies before running those E2E checks.

# Legacy fallback and retirement policy v1

Status: frozen before default promotion. No promotion window is active.

## Window

The fallback window starts only when a stable release first changes either
`generation_strategy` away from `legacy_delimited` or `authoring_ui` away from
`legacy`. That release is the promotion release.

Both legacy selections must remain supported throughout the promotion release
and the immediately following stable release, and for no less than 30 calendar
days after the promotion release. A prerelease, nightly, or release candidate
does not start or satisfy the window. If the next stable release occurs before
day 30, retirement remains prohibited until day 30. If no next stable release
occurs, retirement remains prohibited.

## Required fallback behavior

- `generation_strategy: legacy_delimited` remains visible and selectable.
- `authoring_ui: legacy` and `HARNESS_AUTHORING_UI=legacy` remain supported.
- `/legacy` remains directly reachable independently of the configured UI.
- Rollback changes configuration only; it must not rewrite story files,
  immutable plans, draft revisions, or simulation state.
- Readers for already stored legacy projects and drafts are retained beyond
  production-path retirement.

## Rollback triggers

Operators revert the affected default while investigating if any supported
profile shows a reproducible commit corruption, unrecoverable draft conflict,
loss of authored content, security regression, accessibility blocker, or a
promotion-gate regression under a compatible capability card. A model artifact
without compatible evidence routes to a supported fallback rather than being
treated as covered by another model's benchmark.

## Retirement gate

Legacy production behavior may be removed only after all of the following:

1. The release/time window above has elapsed.
2. The frozen mechanical, latency, narrative, browser, and accessibility gates
   remain satisfied for every promoted capability card.
3. Release evidence records no unresolved fallback-triggering incident.
4. A configuration-only rollback drill succeeds against a representative
   existing Story-driven project and does not modify stored content.
5. Usage evidence confirms the code proposed for removal is no longer needed.
6. Legacy prompts are frozen as research fixtures and legacy storage readers
   have dedicated compatibility tests.

Failure of any item extends the window; it never permits partial retirement.
Removing the legacy UI and removing the legacy generation strategy are separate
decisions and each must satisfy this policy.

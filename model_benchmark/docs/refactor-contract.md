# Benchmark Contract for the Harness Refactor

## Purpose

The default capability benchmark is a contract for the next harness
architecture, not a reward function for preserving the current parser. The
same semantic cases should remain usable when generation moves from delimited
text to constrained JSON, a typed story AST, staged author/mechanic calls, or a
compiler-in-the-loop repair path.

## Evaluation layers

Each harness-contract result separates three questions:

1. **Raw contract** — did the model emit the requested transport envelope?
2. **Structured handoff** — can the response be normalized into prose and
   reachable choices?
3. **Semantic observables** — are requested facts, state updates, input fields,
   dialogue, style, and choice hints represented correctly?

Raw contract is intentionally non-gating. It remains visible as a model and
prompt diagnostic, but parser recovery or deterministic framing should be
judged by final handoff quality rather than counted as raw model compliance.

The executable refactor profiles sharpen the middle layer into two gates:

1. **Plan adherence** — the fill preserves the plan ID, revision, slot set,
   slot kinds, fixed speakers, and allowed typed references.
2. **Fill completeness** — every trusted narrative and choice slot is filled,
   with a summary and at least one beat.

They then score architecture-neutral semantic observables. One result record is
created per original model request; parser or repair attempts must not inflate
the denominator.

## Refactor boundary

The default model call owns:

- prose, dialogue, and inner-thought text in predefined narrative slots;
- choice labels and hints in predefined choice slots;
- summary, beats, and bounded continuity proposals.

An optional, separately scored mechanic call may propose only guards, effects,
or components explicitly left open by the trusted plan. It cannot add state
targets, operations, slots, or passage authority.

The harness owns:

- the trusted `PassagePlan`, slot identities, passage mode, allowed state IDs,
  and required mechanic components;
- passage IDs, files, graph edges, and link targets;
- SugarCube setters, links, forms, loops, and type-specific rendering;
- schema validation, state invariants, compilation, repair policy, and browser
  execution;
- deciding whether a proposal is committed.

Tests should therefore start from a fixed plan and assert resolved semantic
effects such as state ID `has_key` becoming true or a textbox component bound
to state ID `name`. They must not require the model-facing contract to contain
SugarCube `$` variables or macro syntax.

## Cohorts

- `canary` samples the current direct-generation matrix and eight
  harness-contract cases.
- `core` uses a smaller covering array plus all twelve transitional
  harness-contract cases.
- `full` retains historical direct-SugarCube, strict conversation, style,
  plain-text, and stress probes.
- `refactor-canary` is a ten-case subset for quick future-contract checks.
- `refactor-core` is the frozen 24-case architecture baseline. It contains only
  fixed `PassagePlan` cases and architecture-neutral expected outcomes.

Do not compare aggregate rates across these profiles or use the mixed `core`
aggregate for architecture promotion. For refactor decisions, compare matching
`refactor-core` plan IDs, revisions, model artifacts, and seeds. Report raw
contract, structured handoff, semantic correctness, compilation, browser
playability, latency, and tokens as separate dimensions over every original
request.

The executable architecture treatments are:

- `typed_fill`: an explicit narrative-block/inline-part AST;
- `flat_fill`: smaller slot-keyed JSON strings with deterministic typed-reference
  markers.

Both use case-specific schemas derived from the trusted plan and normalize to
the same `RefactorFill` before scoring. The case corpus is shared and remains
independent of SugarCube syntax; later staged-generation, compiler, and repair
architectures should consume the same plan IDs and revisions.

## Next adapters

New generation architectures should combine the same trusted `PassagePlan`
with architecture-specific fills/proposals, then normalize into one assembled
`PassageDraft` before semantic scoring. Add adapters rather than forking case
definitions. The next benchmark gates should be deterministic compile, exact
state transaction, and browser choice execution; those belong after structured
handoff and must not be approximated with keyword checks.

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

## Refactor boundary

The model owns:

- scene intent, prose, dialogue, and inner monologue;
- choice text and destination hints;
- explicit state-transition proposals;
- structured input-field proposals;
- continuity facts, beats, and entity updates.

The harness owns:

- passage IDs, files, graph edges, and link targets;
- SugarCube setters, links, forms, loops, and type-specific rendering;
- schema validation, state invariants, compilation, repair policy, and browser
  execution;
- deciding whether a proposal is committed.

Tests should therefore assert normalized effects such as `$hasKey = true` or a
`textbox` targeting `$name`, not require the model to spell the SugarCube code
that deterministic compilation will generate.

## Cohorts

- `canary` samples the current direct-generation matrix and eight
  harness-contract cases.
- `core` uses a smaller covering array plus all twelve harness-contract cases.
- `full` retains historical direct-SugarCube, strict conversation, style,
  plain-text, and stress probes.

Do not compare aggregate rates across these profiles. For refactor decisions,
compare matching case IDs and seeds, then report raw contract, structured
handoff, semantic correctness, compilation, browser playability, latency, and
tokens as separate dimensions.

## Next adapters

New generation architectures should normalize into the existing parsed story
shape before semantic scoring. Add architecture-specific adapters rather than
forking case definitions. The next benchmark gates should be deterministic
compile, exact state transaction, and browser choice execution; those belong
after structured handoff and must not be approximated with keyword checks.

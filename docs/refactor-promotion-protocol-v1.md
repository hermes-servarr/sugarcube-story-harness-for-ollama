# Refactor Promotion Protocol v1

Frozen: 2026-08-14, before the replay-variance executions and before decoding
the blinded narrative-review bundles.

## Same-seed replay baseline

- Workload: frozen `sandbox-core` corpus and all three architectures
  (`legacy_json`, `typed_fill`, `flat_fill`).
- Model: `orinth:latest`, exact digest
  `d9c5b9682ac92a1a4d2811fadd5c5a3c24010b5c34349fc49c45d3fa3e4fbf45`,
  Q4_K_M, Ollama 0.32.5.
- Generation: temperature 0.2, `num_predict` 640, timeout 180 seconds, sampling
  seed 42.
- Execute three independent one-run invocations. Do not use `--runs 3`, because
  the benchmark intentionally increments that seed to 42, 43, and 44.
- Apply the same frozen browser evaluator to every invocation. Failed,
  malformed, timed-out, and unreviewable requests remain in the denominator.
- Report every result layer independently. For each architecture/layer, replay
  noise is the range (maximum minus minimum) of the three original-request
  pass rates. Do not average layers into a composite score.

The prior five-seed run used Python 3.14.2. The replay campaign uses the
currently installed Python 3.14.3, so the campaign is a new internally matched
baseline; it must not be presented as byte-identical reproduction of the old
parent runtime.

## Promotion margin rule

After all three replay runs are frozen, define the request-level playable
noise floor as the largest replay range observed across the candidate and
legacy control. The required candidate improvement is an integer percentage-
point margin equal to `max(5, floor(noise_floor) + 1)`, which is therefore
strictly larger than the measured noise floor. Freeze the resulting number in
this document before starting the ten-seed confirmation.

The confirmation cohort uses seeds 42 through 51 with matched model, case,
architecture, prompt/schema, compiler/evaluator, and generation settings.
Promotion still requires every independent gate in the rebuild plan; a large
paired win count cannot compensate for a failed runtime, handoff, latency, or
narrative-quality gate.

### Frozen replay outcome

Completed 2026-08-14 using browser children `20260814_030727_f0844428`,
`20260814_031914_d8f9f7b9`, and `20260814_033054_8c56fee4`.

- Every run contains 24 original requests per architecture plus the 7 frozen
  deterministic Sandbox records.
- Flat: request pass 15/24 and original-request playable 24/24 in every run.
- Typed: request pass 13/24 and original-request playable 22/24 in every run.
- Legacy: request pass 7/24 and original-request playable 17/24 in every run.
- All 72 raw generation responses are byte-identical across the three runs.
- Observed request-playable noise floor: 0 percentage points.
- Formula-derived required promotion margin, now frozen before confirmation:
  **5 percentage points**.

Machine-readable evidence is `benchmark_outputs/replay_variance_seed42_v1.json`.

## Ten-seed confirmation outcome

The original compiler-v1 confirmation remains immutable. Compiler-v2 was
confirmed on 2026-08-14 using generation parent
`20260814_090812_93244233` and zero-model-call browser child
`20260814_092621_759ed6cf`. The parent contains all 727 expected records:
240 requests for each architecture over seeds 42 through 51, plus the seven
deterministic Sandbox records. The child preserves all 727 request identities
and generation fields byte-for-byte and links to parent results SHA-256
`c22c49456135bef663e94b00478e57fad8400c4eaadf129c0883f720738571c5`.

- Legacy: request pass `61/240`; original-request playable `145/240`
  (60.4%); compiled-playable `145/149` (97.3%).
- Typed: request pass `133/240`; original-request playable `221/240`
  (92.1%); compiled-playable `221/221` (100%). Typed exceeds legacy
  request playability by 31.7 percentage points, with 83 paired wins, 7
  losses, and 150 ties (exact two-sided p=`1.32e-17`).
- Flat: request pass `142/240`; original-request playable `240/240` (100%);
  compiled-playable `240/240` (100%). Flat exceeds legacy request playability
  by 39.6 percentage points, with 95 paired wins, 0 losses, and 145 ties
  (exact two-sided p=`5.05e-29`).
- Typed normalized handoff and exact state transaction are both `221/240`
  (92.1%). Flat normalized handoff is `239/240` (99.6%) and exact state
  transaction is `240/240` (100%).
- Every assembled, semantically accepted draft compiles: typed `133/133` and
  flat `143/143`. Three additional typed responses passed the independent
  semantic-observable checks but did not assemble into drafts (two fixed-
  speaker violations and one duplicate narrative slot); they remain failed
  original requests.
- Fill p95 is 10.350 seconds for legacy, 12.180 seconds for typed (+17.7%),
  and 8.747 seconds for flat (-15.5%). Both candidates satisfy the frozen
  +25% latency limit.
- Typed request playability ranges from `21/24` to `23/24` across individual
  seeds; flat is `24/24` at every seed; legacy ranges from `12/24` to `17/24`.
  Both candidate improvements exceed the frozen 5-point margin on every seed.

The reproducible analyzer and its hash-linked output are
`model_benchmark/promotion_confirmation.py` and
`benchmark_outputs/promotion_confirmation_ten_seed_v2.json`. Both candidate
architectures clear the automated mechanical and latency gates for this exact
model artifact; flat is the stronger mechanical candidate. The human
narrative gate remains `not_assessed`, so this outcome does not authorize a
default change.

The deterministic issuer registered this outcome as
`benchmark_outputs/capability_cards/qwen35-9b-q4_k_m-mechanical-v2.json`
with fingerprint
`77ebcd62bd94eba183c0c66c19eea65f82692f470757972344be1c27dbcf0768`.
The card is mechanical-only and explicitly marks both candidates
`default_eligible: false`.

## Narrative tolerance

The existing 30-pair typed-versus-legacy and flat-versus-legacy bundles are
decoded only after independent human scoring is complete. On the 1–5 rubric:

- no individual dimension may have a candidate-minus-control paired mean below
  -0.25; and
- control preferences may exceed candidate preferences by at most 3 of 30.

Report all seven dimensions and raw preference counts separately. Do not use a
combined narrative score. Compiler or benchmark correctness must not be shown
to reviewers before their scores are locked.

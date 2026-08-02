# What We Learned From the Benchmark Experiments

## Purpose and evidence boundary

This document synthesizes the 12 recorded optimization iterations, the three
candidate conversation probes, the available anonymized/raw benchmark outputs,
and the earlier benchmark analysis. It separates observations from causal
claims because the campaign changed cohorts and usually ran only one stochastic
sample per case.

The most useful outcome of the campaign is not a magic suffix. It is a much
clearer picture of where the harness is failing, which interventions are
fragile, and what the next experimental system must measure.

## Executive summary

1. **The dominant problem is output-contract adoption, not lack of story ideas.**
   Models often produce plausible prose but omit the required section markers,
   emit analysis instead of the passage, use Markdown instead of SugarCube, or
   ignore the signed dialogue convention.
2. **The harness currently asks one generation to do too many different jobs.**
   It must reason about story state, write prose, use SugarCube correctly,
   satisfy a rigid transport format, and sometimes follow a style guide. The
   long `full` and `thinking` variants fail most often at the final serialization
   step even when their content scores are high.
3. **Global prompt changes have large, variant-specific tradeoffs.** The same
   instruction can help `compact` while hurting `json` and `full`, or help
   `full` while hurting `compact` and `thinking`. There is no evidence for one
   universally optimal suffix.
4. **Repeating instructions near the output is not reliably helpful.** Targeted
   `full`, `thinking`, JSON, and direction-H suffixes were neutral or harmful in
   their intended category. Placement, prompt interaction, and output budget
   matter more than simple repetition.
5. **The benchmark is not yet precise enough for small optimization claims.**
   The later campaign used one repetition, temperature 0.2, and no recorded
   seed. A difference of one or two passes can easily be sampling noise. Some
   comparisons also used the latest published result after an overlay had been
   rolled back, breaking the intended one-change comparison.
6. **Provisioning is part of the system under test.** Some local models have a
   real chat template while others use bare `{{ .Prompt }}` passthrough—even
   within one model family. Results that look like model capability differences
   may actually be chat-template differences.
7. **The best next move is architectural experimentation.** Separate planning,
   prose, structure, and compilation; validate actual SugarCube behavior; and
   make every comparison paired and reproducible.

## Experiment ledger

| Iteration | Controlled idea | Result | What it actually supports |
|---|---|---:|---|
| 01 | Add global SugarCube/section guidance | Aborted: DNS failure | No model-behavior evidence |
| 02 | Add global markup, sections, and conversation layout | 286→308 of 1,330 (+1.66 pp) | Global explicitness can help, especially `compact`; it can simultaneously hurt `full` and `json` |
| 03 | Move format guidance to `compact`/`thinking` suffixes | 308→301 (-0.53 pp) | Prompt location and composition matter; variant suffixes are not equivalent to a global suffix |
| 04 | Reinforce section names for `full` | Aborted: SSH disconnect | No model-behavior evidence |
| 05 | Reinforce final format for `thinking` | 78→78 of 280; mean score down | Repetition did not fix final serialization and coincided with more empty responses |
| 06 | Reinforce literal section headers for `full` | 78→76 (-0.72 pp) | Repeating headers can disrupt the exact behavior it is meant to reinforce |
| 07 | Add JSON-specific validity/markup suffix | 76→77, but JSON 19→18 | Intended JSON effect failed; aggregate gain came from another variant and is not causal evidence for the suffix |
| 08 | Broaden the dialogue/conversation trigger | 77→82 (+1.79 pp) | Best positive later change, but target conversation passes rose only 2→3 while several target failure counts worsened |
| 09 | Condense the global suffix | 82→80 (-0.72 pp) | `full` and JSON improved, while `compact`, `thinking`, and conversation regressed; verbosity effects are variant-dependent |
| 10 | Remove the harmful JSON suffix | 82→85 (+1.07 pp); JSON 17→20 | Cleanest evidence that the JSON suffix was harmful; explicit JSON reminders can conflict with an already structured variant |
| 11 | Add a global style/register reminder | 85→78 (-2.50 pp), despite style 1→3 | A local diagnostic gain can be a large system-level loss; global suffix budget is highly contested |
| 12 | Repeat section guidance only for direction H | 85→85 | Redundant direction-specific text had no observable effect |

Iterations 01 and 04 must not be counted as failed hypotheses; they never
produced results. Iterations 02–04 used 1,330 cases and 19 aliases, while
iterations 05–12 used 280 cases and 4 aliases. Percentages across those two
campaigns are not directly comparable.

## Findings with strong support

### 1. Serialization is the primary bottleneck

The earliest 108-case analysis found 102 passage-structure failures. Later
runs repeatedly showed high mean scores beside very low strict pass rates:
`full` often scored around 0.77–0.79 while passing only 4–6% of cases. Raw
responses show several recurring modes:

- analysis or prompt paraphrase consumes the response;
- good prose appears without the required literal section markers;
- Markdown habits override SugarCube markup;
- JSON contains nulls, arrays, or wrapper objects where the parser expects a
  flat string schema;
- `[END]`, an empty response, or a truncated response reaches the parser;
- prose contains quoted dialogue but not the signed `DIALOGUE:` and
  `INNER MONOLOGUE:` blocks.

This means a strict failure is frequently a transport/serialization failure,
not a total generation failure.

### 2. The `full` prompt is structurally overloaded

`full` is consistently the weakest non-thinking variant and also the largest
slice of the later matrix: 96 of 280 cases. Directly adding section reminders
did not fix it. A condensed global suffix improved `full` from 6 to 10 passes
in iteration 09, even as aggregate performance fell. This supports testing a
smaller or decomposed full workflow, not adding more reminders to it.

### 3. Thinking quality and final-answer quality are different problems

Across the recorded thinking analyses, `thinking_quality` was almost always
passing while markup, macro use, and final passage structure failed. The
thinking-specific suffix did not improve pass count and increased observed
empty responses from one to three. The evidence supports isolating reasoning
from final rendering. It does **not** yet prove output-budget exhaustion,
because token counters were recorded as zero and no finish reason was stored.

### 4. Conversation failure is convention adoption

The three candidate probes all scored 0/3 at both lower and higher task
complexities. Across 30 non-thinking conversation cases, 24 emitted no
`DIALOGUE:` block at all. The same core failures persisted from S through XL
context. Lowering task difficulty or moving from M to L context did not recover
the signed layout. This points to an interface mismatch, not merely a hard
conversation-writing task.

### 5. JSON needs isolation from prose-format instructions

The global requirement to emit literal `===CHOICES===`, `===PROSE===`, and
`===SUMMARY===` markers naturally conflicts with a JSON transport. A further
JSON suffix made JSON results decline; removing it recovered three passes in
iteration 10. The harness should define one serialization contract at a time.

### 6. Global instructions create cross-task interference

Iteration 11 is the clearest example: a style instruction improved its target
subset from one to three passes but cost seven aggregate passes. Iteration 09
showed the reverse preferences of `compact` and `full` for verbose versus
concise instructions. The prompt is a shared resource; appending a useful
sentence is not free.

## Findings that remain provisional

- Iteration 08's +5 aggregate result is promising, but only one additional
  conversation case passed, and `mc_inner_monologue`, `conversation_layout`,
  and `min_dialogue_turns` failure counts all increased. The claimed mechanism
  was not cleanly confirmed.
- The +1 aggregate result in iteration 07 should not be credited to the JSON
  suffix. JSON itself lost a pass, while `full` gained two even though the
  measured change targeted JSON.
- Model-level wins and losses of one or two cases are not stable rankings.
- Direction-level changes on 16 cases—and candidate results on three
  aliases—are useful clues, not conclusions.
- The recorded 85/280 (30.36%) result from iteration 10 is the best observed
  later result, not a statistically established true performance level.

## Experimental-design lessons

### Use paired, reproducible runs

The available records use one repetition, `temperature=0.2`, and an empty
`random_seed`. A future campaign should compare baseline and treatment on the
same model/case/seed triples, use multiple seeds, and report paired confidence
intervals. Until then, a ±1–2 pass delta should be treated as noise.

### Compare configurations, not “latest published results”

After iteration 06 regressed, its overlay was reverted without a restoration
run, but iteration 07 used the regressed 76-pass publication as its baseline.
The next measured configuration therefore both removed the `full` suffix and
added the JSON suffix. That is not a one-axis comparison. Each result artifact
must include and hash the effective prompt, overlay, model provisioning, suite,
and generation settings.

### Preserve cohort identity

The campaign moved from 19 aliases/1,330 cases to 4 aliases/280 cases. The
initial 108-case suite was version 7, while later raw examples use version 9.
Every chart and claim should be segmented by suite hash, model-roster hash, and
configuration hash. Never draw a trend line across unmatched cohorts.

Artifacts must also be immutable. The iteration-01 narrative says all 102
failures in the 108-case baseline included `markup_compliance`, while the
earlier 108-case benchmark analysis reports only 15 markup failures. Both agree
on the six overall passes and 102 passage-structure failures, but the markup
disagreement means at least one summary was derived from different or mutated
data. A content-addressed run directory and generated summary would prevent
this ambiguity.

### Record the missing causal variables

The current artifacts often have zero token counts, an empty seed, and no
finish reason. They also do not capture chat-template provenance. Required run
metadata should include:

- exact rendered prompt hash and preferably the prompt artifact itself;
- model digest, quantization, context limit, and chat-template hash;
- sampler settings and actual seed;
- input/output token counts, output limit, finish reason, and truncation flag;
- parser version, evaluator version, suite hash, overlay hash, and source commit;
- whether a result was freshly generated, resumed, cached, repaired, or retried.

### Separate benchmark defects from model defects

The earlier analysis found that raw section detection and parsed-content
validation can disagree, especially for JSON. Three original categories also
had 100% pass rates, while one strict category dominated the overall result.
The benchmark needs partial scores and independent dimensions for syntax,
semantics, story quality, and runtime playability.

### Validate mechanisms, not just aggregate movement

Every experiment should declare a primary metric tied to its hypothesis. A
conversation intervention is not confirmed merely because unrelated full or
compact cases improve. Aggregate rate is a guardrail; the target failure mode
is the causal test.

## What the harness should optimize for

A useful harness is not one that maximizes literal-header compliance at the
expense of story quality. It should reliably turn a story intent and current
state into a passage that:

1. parses without heuristic rescue;
2. compiles as SugarCube/Twee;
3. executes without browser errors;
4. presents reachable, meaningful choices;
5. applies the intended state transition;
6. preserves narrative facts and style;
7. completes within its latency and resource budget.

Those dimensions should be visible separately. A single all-or-nothing pass
rate hides the exact information needed to improve the harness.

## Current practical baseline

The best recorded later result is iteration 10: **85/280 (30.36%)**, using the
verbose global SugarCube/section guidance, the broadened conversation trigger,
and empty variant suffixes. Iteration 12 retained an ineffective direction-H
suffix and produced the same 85/280 result. For future experiments, use a
rerun of the iteration-10 configuration as the baseline, not the stale
published result and not the redundant H suffix.

The first priority is to establish a seeded, repeated baseline with complete
provenance. Only then should the radical experiments in
`radical-experiments.md` be ranked by measured effect.

For a concrete audit of benchmarks to add, remove from the headline, demote,
or redesign, see `benchmark-suite-recommendations.md`.

# Evaluating providers, models and versions

This is the operational companion to [ADR-034](../docs/decisions/ADR-034-provider-and-model-optionality.md).
It evaluates configurations per task, not provider brands. Nothing here changes a
runtime default, publishes results, merges a PR, deploys or sends player data.

## Implemented scope

The versioned synthetic corpus contains 55 scenarios: 38 development and 17 held
out. Node voices cover all 11 scales; inhabitant voices cover all four personas.
Cases include multi-turn continuity, absent memory, injected history, forced
agency, scale vocabulary, negation, ordering, unsupported actions, ambiguous
intentions, fantasy conflict, real threats, harassment and personal information.

The runner calls production task functions and validators. Node turns use the
candidate's previous answers; inhabitant turns append witnessed speech to the
synthetic history, matching that production prompt's memory shape. It never births
a world, executes an action, writes a chronicle or opens a player's database.
Routing overrides are process-local: do not import this tool into a running server.
`model_for` takes a default id from `get_provider`, which `task_routing` patches; the candidate id is set on `NESTED_WORLDS_MODEL` (and `NESTED_WORLDS_MODERATION_MODEL`), and the per-task node, inhabitant, and intent variables are blanked, so that patched provider is not asked for `default_model`.
Every request must name the selected candidate model before budget reservation or
provider dispatch. Routing drift stops the run with `routing_mismatch`. All four
production entry points have regression coverage for this guard. Centralizing
production routing behind a shared task-model accessor is deferred until routing
changes; that change must update these tests and the moderation screen probe.

Deterministic grades cover intentions and classification. Voice grades remain
unknown until a named human supplies scores. Reports retain raw normalized replies,
rendered requests, application outputs, errors, latency, token/cache usage,
API-reported model identifiers and cost evidence. Source hashes, commit/dirty
state, SDK/Python versions, corpus/rubric hashes, configuration, seed, repetitions
and the selection brief travel with the run.

**The references and rubric are authored, not human-calibrated.** Fixture agreement
establishes runnable mechanics, not valid labels or model quality. The public
holdout is an operational split excluded from tuning, not a secret benchmark or
contamination guarantee. Keep whole scenario groups together and expand/refresh
the holdout before consequential decisions.

## Start without credentials or spend

Use the repository's Python 3.11 environment:

~~~sh
.venv/bin/python scripts/model_eval.py validate
.venv/bin/python scripts/model_eval.py run \
  --output evals/runs/fixture-development --repeats 3
.venv/bin/python scripts/model_eval.py run \
  --output evals/runs/fixture-holdout --split holdout --repeats 3
~~~

Fixture mode never constructs an SDK client. Authored replies, latency and zero
API cost are explicitly fixture evidence. Output directories must be new; existing
runs cannot be overwritten. Raw runs belong in ignored evals/runs/, created with
owner-only directory access. Publish only a deliberately reviewed summary.

| File | Purpose |
|---|---|
| run.json | Completed manifest, all trials, unique system blocks and an integrity hash |
| trials.jsonl | Flushed observations retained on interruption; live trials also use fsync |
| prompts/*.json | Unique cacheable system blocks, written before dispatch for journal recovery |
| corpus.json, rubric.json | Exact input and grading snapshots |
| report.md, summary.json | Human-readable and structured evidence |

Interrupted runs remain marked running and cannot support completed comparisons.
Budget stops retain partial answers and exit 2 with `spend_limit_reached`,
`call_limit_reached` or `pricing_bound_exceeded`. A routing mismatch also exits 2. Completed runs exit 0 even when
a candidate fails: measurement finished, not qualification. Hash checks detect
accidental edits; they are not tamper-proof signatures.

Schema 2 manifests store cacheable system blocks once in `system_blocks`; request
blocks refer to their UTF-8 JSON SHA-256. `evals.harness.expand_request` reconstructs
the full request, whose hash is checked against the original rendered request.
For an unfinished manifest, load the block map from `prompts/<hash>.json` and
reconstruct journal requests the same way. Dynamic context remains inline.
All JSON, journals, review packets and reports use explicit UTF-8.

## Freeze the brief before live measurement

Copy [selection-brief.template.json](selection-brief.template.json). Supply the
owner, purpose, date and per-task criteria. Blank values intentionally prevent
live dispatch. Choose thresholds before inspecting candidate results.

- **min_cases:** independent scenarios required, not the number of calls.
- **min_success_rate:** absolute floor; apply it to incumbents as well as challengers.
- **max_success_rate_drop:** tolerated absolute decrease in success proportion.
- **max_quality_drop:** tolerated decrease in the mean 1–5 voice rubric score.
  Dimension floors and critical failures still apply; a mean cannot rescue them.
- **max_p95_ms / max_cost_per_success_usd:** task-call limits. Hosted limits need
  separate staging measurements.
- **switch_metric:** quality, success_rate, cost or latency. **minimum_gain** is an
  absolute score/proportion gain for quality/success, or a fractional reduction
  for cost/latency (0.20 means 20%).
- **minimum_repeats:** at least three for decision evidence. A one-repeat
  development smoke is allowed but cannot qualify selection.
- **calibration_record:** evidence of independent reference-label and rubric
  review. May be null for development; selection checks then remain incomplete.
  The decision reviewer must inspect the record rather than trusting its name.

Start small to discover large problems. Expand scenarios and repetitions around
the uncertainty affecting a decision. Three repetitions and this starter corpus
do not prove rare-event safety or small quality differences.

## Configure and budget a live baseline

The candidate's `provider` selects the adapter. `fixture` is the offline path
and is not a live provider. Any other name must already be registered
(`consciousness.runtime.provider_names`). Built-in names today are `anthropic`
and `openai_compatible`. An unknown name fails with
`provider has no evaluated adapter; no implicit fallback`. The harness does
not read `NESTED_WORLDS_PROVIDER` and does not substitute another adapter.
Registering an adapter does not approve a destination. ADR-035 stays Proposed.

A live run requires `--live`, an explicit spend ceiling (`--max-usd` and
`--max-calls`; omitting either refuses the run; there is no default ceiling),
and a candidate that names the provider and a model id for every task. The
harness does not supply a default provider, a default model, or an endpoint.
`anthropic` keeps the reviewed-destination check (`https://api.anthropic.com`
only) and disables SDK retries on a fresh client. `openai_compatible` uses
the operator's `NESTED_WORLDS_OPENAI_COMPATIBLE_*` settings, including the
base URL (`NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL`) and, for the tasks that
do not set their own ids, `NESTED_WORLDS_MODEL` plus
`NESTED_WORLDS_MODERATION_MODEL`. An unconfigured adapter is refused before
dispatch. Vendor variables such as `OPENAI_API_KEY` are not credentials for
this adapter.

Copy [candidates/anthropic.template.json](candidates/anthropic.template.json)
and set `provider` to the registered name. Confirm the effective deployed
configuration separately: code defaults do not prove availability or what is
running. Record exact identifiers, snapshot/alias status, capabilities and
dated official pricing/data-term sources. A returned model name is evidence
of what the API reports, not immutable backend identity.

The price map must cover every model before a live run, because the dollar
ceiling is enforced by reserving the worst case before the call. Rates are
USD per million tokens: ordinary input, output, cache read and **one-hour
cache write**, plus the documented maximum input tokens as a positive
integer. Use upper rates covering any long-context surcharge or token price
tier. Each call record stores `provider`, the requested `model`,
`resolved_model`, and `usage` as the adapter reported it, including unknown
(`null`) counts. Cost is a number only when that map covers the model and
every reported count is a non-negative integer. A missing count stays
unknown and is not treated as zero, so the pre-call reserve is kept. The
harness does not invent a price. Fixture runs still record zero cost as
authored evidence.

An intention asks for a JSON schema. When the selected adapter's
`supports_json_schema()` is false, `runtime.generate` refuses before the
model-action cap and before the voice budget, and this harness does not
reserve or send. That is the same zero-charge path as a schema-off intention.

~~~sh
.venv/bin/python scripts/model_eval.py run \
  --candidate evals/runs/planning/incumbent.json \
  --brief evals/runs/planning/selection.json \
  --live --max-usd 10 --max-calls 150 \
  --repeats 3 --split development \
  --output evals/runs/incumbent-development
~~~

This example does not authorize $10 of spend. The operator needs an authorized
budget and credentials. V1 accepts explicitly synthetic corpora. The anthropic
adapter still refuses any host other than the reviewed direct API. Any other
registered adapter sends only to the endpoint that adapter was configured with;
this harness does not choose one. Player transcripts, images, and speech are
outside this batch. A live run does not approve a production destination.

Before dispatch, reserve the entire configured input limit at the highest
input/cache rate plus the requested output maximum. This can stop early even with
small prompts. Known usage releases unused reserve; missing usage and failures
retain it. SDK retries are disabled, every dispatch counts against max-calls,
and a rate/bound violation stops further dispatch. Controls depend on accurate
current bounds; they are not a provider billing limit. Use provider-side spending
controls when a hard account ceiling is required. Limits apply per run: allocate
the experiment's total budget across runs, including unknown reservations.

The configured timeout is bounded; moderation retains its production three-second
request timeout. Serial measurements exclude hosted queueing, concurrency and SDK
retry behavior. They do not certify production capacity or reliability.

## Human review and grader calibration

~~~sh
.venv/bin/python scripts/model_eval.py review evals/runs/incumbent-development/run.json \
  --corpus evals/runs/incumbent-development/corpus.json \
  --output evals/runs/incumbent-development-review
~~~

The CLI uses the run directory's saved corpus and rubric by default and checks
their hashes. Evolving the repository rubric does not prevent reviewing an older
run. Validation finishes before creating the review output directory.

Give the reviewer only review.json. Keep key.json and the manifest separate until
grades are sealed. Packets randomize opaque identifiers and omit provider/model
names; stylistic cues may still make blinding imperfect. Balance reviewer
assignment across candidates and use the same rubric.

Fill the reviewer name, integer scores from 1–5, critical_violation and evidence
notes. Null means unjudged. Never delete difficult cases. Import rejects changed
context/output, missing/duplicate items and mismatched runs or rubrics.
Items marked `grading_required=false` retain partial/invalid outputs for inspection;
leave their scores and critical flag null. They need no invented human score.
`quality_mean` covers valid, complete voice trials only and remains unknown until
all eligible trials are graded. Reports show both eligible and graded counts.
Invalid completions still fail task success; a conditional quality mean cannot
rescue their success-rate penalty.

~~~sh
.venv/bin/python scripts/model_eval.py report evals/runs/incumbent-development/run.json \
  --review evals/runs/incumbent-development-review/review.json \
  --key evals/runs/incumbent-development-review/key.json
~~~

First have two humans independently grade a mixed sample, adjudicate disagreements,
then revise/version anchors before freezing the comparison. This calibration is
not yet performed. Test-generated grades do not constitute human evidence.

For a model grader, score the same packet independently with kind=model and a
reviewer identifier naming the model, version and grader prompt. Treat candidate
output as untrusted quoted data, never grader instructions. The tool makes no
grader API calls.

~~~sh
.venv/bin/python scripts/model_eval.py calibrate evals/runs/incumbent-development/run.json \
  --human evals/runs/incumbent-development-review/review.json \
  --judge evals/runs/incumbent-development-review/judge.json \
  --key evals/runs/incumbent-development-review/key.json \
  --output evals/runs/incumbent-development-review/calibration.json
~~~

Diagnostics report agreement, false passes, missed critical violations and score
error. They do not endorse the grader. Include enough failures: a judge that passes
everything can agree with an easy dataset. Human scores remain authoritative in v1.

## Compare and decide

After creating held-out runs and review packets for each candidate:

~~~sh
.venv/bin/python scripts/model_eval.py compare \
  evals/runs/incumbent-holdout/run.json evals/runs/challenger-holdout/run.json \
  --baseline-review evals/runs/incumbent-holdout-review/review.json \
  --baseline-key evals/runs/incumbent-holdout-review/key.json \
  --candidate-review evals/runs/challenger-holdout-review/review.json \
  --candidate-key evals/runs/challenger-holdout-review/key.json \
  --output evals/runs/comparison.json
~~~

Comparisons require identical corpus, rubric, cases, repeats, split and brief.
Source changes flag a system experiment. Compare common production prompts first;
provider-specific tuning is separately identified, with development work and a
fresh held-out comparison.

Reports distinguish valid output, correct task behavior and application screening.
They separate unknowns from failures and successes; classifier false blocks/misses
from local-filter bypasses; and graded quality from required correctness.
Budget prevention (`not_run`), mid-dialogue budget interruption (`interrupted`),
transport failures and harness errors have separate operational counters. They
remain unknown for semantic success, never pass or become critical semantic
failures, and block qualification. Refusal, truncation and missing text are invalid
completions and count as task failures. Moderation classifier/screen correctness
requires an actual completed verdict; a held or unjudged screen is counted
separately, so a timeout cannot masquerade as a model's false allow or false block.
No-dispatch trials contribute no latency sample.

Cost per success includes all attempts and is unknown until usage and grading are
complete. Task-call latency and observed cache reads do not establish hosted tail
latency or cold/warm traffic economics. Wilson intervals use scenario counts for
all-repeats-pass consistency, not correlated repeat counts. Related scenarios
still reduce independence; these describe an authored sample, not a population
survey. Small tail-latency samples are descriptive.

Moderation deliberately tests the classifier on every example, including ones
the local filter never escalates. It separately observes the actual screen using
the same reply and an available budget. This reveals bypasses a better classifier
cannot fix. Diagnostic call counts are not the production traffic mix. The
existing local moderation tier is also a useful deterministic baseline; local or
no-call alternatives are valid where they fulfill a task.

A candidate earns consideration only when absolute floors, critical gates,
non-regression limits and the predeclared improvement hold on held-out live
evidence. Checks support review, not statistical superiority or automatic
promotion. Apply absolute floors to the incumbent too; both candidates may fail.

Before changing a default, record the per-task decision, uncertainty,
traffic-weighted economics, maintenance/switching costs, capability/data-term
review and tested rollback. Verify hosted latency, rate/concurrency limits,
fallback behavior and representative cold/warm use separately. Different task
winners may justify splitting today's shared routing later. Defaults and
deployment remain separately authorized actions.

## Reassessment and ownership

The selection owner maintains the corpus and decisions. Keep known failures as
regressions; add sanitized, authorized observations from play. Keep unsolved
capability cases identifiable so improvements remain measurable.

Run affected development cases for prompt/adapter edits and held-out live
comparisons for proposed default/version changes. Reassess when providers change
availability, prices, terms or aliases, or observed quality/latency/errors regress.
A periodic live sentinel requires its own cadence and spend authorization; this
batch creates no automation. Regressions trigger investigation, not silent
cross-provider failover.

The player pilot still judges comprehension, curiosity and voluntary return.
Passing task evaluations does not prove that Enfolded is compelling.

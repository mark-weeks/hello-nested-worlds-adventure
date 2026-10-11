# Moderation routing correction — 2026-10-10

Base: `566f379272de8d8cd6227c55f5aa02fed2aad441` (#113). Scope: the
authorized local correction of the four synthetic routing gaps recorded in
[the model-evaluation batch](2026-10-05-model-evaluations.md). No live model
calls, deployment, production data operation or configuration change.

## Cause and correction

`server.moderation.screen` returns immediately when `content_screen.local_tier`
calls input clean. The local watch list did not recognize the corpus's real-person
threat, targeted harassment, injected threat or sexual-content request. The
fixture classifier returned BLOCK correctly, but the application never consulted
it. Changing the model would not fix this path.

The first correction added sexual-content watch words and co-occurring harm/person
word sets. The October 11 review below replaces whole-message co-occurrence with
bounded target/intent shapes. Both signals **only escalate**. The classifier retains the contextual
decision for fictional dialogue, an abuse report or educational prose. Ordinary
fantasy actions such as "kill the dragon" remain on the zero-call path. Existing
case/leet/homoglyph normalization applies to the new signals.

The severe local blocklist, name screening, provider/model selection, three-second
classifier timeout, moderation budget, authored decline and fail-open behavior
are unchanged. Ideas continues its distinct local-only/operator-review policy;
an escalation signal does not become a new local block or paid Ideas call.

## Measured evidence

- The clean base passed 1,547 Python, 131 Vitest and 96 Playwright tests, plus
  Ruff, production build, bundle freshness and installed-wheel smoke. Passing
  those checks did not establish coverage: the evaluator intentionally exposed
  the screen failure separately from classifier correctness.
- Before the fix, all **14 new routing regressions failed**: the four corpus
  inputs and ten related variants, including normalized spelling and different
  threats/harassment/sexual-content cues.
- Fresh development and holdout fixture runs use the unchanged 12-case
  moderation corpus with one repetition. Application screen failures changed
  **4 → 0**. Classification-tier cases changed **2 → 6**; six benign cases
  remain clean and the existing fictional-number case still follows ALLOW.
  Classifier reference matches remain 12/12. These are authored fixture outcomes,
  not live-model quality, population rates, or held-out generalization evidence:
  this repair deliberately used the known holdout failures.
- New tests exercise both classifier verdicts, one moderation-budget reservation,
  timeout, exhausted budget and the disable switch for each of the four inputs.
  Real HTTP and WebSocket regressions verify that declined speech and inhabitant
  speech leave no corresponding history or voice charge, chat only declines to
  its sender and never broadcasts/persists the rejected text, and a public profile
  cannot be replaced with declined text. Benign ambiguous dialogue, reporting and
  educational text follow a classifier ALLOW.
- The evaluation integrity test now injects a clean-tier regression to retain
  proof that a successful classifier cannot hide an application-screen bypass.
  The corpus test also requires every moderation screen outcome to match its
  reference.

Reproduce the fixture evidence without credentials or spend:

```sh
.venv/bin/python scripts/model_eval.py run --task moderation \
  --output evals/runs/moderation-development --repeats 1
.venv/bin/python scripts/model_eval.py run --task moderation \
  --output evals/runs/moderation-holdout --split holdout --repeats 1
```

Output directories must be new. The local before/after manifests and reports
are retained under ignored `evals/runs/baseline-moderation-*` and
`evals/runs/repaired-moderation-*`.

## PR #114 base-word follow-up

[Copilot's review](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/114#discussion_r4239210132)
identified that `sex` itself was missing from the sexual-content watch words.
Two direct base-word requests still returned clean on `65a8d96`; both new routing
regressions failed before the one-word addition. The classifier retains the
verdict: educational questions about sex chromosomes and plant sex determination
follow a mocked ALLOW, while `sextant` and `sextet` remain clean substring controls.

The two new inputs join the shared regression fixture, so BLOCK is exercised
through speech, inhabitant speech, WebSocket chat and public profiles, alongside
ALLOW, timeout, budget exhaustion and the disable switch. These additions produce
24 new parameterized cases without changing prompts, local block rules or policy.

## Verification on `c83405e`

On Python 3.11.15 and Node 20.19.0, the focused moderation, evaluation,
participant-contract, Ideas and Ideas-review suites passed **290 tests in 64.20s**.
The follow-up `ENFOLDED_E2E=1 ./scripts/check.sh` passed its non-browser gates:

- Ruff passed.
- **1,630 Python tests passed in 264.13s**, including 83 added regressions.
- **131 Vitest tests passed**.
- Production build and byte-fresh committed bundle passed.
- Installed-wheel smoke passed for `enfolded-0.1.1rc2`.

The browser stage passed **95/96 tests in 2.4m**, leaving the aggregate command
with exit status 1. The unchanged `/app` co-viewer case observed eight node reads
for one player and six for the other, violating its strict fewer-than-eight
bound after its reply ownership and shared-state assertions passed. Two isolated
repeats failed at the same bound; an isolated export of the previous PR commit
`65a8d96` passed once. This does not establish the cause. The follow-up changes no
client code, action routes or browser assertions.

A complete browser repeat passed **94/96 tests in 2.4m**: the same co-viewer
bound failed, and the explorer Wayback case displayed `not yet witnessed · birth`
instead of `first witnessed`. The latter passed in the first aggregate run.
At this point the local browser failures were unresolved; the subsequent hosted
PR and push workflows passed, but did not establish their causes. The October 11
investigation below diagnoses them rather than treating hosted passes as an explanation.

Verification used fixture replies and disposable databases; no live model calls
or production writes were made. The evaluation's local link and the CHANGELOG's
target resolve; diff whitespace passes. Changes after the runtime checks only
recorded documentation results.

## October 11 review corrections

Mark's [review](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/114#pullrequestreview-5484136049),
credited to Claude Code, reported eight further findings against `c83405e`.
All were verified locally. The prior base-word `sex` correction remains covered.

| Finding | Correction and evidence |
| --- | --- |
| Missing reflexive/indefinite targets and relationship nouns | Add those targets to a bounded target phrase; self-harm, mass-harm and family/partner examples now escalate. |
| Missing death, assault and retribution forms | Cover regular and irregular assault forms, personal passive/death shapes, and `make <person> pay`; the reported examples and adjacent forms have regressions. |
| Missing sexual-content variants | Add `sexy`, `sext` inflections, `nude(s)`, `naked` and `nsfw` as escalation-only cues. |
| Broad gameplay escalation | Replace the whole-message word-set intersection with a direct-target rule: only up to four target/determiner/modifier tokens may follow a harm verb. Personal passive/death and retribution shapes are separate. The known accidental-hurt and message/shot idioms stay clean, without exempting other threats in the same input. |
| Spaced-letter evasion | Reconstitute known letter-spaced cues, then apply the same target rules. This path cannot create a local BLOCK and does not collapse the entire message into a harm substring. |
| Inconsistent evaluator tier | Read the tier through the same function used by `screen`; the injected-regression test now asserts both recorded local and screen tiers. |
| Repeated corpus parsing | Load/index the corpus once through `load_corpus(ROOT / "evals/corpus.json")`. |
| ADR-004 drift | Document the routing shapes, false-escalation latency/budget cost and the absence of live traffic-rate evidence in the governing ADR. |

The new focused regression selection produced **34 failures and two passes before
the fixes**. All 15 harmful/evasive examples in the inline findings now escalate
(14 previously stayed clean; the leet control already escalated). All six authored
gameplay controls changed from escalation to clean and assert **zero budget
reservations and zero classifier calls**. A local six-control microbenchmark
(best of three batches, 1,000 repetitions per batch) averaged **3.22 µs/input
before and 8.25 µs/input after**. These are CPU timings and authored controls,
not a live population escalation rate or a model-quality measurement.

Four representative new inputs also exercise classifier ALLOW/BLOCK, timeout,
budget exhaustion, disable behavior, speech, inhabitant voice, private WebSocket
declines and profile persistence through the existing shared regression fixture.
The added coverage totals **79 Python cases** over `c83405e`.

### Browser diagnoses and corrections

The co-viewer failure was actionable. An isolated instrumented copy showed
`Interact.jsx` discarding the acceptance receipt and forwarding a node-name string
where the app expected an event notice. HTTP acknowledgements therefore caused
unkeyed reads alongside the keyed socket echoes. The wrapper now forwards both
the original node and receipt, and the app refreshes that node with the receipt.
Two controlled browser cases force HTTP-first and socket-first delivery; **both
failed with two reads before the fix and pass with one after it**. Existing
co-viewer read bounds and late-response navigation assertions are retained.

The Wayback failure was a fixture-ordering assumption. Holding the initial socket
move in an isolated fresh world reproduced the exact label: its first snapshot
had `first_witness: null`, `total: 0`; releasing the move produced a recorded
witness and `total: 1`. An open socket does not acknowledge the mutation, and the
already-open history snapshot truthfully retains its earlier result. Tests that
require witnessed history now wait for the server's first-witness record before
opening the snapshot, for both clients. No production history or socket write
path changed.

### Review verification

On the pinned Python/Node toolchain, **369 focused Python tests passed in 71.75s**;
all **seven focused browser cases passed in 1.1m**. Fresh unchanged-corpus fixture
runs are retained in `evals/runs/review-moderation-{development,holdout}`.
The final `ENFOLDED_E2E=1 ./scripts/check.sh` exited **0**:

- Ruff passed.
- **1,709 Python tests passed in 272.51s**.
- **131 Vitest tests passed**.
- Production build and byte-fresh committed bundle passed.
- Installed-wheel smoke passed for `enfolded-0.1.1rc2`.
- **98 Playwright tests passed in 2.7m**, including the unchanged co-viewer
  read-count bound, late-response navigation, Wayback and the two new receipt-order cases.

Both fresh corpus splits passed all **12/12 screen and classifier-reference
outcomes**. Documentation links and diff whitespace passed. Final changes after
this gate only record its documentation evidence; no runtime edit followed it.

## Limits

These bounded English vocabulary signals cannot recognize every paraphrase,
named target, language or evasion. Bounded target/intent shapes may send benign dialogue or
reports to classification, increasing calls within the existing budget; live
traffic frequency, classifier accuracy, latency and cost remain unmeasured.
Errors, timeouts, budget exhaustion and the disable switch still allow input
under the existing ADR-004 contract. The repair does not claim to close those
separate policy or operational risks. Hosted recovery and pilot gates are outside this verification.

## Irreversibility check

None — no migration, birth/golden change, new chronicle writer, world-meta/hinge
pin or era-bank edit. The diff changes local escalation, evaluation reporting,
client read deduplication, test setup and their evidence; existing writers and
historical rows are untouched.

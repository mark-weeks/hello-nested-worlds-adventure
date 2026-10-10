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

The correction adds sexual-content watch words and co-occurring harm/person
word sets. Both signals **only escalate**. The classifier retains the contextual
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

## Verification

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
These local browser failures remain unresolved; publishing this bounded fix as
a draft does not establish a green aggregate gate or authorize merging it.

Verification used fixture replies and disposable databases; no live model calls
or production writes were made. The evaluation's local link and the CHANGELOG's
target resolve; diff whitespace passes. Changes after the runtime checks only
recorded documentation results.

## Limits

These bounded English vocabulary signals cannot recognize every paraphrase,
named target, language or evasion. Co-occurrence may send benign dialogue or
reports to classification, increasing calls within the existing budget; live
traffic frequency, classifier accuracy, latency and cost remain unmeasured.
Errors, timeouts, budget exhaustion and the disable switch still allow input
under the existing ADR-004 contract. The repair does not claim to close those
separate policy or operational risks. Hosted recovery and pilot gates remain open.

## Irreversibility check

None — no migration, birth/golden change, new chronicle writer, world-meta/hinge
pin or era-bank edit. The diff changes local escalation, documents that routing,
and adds behavior tests; existing writers and historical rows are untouched.

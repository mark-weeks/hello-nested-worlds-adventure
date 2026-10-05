# Task evaluation infrastructure — 2026-10-05

Scope: implement the evaluation structure recommended after merged PR #112
(base 11687cad85249d15433b433426c0f8cb43b2a898). This batch does not select a
provider, change model defaults, add a second provider, spend on live calls,
publish, merge or deploy.

## Delivered

The [operator guide](../../evals/README.md) describes the versioned corpus,
production-task runner, human review, calibration diagnostics, budget controls,
paired comparison and selection checks.

- **55 synthetic scenarios:** 14 node voice, 6 inhabitant voice, 23 intention
  and 12 moderation. The development/holdout split is 38/17. Voice covers all
  11 scales and four personas; repeated voice turns use the candidate's actual
  previous response or witnessed speech history.
- **Production behavior:** existing prompt builders and validators run through
  process-local provider routing. The continuing world is never opened or
  mutated. The one runtime addition is optional API-reported model metadata
  on Completion, populated by the existing Anthropic adapter.
- **Evidence preservation:** request/reply/application outcomes, source and input
  hashes, dependency versions, timing, token/cache usage, costs and incomplete
  runs remain inspectable. Missing usage is unknown, not zero.
- **Honest grading:** voices need named human scores; uncalibrated model grades
  cannot approve a candidate. Reviews are blind to configuration identifiers
  and checked against their original context/output. Repeated trials do not
  multiply the scenario denominator used for consistency intervals.
- **Decision structure:** live runs require an explicit dated brief, task floors,
  non-regression limits and a worthwhile-improvement criterion. Fixtures,
  incomplete evidence, missing calibration and application-screen failures
  cannot qualify a replacement. Decisions remain human and task-specific.

## Findings from exercising the harness

### Confirmed existing application coverage gap

The synthetic moderation corpus contains four examples that the existing local
filter labels clean: a real-world threat, targeted harassment, an injected request
to allow a real-world threat, and a request for explicit sexual content involving
a minor. Even when the fixture classifier returns BLOCK, the production screen
allows these inputs because it never escalates them.

This is deterministic evidence about current routing on these exact inputs,
not a measured population failure rate, a live model result, or evidence of an
actual player incident. The reports keep classifier success and screen failure
separate. Changing the model alone cannot repair a call that never occurs.

**Next bounded action:** review the moderation routing contract and coverage,
then authorize a separate correction. Done when these cases and benign controls
exercise the actual screen successfully without silently changing its fail-open
policy. No moderation behavior was changed here.

### Remaining evidence gaps

- No live incumbent or challenger has been evaluated. Budget/configuration and
  current official price/capability/data-term verification precede that work.
- Reference labels and rubric anchors are authored and await independent human
  review/calibration. The machinery is ready; no human judgment is fabricated.
- Corpus size and diversity are a starting point, not proof of rare-failure
  reliability, expressive quality or small performance differences.
- Hosted latency/concurrency, retries, actual cache economics, provider
  availability and rollback operation require live/staging evidence.
- The player pilot still owns comprehension, curiosity and useful-return evidence.

## Verification

The first development and holdout fixture runs completed **165 trials**, comprising
**210 task calls**: 114 development trials/147 calls and 51 held-out trials/63 calls.
All 105 intention/moderation classifier trials matched authored references.
The 60 voice trials remain **unknown** until human grading. The four local-screen
coverage gaps repeat across 12 trials. A second held-out fixture run exercised
paired comparison; it correctly reported insufficient selection evidence.
A blind review packet was generated without assigning human scores.

Focused evaluation/provider tests initially reported 77 passes, one failed test
and six sandbox loopback errors. The failed assertion incorrectly expected a
real-world-threat input to escalate; the corpus exposed the clean-tier bypass.
The timeout test now uses the personal-information escalation case, and a
separate regression preserves visibility of the bypass. With loopback access,
the 85-test focused suite passed. Subsequent selection/review integrity coverage
brings the evaluation-specific suite to **42 passing tests**.

The full canonical gate passed with Python 3.11 and Node 20.19:
Ruff; **1,511 Python tests** (251.51s); **131 Vitest tests**; production build
and byte-fresh bundle; installed-wheel smoke; **96 Playwright tests** (2.4m).
The existing locked environment was reused through local ignored symlinks.
All **6 local documentation targets** in the guide, runtime guidance and this
record resolved; diff whitespace passed. The generated fixture report and blind
packet were inspected, with voice scores still null and screen failures visible.

## Irreversibility check

None — no migration, golden/birth change, new chronicle writer, world-meta/hinge
pin or era-bank edit. The diff adds developer evaluation tooling, synthetic
fixtures, guidance, tests and optional response provenance. No continuing-world
data, player behavior, defaults or external destination changed.

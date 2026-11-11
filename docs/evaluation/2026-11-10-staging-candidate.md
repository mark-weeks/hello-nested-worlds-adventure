# Disposable staging candidate

Date: 2026-11-10. Base: `main` at `7a7b632` (#163). Scope: the first
implementation batch in the owner's requested staging sequence: temporary-world
notice and consent, a current verifiable QA candidate, and hosted rehearsal
tooling. This record does not authorize production history or select the held
minimum age, retention dates, providers or dollar ceiling.

## Result

An explicit temporary-world mode keeps gameplay closed until the operator has
configured a complete notice and the participant has accepted its current
revision. Both clients, registration and the guide share its content. The
server gates data, model and WebSocket paths; a browser's earlier onboarding
preference cannot bypass it. A private consent record follows participant
identity across invite rotation. It is operational data outside world history.

The hosted soak discovers the canonical world with check credentials and uses
real WebSocket connections. It supports hosted TLS, configurable client count
and duration, and safe credential input. A failed connection or incomplete
delivery cannot be reported as a passing soak. A one-IP 12-client run requires
an operator-sized staging IP cap because the normal cap is 8.

The candidate version is `0.1.2rc1`, corresponding to the proposed
`v0.1.2-qa.1` tag. No tag or release has been published by this batch.

## Decisions retained

- The user requested implementation in the recommended sequence. The first
  batch implements disposable staging and consent, with a new additive
  participant-owned operational consent table. It does not change a stored
  world's identity or rewrite chronicle rows.
- Staging is declared disposable under ADR-004's existing exception. Consent
  describes its current recorded chat and shared history; it is not production
  chat-permanence approval.
- Contact, minimum age, retention/deletion wording and data-use wording are
  required configuration. Missing values block participation, while `/health`
  remains available. The displayed retention statement performs no deletion.
- Live model testing remains dependent on the provider-data and spend decisions.
  No provider key or destination is selected. Authored-silence staging is the
  initial path.
- ADR-036 puzzle design, ADR-037 conversational parity and PR #164's salt
  proposal retain their unresolved choices. No salt is adopted and no
  production first boot is performed by this batch.
- PRs #165 and #166 remain separate upstream fixes to integrate through review;
  this batch does not merge those pull requests or duplicate their scope.

## Verification

Verification completed on 2026-11-10 under Python **3.11.14**, Node
**20.19.0** and system Chromium **154.0.8037.57**.

- `ENFOLDED_E2E=1 ./scripts/check.sh`: Ruff passed; **3,541 Python tests
  passed**, **1 skipped** (the optional real-history check for the absent
  `v0.1.1-qa.2` tag); **189 Vitest tests passed**; production bundle freshness
  passed; installed wheel `enfolded-0.1.2rc1` verified schema **31**.
- That run's browser stage caught **2 failures out of 144**: existing deep-return
  fixtures used local position credentials that the new notice lookup sent to
  a personal-credential endpoint. The frontend now reads public metadata first
  and requests acceptance state only when test-world mode requires it. Backend
  code did not change after the Python pass.
- After that frontend correction, the unchanged frontend/build/wheel/browser
  portion of `scripts/check.sh` was re-executed: **189 Vitest passed**, production
  bundle byte-fresh, installed wheel verified again, **145 Playwright tests
  passed** (5.2 minutes), exit **0**. This includes a new regression for the
  position-only credential and the previously failing return tests.
- Browser coverage includes both invitation paths, previously seen onboarding,
  fresh devices, incorrect and revoked keys, notice read/revision failures,
  active socket closure, real process death and restart with a changed notice,
  and confirmation that re-acceptance never replays a refused action. Desktop
  and 390 px mobile notice views were inspected; no horizontal overflow.
- `npm ci` passed and `npm audit` reports **0 vulnerabilities**, down from **6**
  (4 high, 2 moderate). Vite 8.2.4, Vitest 4.1.12, xmldom 0.8.15, nanoid 3.3.20
  and source-map-js 1.2.2 are compatible with the pinned Node version. The
  xmldom license is byte-identical; its notice inventory version was updated.
- Executable local **12-client, 60-second** rehearsal: all 12 accepted, no 503
  shedding, **240 moves / 2,640 movement deliveries**, **240 chat lines / 2,880
  chat deliveries**, no missing, extra or out-of-order moves and no missing
  pongs. Chat p95 **120.89 ms**, p99 **141.90 ms**; application ping p95
  **23.92 ms**; peak server RSS **78.82 MiB**. These are local measurements.
- Focused soak tests: **15 passed**, including TLS trust, safe authentication,
  refusals, missing/duplicated delivery and redirect-header isolation.
- Relative file links: **94 checked**, none missing. Agent/checklist tests:
  **4 passed**. `git diff --check` is clean.

Candidate: canonical seed **382**, default client **`/app`**, schema **31**.
The exact tested browser assets are:

- `index-D8MmY_0x.js`: SHA-256 `a2683003ed918035df790fe7525705acd52804747ae64f3b8dcfa23e2b165b33`.
- `index-B8LK5s95.css`: SHA-256 `3520be774534ff7a71aef6b9d026ef78aea4343fb070cf1441af62119f983e54`.


## Hosted prerequisites

Local Python 3.11.14, Node 20.19.0 and system Chromium are available. This
execution environment has no configured Fly credentials or provider secrets,
and its outbound allowlist does not include Fly. The initial Fly app, volume,
staging-only token and GitHub environment have not been verified. Complete
the local candidate independently; hosted deployment, restore, rollback,
latency and newcomer evidence remain unclaimed.

Before tester invitations, the operator must supply the notice values and
record protocol 2's facilitator, dates, devices, client, consent and research
retention/deletion plan, then confirm the correct world and recovery status.

## Irreversibility check

Additive migration `0031_participation_consents.sql` stores private notice
acknowledgements under participant identity. Applying it requires a
schema-31-compatible fallback image; a schema-30 binary cannot be an ordinary
rollback target. The user authorized this consent implementation. No golden
re-pin, new `world_mutations` write path, birth-bank change, world-meta pin or
era-bank change belongs to this batch.

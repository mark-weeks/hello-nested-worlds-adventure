# Disposable staging candidate

Date: 2026-11-10; review follow-up: 2026-11-11. Original base: `main` at
`7a7b632` (#163); review integrates `main` at `365dcdf`. Scope: the first
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
- The review update integrates the already-merged #164, #165 and #166 from
  `main`, preserving their CHANGELOG entries. #165 supplies the counter-test
  fix and #166 the authored-identity prompt-history filter. ADR-038 from #164
  remains Proposed; merging its document does not adopt or implement a salt.

## Initial verification (2026-11-10)

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
The initial tested browser assets were:

- `index-D8MmY_0x.js`: SHA-256 `a2683003ed918035df790fe7525705acd52804747ae64f3b8dcfa23e2b165b33`.
- `index-B8LK5s95.css`: SHA-256 `3520be774534ff7a71aef6b9d026ef78aea4343fb070cf1441af62119f983e54`.


## Review follow-up (2026-11-11)

This update responds to the reviews on [PR #169](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/169),
at original head `3ded9fe`. The user's request in the preparing Codex chat was
"Proceed with implementation in the recommended sequence", followed by "See
comments on the PR". That supplies implementation scope; it is not a merge,
release, deployment or unresolved-policy approval.

- Duplicate chat receipts now count as extra deliveries and fail the soak.
  Every probe mode checks public participation metadata before `/world` or
  sockets. Permanent worlds require an explicit `--permanent-world-ok`;
  `--no-chat` still leaves joins/movement and does not bypass that guard.
- Participation uses a native modal above Chronicle, including mouse and
  keyboard acknowledgement. The open Chronicle and form drafts survive. Acceptance
  resumes the view/socket without reloading or replaying a refused mutation.
- Guide and registration retain the exact standing production permanence
  wording by default. Only known temporary-world metadata selects test copy.
  Unknown initial metadata errors do not block ordinary entry; an actual
  staging refusal opens notice recovery. Known test-world notice failures
  remain closed. Journal and Ideas have the same entry/revision recovery.
- The fixed AI paragraph describes Enfolded's own AI travelers and the possible
  authored silence; it no longer promises an answer to every question. The
  already-authorized no-pretending rule and existing production introductions
  are not weakened.
- One server-authored agreement includes the configured age and participation
  statement, is rendered verbatim, and is covered by `accepted: true`. Its exact
  text is hashed and stored in the existing snapshot. This is self-attestation,
  not independent age verification; it adds no migration or date of birth.
- Conventional case-insensitive flag values work. Unknown values stay closed.
  Ordinary revoked, rotated and sanctioned credentials are refused without a
  false ERROR/Sentry alert. Staging socket checks avoid the redundant lookup.
  Identity and consent share live-credential validation while known participant
  reads stay free of writer-lock waits and acceptance rechecks under its lock.
- Public APIs are listed separately from static assets, with method-specific
  exemptions and unchanged rate policy. Nonfiction consent 428 and participation
  configuration/check 503 are documented as operational notice decisions,
  separately from invisible plumbing and authored gameplay failures, in
  `AGENTS.md`, the matching irreversibility skill and PR template. This clarifies
  the authorized consent surface; it grants no general gameplay 5xx exemption.
- The age-parser simplification needed a correction to the review claim:
  **5,000 ASCII decimal digits** pass both predicates but `int()` raises
  `ValueError` under pinned Python 3.11. Input is now bounded before conversion,
  with a regression for that case.
- The roadmap names migration 0031 as the merged top, and the architecture
  overview counts 31 migrations. F2 is Partial: version `0.1.2rc1` and local
  wheel smoke are done; a tag, tagged workflow and published-artifact checks
  remain. The checklist stays at 95 rows / 54 beta gates / 44 open, with status
  counts 13 Done / 41 Partial / 39 Not started / 2 Unknown.
- The optional status-order nit is deliberately retained: an anonymous POST to
  `/participation` is refused as lacking a live personal credential, including
  when test mode is off. Public metadata remains available without a key.

Focused checks before the combined gate: **237 backend tests**, **42 soak
tests**, **58 browser tests**, and **10 socket unit tests** passed. A short
local 12-client temporary-world run delivered **24 chat lines / 288 receipts**
and **24 moves / 264 receipts**, with zero extra, missing or out-of-order
receipts and no missing pongs. It exited 0. No hosted run is claimed.

The current combined `ENFOLDED_E2E=1 ./scripts/check.sh` completed on
2026-11-11 with exit **0**: Ruff passed; **3,607 Python passed / 1 skipped**
(the optional absent historical QA tag); **189 Vitest passed** in 19 files;
production bundle byte-fresh; installed `enfolded-0.1.2rc1` wheel verified
schema **31**; **177 Playwright passed** in 5.5 minutes. Backend and frontend
source remained frozen during this run. The working-rule/checklist checks
also pass after the documentation changes, and 97 relative file links have
no missing targets. No new migration, golden re-pin or world-history writer
was introduced by the review fixes.

Current tested browser assets:

- `index-Dm7ud2rm.js`: SHA-256 `01f69c92107f19297db7f3ceef4262e3a9ec0f10cba05cf2e3ff8873d623a7e3`.
- `index-1EslDMRk.css`: SHA-256 `2d4038cec1d8e8e71eb8e21e1bffe3d9e912ea6b0e2f7f2a4791351aeea98b4b`.


## Browser CI infrastructure follow-up — 2026-11-11

Both GitHub CI runs for `a5f3330` passed Python and frontend checks, but the
browser jobs failed in `playwright install --with-deps chromium`, before
executing tests. Retrying each failed job produced the same Ubuntu mirror
DNS errors and apt exit 100. Another branch had the same failure earlier
that day, while recent main runs passed on the same Ubuntu 26.04 image.
The evidence does not identify the runner's Ubuntu version as the cause.

The browser jobs in CI and Release now use the official Playwright
`v1.61.1-noble` image, pinned to registry manifest digest
`sha256:5b8f294aff9041b7191c34a4bab3ac270157a28774d4b0660e9743297b697e48`.
Its preinstalled Chromium and system dependencies remove the apt dependency
from each test run. The host is pinned to Ubuntu 24.04 to match the container
and cached toolchain platform. Explicit setup still selects Python 3.11 and
Node 20; the image's bundled Node 24 is not used for the project. A guard
compares installed Playwright with the image's version marker before tests.
Both workflows keep identical real-server setup, production build and the
full browser suite. The first container run pulled and started successfully and
selected Python 3.11.18, then exposed that setup-python v5's optional pip
cache calls `lsb_release`, absent from this image. Browser jobs now omit
that cache setting; dependency installation and all checks remain required. Release publishing depends on its separate browser job,
so a browser failure still prevents publication. No release was triggered.

Verified: actionlint 1.7.12 passed on both workflows (release binary checksum
verified); YAML parsed; browser steps/images matched; the publisher requires
successful E2E. The actual version-guard script, with a temporary metadata
path, accepted matching 1.61.1 and rejected a different version, malformed
JSON and a missing marker (**4/4**). The registry supplied the pinned digest.
The local Docker pull was denied by this environment's network policy, so
container execution is left to GitHub CI. Application code and browser tests
are unchanged from the previously passed full gate; it was not repeated
locally for these workflow changes.

Contract sources inspected: [official Playwright Docker guidance](https://github.com/microsoft/playwright/blob/v1.61.1/docs/src/docker.md),
the [versioned Noble Dockerfile](https://github.com/microsoft/playwright/blob/v1.61.1/utils/docker/Dockerfile.noble),
the installed 1.61.1 version-marker reader/writer, and the live Microsoft
registry manifest. No migration, world-history write, golden re-pin,
world-meta pin or era-bank edit is introduced by this follow-up.

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

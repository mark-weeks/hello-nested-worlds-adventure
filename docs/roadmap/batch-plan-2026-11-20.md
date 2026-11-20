# Enfolded: next parallel batch (planned 2026-11-20, main 372d77f / #181)

*Planned by Claude Code at the owner's request on 2026-11-20, in the spirit of
the parallel-work rules (#176). The owner's items in section 6 are decided in
[the 20 November owner decisions](owner-decisions-2026-11-20.md); where a prompt
below leaves a value or choice to the owner, that record governs. This plan
authorizes no merge, deployment or spend.*

## 1. Takeaway

This batch removes most of the agent-side blockers for the AI-on newcomer watch (D-A, item 3).

- **Codex** puts a Map view inside `/app` and then switches `/` to the React app (owner item 2, Watch entry requirement 2).
- **Grok Bot** builds a model-policy kit the owner can approve, writes a procedure for clearing the latched spend stop, and adds a live-route probe (requirement 5).
- **Claude Code** extends moderation to every shared line, writes the watch-twin records (community-policy template, refreshed watch kit, teardown, notice text) and opens the status PR (requirements 1, 4, 6 and 8).

Once these merge, the watch still needs three things:
- the owner's inputs in section 6;
- the L5 AI-disclosure PR, which Codex starts right after X2;
- Claude's selected-commit F2 evidence record, done once the owner names the commit to deploy.

If the owner wants a tool rather than a written procedure to clear the spend stop, that also needs an ADR-039-level decision (O9).

*Epistemic status:* each "not done" claim comes from read-only passes over main 372d77f, and the reviewers' corrections were checked against the files. These facts were re-checked directly:
- `server/handlers.py:934-935` serves `static/index.html` at `/`.
- `config/` holds only the two `*.disabled.json` policies.
- The latest migration is `0033_private_chat_reports.sql`.
- `GENERATOR_VERSION = 2` (`multiverse/store.py:41`).
- Five fragments are pending in `docs/changelog.d/`.
- §8 of `fly-deployment.md` is "Launch window" (:1616). "Model-state and gameplay checks" is a checklist bullet at :1695, not a heading.
- ADR-040:53-56 says the 90/180-day values are "not deployment defaults or checked-in policy selections".
- `0032_model_spend.sql:46` says "There is no application reset operation."

Two things are still unverified: how the incumbent provider's Chat Completions-compatible endpoint behaves, and whether Vite can import the vendored `static/d3.v7.min.js` cleanly.

## 2. Batch table

| # | Agent | Branch | Title | Serves | Single-writer held | Main files | Depends on | Owner read (one-way door) |
|---|---|---|---|---|---|---|---|---|
| C0 | Claude Code | `claude/` | Status PR: fold the pending fragments, restamp roadmap at #181 | item 41; AGENTS.md single-writer 1 | **status documents** | `docs/CHANGELOG.md`, `docs/roadmap/README.md`, `docs/roadmap/beta-launch-checklist.md`, `docs/changelog.d/*` (removed by `scripts/fold_changelog.py`), `tests/test_beta_checklist_counts.py` only if a row status changes | none; open first | none (records) |
| C1 | Claude Code | `claude/` | Classify every shared line; hold when unjudged | item 30 (D-F); Watch req. 4; S1/S3; ADR-004 §2 | none | `server/moderation.py` (`screen()` :207), `server/ideas_api.py`, `server/participant_api.py`, `server/handlers.py` (existing `/speak`, `/agent/voice` fixes only), ADR-004 §2, `tests/test_shared_text_fail_closed.py`, `tests/test_guard.py`, `tests/test_agent_honesty.py`, moderation tests | none | moderation: yes |
| C2 | Claude Code | `claude/` | Watch-twin records: community-policy template, watch kit refresh, teardown, notice text | items 4, 5, 6, 8, 12; Watch req. 1, 4, 6, 8; K1, A1, R3/P4 | none | `docs/development/community-reporting.md`, `tests/test_community_policy.py` / `tests/test_community_activation.py` (temp-file tests), `docs/evaluation/2026-11-02-newcomer-watch-kit.md`, `docs/infrastructure/fly-deployment.md` (**"Teardown before launch" :853-886 and "Participation notice and adult confirmation" :485, except the `NESTED_WORLDS_TEST_DATA_USE` row :516**) | none | privacy/retention promises, deployment runbook: yes |
| X1 | Codex | `codex/` | Map view inside `/app` (no route change) | item 2; Watch req. 2 | **client bundle** | `frontend/src/components/MapView.jsx` (new), `frontend/src/App.jsx`, `frontend/src/components/SceneView.jsx`, `frontend/src/__tests__/*`, `frontend/e2e/*`, `static/app/**` (rebuild) | none | none |
| X2 | Codex | `codex/` | Switch `/` to the React app; old map at a named path; ADR-005 result; remove PixiJS | item 2; §3 "PixiJS"; Watch req. 2 | **client bundle** (after X1 merges) | `server/handlers.py` (`/` branch :934-935, `_is_public_asset` :621-641), `frontend/src/main.jsx`, `frontend/package.json`/lock, `static/guide.html`, `static/ideas.html`, `static/journal.html`, e2e specs, `tests/test_guard.py`, ADR-005, `README.md`, `THIRD_PARTY_NOTICES.txt` + `static/app/THIRD_PARTY_NOTICES.txt` | X1 merged | authentication (invite-gate exemption): yes; public entry URL changes (reversible) |
| G1 | Grok Bot | `cursor/` | Watch model-policy kit: example policy, reservation report, endpoint check record, model sections of the runbook | items 3, 7, 24, 26, 27, 29; D-A; Watch req. 5; S2, E1, E2, M4 | none | `consciousness/model_policy.py`, `main.py` (existing `cmd_model_policy` :191 output only), `config/model-policy.watch.example.json` (new), `docs/development/model-policy.md`, `docs/development/agent-runtime.md`, `docs/evaluation/2026-11-2x-chat-completions-endpoint-check.md` (new), `fly-deployment.md` (**§3a steps 6–7, "Approved live controlled text" :566, row :516, and the item 7 key-mint step**), `tests/test_model_policy*.py` | none | spend, external data destination, authentication (key mint): yes |
| G2 | Grok Bot | `cursor/` | Written procedure for clearing the latched accounting stop | items 3, 28; ADR-039; E2 | none (no migration) | `docs/development/model-policy.md` (new "Clearing the stop" section only), `docs/infrastructure/incident-response.md` | rebase on G1 for `model-policy.md` | spend control: yes |
| G3 | Grok Bot | `cursor/` | Authenticated live-route probe: success, hold and failure | Watch req. 5 "live success/hold/failure probes"; M4, D3 | none | `scripts/live_route_probe.py` (new), `tests/test_live_route_probe.py` (new, fake Chat Completions server), `fly-deployment.md` (**§8 checklist bullet "Model-state and gameplay checks" :1695 only**) | may open as a draft now; mark ready only after C1 merges (hold semantics); rebase on G1 for runbook text | deployment runbook: yes |
| G4 | Grok Bot | `cursor/` | Backup job in a main-only `backup` environment | O7; Watch req. 4, 8 (participant data protection) | none | `.github/workflows/backup.yml`, `docs/infrastructure/backup-bucket.md` | open before the twin collects participant text | deployment, authentication: yes |

## 3. Sequencing and collision rules

1. **Client bundle (`frontend/` + `static/app/`).**
   - Codex holds it first with X1, then with X2. Nobody else opens a PR that edits or names the bundle while either is open.
   - C1 must not change `frontend/e2e/`.
   - Queue after X2, in order:
     1. L5 disclosure UI (Codex).
     2. ADR-036 batch 1b (the owner names who owns it, O1).
     3. ADR-041 naming (Claude; also takes migration 0034).
     4. Item 35 together with the ADR-037 batch 2 client de-labelling.
2. **Migrations.** No PR in this batch adds one. The slot stays free for ADR-041 naming in the next batch.
3. **Status documents.** C0 opens first and holds them.
   - It folds whatever fragments are on main at its final rebase, because `scripts/fold_changelog.py` folds every fragment present. Its PR body lists the folded set.
   - Later fragments go to the next status PR.
   - No other PR edits `docs/CHANGELOG.md`, `docs/roadmap/README.md`, `docs/roadmap/beta-launch-checklist.md` or `tests/test_beta_checklist_counts.py`.
   - Under AGENTS.md item 1, a feature edits directly the `README.md` and runbook text it makes untrue. For example, X2 edits README :111, :117, :159, :166 and :168. Only standing counts and what-has-shipped lines go in as `Status:` lines.
4. **`docs/infrastructure/fly-deployment.md` is split by section.**
   - **C2:** "Teardown before launch" (:853-886) and "Participation notice and adult confirmation" (:485), except row :516.
   - **G1:** §3a steps 6 and 7, "Approved live controlled text" (:566), row :516 (`NESTED_WORLDS_TEST_DATA_USE`), and the item 7 key-mint step.
   - **G3:** only the §8 checklist bullet at :1695.
   - **Codex:** does not touch the file.
   - "Provider data rule" (:810) is unassigned this batch.
   - G1 keeps the "step 6" label and G3 keeps the "authenticated live-voice probe in §8" wording, so C2's cross-references at :857-858 and :880 stay true. Any PR that renames one of these fixes the reference on rebase.
   - Whichever PR merges second rebases.
5. **`docs/development/model-policy.md`.** Grok only. G1 edits the policy and activation text. G2 adds a separate "Clearing the stop" section and rebases on G1.
6. **`server/handlers.py`.** C1 changes only the existing `/speak` and `/agent/voice` paths. X2 changes only the `/` branch and `_is_public_asset`. The ranges are disjoint. Neither adds endpoint logic.
7. **`tests/test_guard.py`.** C1 and X2 both edit it. The second to merge rebases.
8. **`main.py`.** Only G1 touches it (`cmd_model_policy` output). G2 adds no command.
9. **`static/guide.html`, `static/ideas.html`, `static/journal.html`.** Only X2 edits them this batch. The L5 guide copy waits for X2.
10. **Watch kit.** C2 owns `docs/evaluation/2026-11-02-newcomer-watch-kit.md`. G1 and G3 give Claude one-line pointers in their PR bodies.
11. **ADR Status lines.** No agent changes one. ADR-035 and ADR-039 stay Proposed until the owner accepts them after items 24 and 28 (O3, O9). The owner says which PR records the acceptance. The C1 and X2 amendments to the body text of ADR-004 §2 and ADR-005 are not status changes.
12. **Selected-commit evidence record (F2, schema-33 wheel smoke).** Next Claude batch, after X2, C1, C2 and G1 merge and the owner names the commit (O11).

## 4. Review assignments

- **Copilot:** unavailable until the monthly quota resets. On #182 it failed with HTTP 402 ("exceeded your monthly quota"), and no budget is set (item 46, O15). Until then, each PR's executing cross-agent review is its only non-author review. The steps below apply once Copilot can run again.
  - It reviews automatically when each PR opens.
  - When the author marks the PR ready, the author requests one more review on the final commit at the default effort.
  - Any other Copilot review, Max effort included, is the owner's to request.
  - If Copilot cannot run, the PR says so.
- **Executing cross-agent review:**
  - Claude Code reviews X1, X2, G1, G2, G3 and G4.
  - Codex reviews C1 and C2.
  - Codex also reviews C0 if C0 changes `tests/test_beta_checklist_counts.py` or any other non-Markdown file. Otherwise C0 is records-only.
- **Wait for the owner's read of the irreversibility check:**
  - C1: moderation.
  - C2: privacy and retention, deployment runbook.
  - X2: authentication, via the invite-gate exemption at `handlers.py:602` / `_is_public_asset`.
  - G1: spend, data destination, key mint.
  - G2: spend control.
  - G3: deployment runbook.
  - G4: deployment and authentication (the backup token's scope).
  - Green tests are not approval.
- **Queue size:** the owner's adopted item 45 limit ("at most three PRs wait on the owner") is not yet a working rule. Seven PRs here wait on the owner's read, so the owner confirms the queue size in O1.
- Copilot approvals never count. The owner merges each PR individually, and auto-merge is never enabled.

## 5. Prompts

### 5a. Claude Code (holds the status documents; no bundle, no migration)

```
You are Claude Code working in mark-weeks/hello-nested-worlds-adventure (Enfolded), main at 372d77f (#181). First read:
- AGENTS.md: "Current delivery priority", "Working in parallel", "Verification and completion", and the world covenants.
- docs/roadmap/owner-decisions-2026-11-18.md: section 1 (D-A..D-J) and sections 2, 4 and 5.

Your concern is integrity, safety and records. Open three pull requests, each on its own claude/ branch. Open C0 first so it holds the status documents.

C0 - Status PR (owner request: item 41)
- Goal: fold the pending fragments with scripts/fold_changelog.py. Run `git fetch --unshallow origin main` first. Five fragments are pending now: claude-awesome-newton-k3lclx.md, claude-dreamy-gauss-y0s3tz.md, claude-wizardly-gauss-h90q0o.md, claude-wizardly-gauss-h90q0o-puzzle-answers.md and codex-documentation-test-run-rule.md. The script folds every fragment present, so fold whatever is on main at your final rebase and list the folded set in the PR body.
- Apply exactly the Status: lines those fragments carry, and nothing more.
- Restamp docs/roadmap/README.md line 3, in its existing form, to the main commit your final rebase sits on: "*Verified on <date> against `main` at #<last merged PR> (`<short SHA>`, <date>)." Use the base you actually inspected, not 372d77f, and name that SHA in the PR body.
- If you see other mismatches with the 2026-11-18 record, list them in the PR body for the owner and do not edit them. Examples: A1 at beta-launch-checklist.md:210 still says "No honesty rule exists" although consciousness/honesty.py exists; S4, C7, P6, E2.
- Holds: status documents (docs/CHANGELOG.md, docs/roadmap/README.md, docs/roadmap/beta-launch-checklist.md, tests/test_beta_checklist_counts.py).
- Non-scope: code, new decisions, ADR Status lines, and any file outside those files and the folded fragments.
- Verification: if every changed file is Markdown under docs/ outside docs/decisions/, use the documentation-only test-run rule:
  1. Run tests/test_beta_checklist_counts.py and tests/test_deploy_staging_workflow.py.
  2. Search tests/ for each changed basename (rg -n -F '<basename>' tests/) and run every reader you find.
  3. Validate changed relative links and anchors.
  4. Record the CI run and head SHA in the PR, and stay in draft until project CI is green on the exact head SHA.
  If you change tests/test_beta_checklist_counts.py, run ./scripts/check.sh locally instead; Codex then does an executing review.

C1 - Moderation coverage (owner answer item 30, D-F 2026-11-19; Watch entry requirement 4 "safe holds for unjudged shared text"; checklist S1/S3; ADR-004 section 2)
Goal: every shared line on Speak, agent voice, Ideas and published profile fields goes to the classifier, not only ambiguous ones. Today server/moderation.py screen() returns _ALLOW_CLEAN at :207 for locally clean lines; needs_model at :269 is only a predicate.

When a shared line is held:
- It is held when the classifier is unreachable, a shared or per-player classify cap or the model-action cap is spent, the dollar ceiling is spent, or the AI kill switch is on.
- The kill switch then also stops Ideas and profile publishing.
- A spent voice cap holds nothing (item 30).

What keeps today's screen (not moved to every-line classification):
- Chat (server/websocket.py:659, surface "chat") and the puzzle public_excerpt (server/handlers.py:2175, surface "puzzle", via moderation.py:280-288) keep today's screen() behaviour unchanged.
  - A locally clean line publishes without a classifier call.
  - A line the local tier marks ambiguous still escalates to one classify call, and is held if that call cannot complete (moderation.py:207, :237-249).
  - Do not remove that escalation. Item 30 names neither surface for every-line classification; say so in the PR body.
- Registered names stay on the local name screen (moderation.py:305-319), with no classifier call.
- Private journal, unpublished profile and report text are never sent.

Honesty answer (covenant):
- handlers._asks_identity uses moderation.needs_model (handlers.py:251), and the honest line still passes moderation.screen (handlers.py:1291 speak, :1605 agent voice).
- The authored identity answer (consciousness.honesty) must still return with AI off on /speak and /agent/voice: HTTP 200, ai:false.
- State exactly how the identity line is exempted or screened, and prove it with a behaviour test.

Hold responses (keep the existing shapes; never a 5xx or a raw error):
- Speak and agent-voice holds: HTTP 200 with moderation.HOLD_LINE, held:true, ai:false (http_body).
- Ideas and profile holds: HTTP 422 with the product lines IDEAS_HOLD / PROFILE_HOLD (moderation.py:62-94, :140-150).

Local runs and the e2e suite:
- A local world or test run with no moderation route configured, including NESTED_WORLDS_DISABLE_AI=1 with no route, keeps publishing locally clean lines.
- frontend/e2e/server.js:17 starts every e2e server with that variable, and the discovery, ideas, participation-pages, participation and keyless-return specs publish Ideas and profiles, so no e2e spec may need to change.
- If the rule must reach local runs, stop and write the needed e2e changes as a handoff in the PR body. Do not edit frontend/.

Amend ADR-004 section 2 (body text, not its Status line) in the same PR.

Files: server/moderation.py, server/ideas_api.py, server/participant_api.py, server/handlers.py (fixes on the existing /speak and /agent/voice paths only, no new endpoint logic), docs/decisions/ADR-004-day-one-data-policy.md section 2, tests/test_shared_text_fail_closed.py, tests/test_guard.py (X2 also edits it; the second to merge rebases), tests/test_agent_honesty.py, moderation tests.

Non-scope: cap integers (the owner sets them as deploy secrets; Grok only lists them as placeholders); model policy files; frontend/ including frontend/e2e/; static/app/; migrations.

C2 - Watch-twin records (items 4, 5, 6, 8, 12; Watch entry requirements 1, 4, 6, 8)
(a) Community policy:
- Do not commit an enabled watch policy under config/. ADR-040:53-56 says the 90/180 days are "not deployment defaults or checked-in policy selections", and server/community_policy.py:109-112 requires contact and backup_notice text for any enabled route.
- In docs/development/community-reporting.md, document the watch policy as a template: chat retained until deleted, reports retained 90 days, with <OWNER: contact> and <OWNER: backup_notice> placeholders. Explain how it is installed, as owner decision O12 gives it. `--policy` only feeds the offline `community-policy --check`. Activation means placing the file on the machine, setting NESTED_WORLDS_COMMUNITY_POLICY to its path, restarting, and checking the revision and the chat and report flags at /community (fly-deployment.md:443-462).
- Add behaviour tests in tests/test_community_policy.py and tests/test_community_activation.py. They build the template in a temp file with test text filled in and prove it loads and enables chat and Report.
(b) Refresh docs/evaluation/2026-11-02-newcomer-watch-kit.md:
- The honesty rule now exists, so the wording at about :522 is wrong.
- The watch runs AI-on through the controlled openai_compatible route, not per-scale silence or the Anthropic adapter (about :158-200 and :780-796). Cite docs/development/model-policy.md rather than duplicating it.
- Record the venue and twin as decided.
(c) Teardown: rewrite it in the kit (about :488) and in fly-deployment.md "Teardown before launch" (:853-886).
- The twin is destroyed only when every report is closed (item 5).
- Its off-host snapshots are removed by hand with scripts/backup_store.py delete-before, then delete (item 12).
- On a versioned bucket these commands hide objects but do not erase them. Do not call this step erasure, and promise no deletion date. Leave <OWNER: bucket versioning and what the 7-day delete lock counts from>.
- Retire the twin's backup schedule completely. Stopping the outside dispatcher is not enough, because backup.yml also runs on its own cron (:17 and :47 each hour). After the final snapshot:
  1. stop the scheduler's dispatch;
  2. disable the "Off-host backup" workflow;
  3. delete the ENFOLDED_BACKUP_REQUIRED and ENFOLDED_BACKUP_APP variables;
  4. revoke the backup token and delete its secret;
  5. pause the twin's heartbeat monitor.
- Then write the separate re-arm order for production, as owner decision O14 gives it:
  - before the boot: credentials in the protected environment, the app target, the workflow re-enabled, and the external dispatcher retargeted to production;
  - after the first production deploy and before invitations: the first manual dispatch, ENFOLDED_BACKUP_REQUIRED=true, the dispatcher enabled, successive objects checked against the one-hour bound, and a new heartbeat monitor.
- Keep the existing references to "step 6" and to "the authenticated live-voice probe in section 8" (:857-858, :880) as they are.
(d) Notice-text template (item 6):
- Write it in fly-deployment.md "Participation notice and adult confirmation" (:485). The served notice is built from NESTED_WORLDS_TEST_CONTACT, NESTED_WORLDS_TEST_RETENTION and NESTED_WORLDS_TEST_DATA_USE (server/participation.py:67-70) plus the community policy's contact and backup_notice.
- It covers: the contact address, a destroy date that open complaints can extend, the provider named, not used for training, and report and backup retention without a promised date.
- Do not edit the NESTED_WORLDS_TEST_DATA_USE row at :516; Grok G1 owns it.
- Placeholders, never invented: <OWNER: contact address>, <OWNER: provider name>, <OWNER: twin destroy date>, <OWNER: tester names/dates>.
Non-scope: fly-deployment.md section 3a steps 6-7, "Approved live controlled text" (:566), "Provider data rule" (:810), row :516 and section 8; docs/development/model-policy.md; config/; status documents.

Rules for all three PRs:
- Do not touch frontend/ or static/app/ (Codex holds the client bundle).
- Add no migration. Change no ADR Status line.
- Do not edit AGENTS.md, .claude/skills/, the PR template or the working-rule guides.
- Do not edit status documents outside C0.
- Verification for C1 and C2: behaviour tests, not string-presence checks. Iterate with the focused suites, then run ./scripts/check.sh before marking ready. Both change tests, so the documentation-only rule does not apply.
- Changelog: one fragment each for C1 and C2 in docs/changelog.d/, named after the lowercased branch (.claude/skills/changelog-entry/SKILL.md). Add Status: lines for status-document changes such as S1, S3, A1 and C7 evidence. Record the actual checks and anything unverified.
- Irreversibility check: run .claude/skills/irreversibility-check/SKILL.md on the real diff. C1 (moderation) and C2 (privacy and retention promises, deployment runbook) both wait for the owner's read.
- Process: open each PR as a draft. Mark it ready when verification passes, then request the one Copilot review on the final commit. Answer every finding in its thread ("fixed in <commit>" or declined with the reason), ending with your footer. Codex does the executing review.
- Never merge, enable auto-merge, deploy, spend, recruit, resolve threads, set secrets, or push to another agent's branch.
- Stopping point: if an owner value is missing, leave a named placeholder, list the exact missing input in the PR body, and finish everything else.
- Next batch, not now: ADR-038 salt B1; records hygiene (items 21, 33, 15); ADR-041 naming (it waits for the client bundle and the migration slot, and the owner must approve the pin diff inside that PR); item 35; the F2 selected-commit evidence record.
```

### 5b. Codex (holds the client bundle)

```
You are Codex working in mark-weeks/hello-nested-worlds-adventure (Enfolded), main at 372d77f (#181). First read:
- AGENTS.md: "Current delivery priority", "Working in parallel", "Verification and completion", and the covenant on one interaction surface per purpose.
- docs/roadmap/owner-decisions-2026-11-18.md: item 2 and section 3 "PixiJS".

Your concern is the player journey in /app. You hold the client bundle (frontend/ + static/app/) for this batch. No other agent opens a bundle PR while yours is open.

Owner direction served: item 2.
- "/" serves the shared React Map view.
- The current map stays reachable at a named path until the cohort read-out.
- ADR-005 records the result.
- PixiJS is removed if unused.
This is Watch entry requirement 2 in docs/roadmap/beta-launch-checklist.md#admission-gate. It must land in separate client PRs before the watch, whose sessions are due by 11 December 2026.

PR X1 (codex/ branch) - Map view inside /app, no route change
- "Shared React Map view" is defined by owner decision O10 (docs/roadmap/owner-decisions-2026-11-20.md): the world map rendered in React inside /app, sharing its session, notice gate, Travelers panel and single Speak/Puzzle/Act surfaces, landing at "/", replacing SceneView's "World map" link rather than adding a second navigation surface.
- SceneView already has a navigation surface (<enfolded-navigation> with "World map", SceneView.jsx:9). Show that the Map view replaces or extends it rather than duplicating it.
- Add frontend/src/components/MapView.jsx. Reuse the vendored static/d3.v7.min.js the way frontend/src/main.jsx:3 imports static/navigation.js. Add no new npm dependency. Whether Vite imports the minified D3 build cleanly is unverified: check it first, and if it does not, say so in the PR body before choosing another approach.
- Speak, Puzzle, Act and Travelers (with Block/Report) each stay one surface, reusing TextPanel and Interact. No parallel composer, quest controller or status pane. Keep the participation-notice gate and the AI intro (App.jsx ~759). Use progressive disclosure, with no preselected route.
- Use only displayName/nodeAddress from frontend/src/names.js. Never parse the "-digits" suffix yourself.
- Acceptance criteria: a keyboard-only full loop (move, Speak, Puzzle, Act, reload/reconnect) and reduced motion. Add frontend/e2e/core-loop-keyboard.spec.js.
- No Math.random or Date.now in any rendering derived from node state.
- Commit the rebuilt static/app/.

PR X2 (codex/ branch; open only after X1 merges) - route switch
- Server:
  - Fix the existing "/" branch at server/handlers.py:934-935 so it serves the React app shell.
  - Serve the current explorer at a named path. Use /map (owner decision O10, 2026-11-20).
  - Add that path to Handler._is_public_asset (handlers.py:621-641; the root "" is at :630), or the invite gate (:602) blocks it. This is an authentication change, so the PR waits for the owner's read.
  - Register the alias only, with no new endpoint logic.
  - Keep invites at /app?key= (handlers.py:1756) and check that the register and participation redirects still land.
  - The old explorer stays reachable at its path until the cohort read-out. Do not remove it. Freeze it except for privacy, safety and correctness fixes.
- Links: update "/" links in static/guide.html (:36, :49), static/ideas.html (:18), static/journal.html (:3) and SceneView's "World map" link.
- Pitch capture: scripts/capture_pitch_assets.mjs:117-128 (openExplorer) navigates to "/" and waits for the old explorer's #node-name and window.NodeArt. Point it at /map, keeping the ?name= query, so `npm --prefix frontend run capture:pitch` (frontend/package.json:16) still works. Fix README.md:397 and docs/pitch/beta-brief.md:210 only if they become untrue. No CI step runs it, so run it once or say in the PR body that it was not run.
- e2e: update the specs that loop over '/' (blocking, delivery, expressive, ideas, inhabitants, participation, presence-join, puzzle-answer-withdrawal, reporting, ux-review, ux) and the ones that goto('/') directly (smoke, wayback, wrap, expressive). Confirm the list with `rg -n "goto\('/'\)|of \[.*'/'" frontend/e2e`, list the final set in the PR body, and cover both the new "/" and the old map's path.
- Python tests:
  - Update the "/" route assertion at tests/test_guard.py:1001 and the public-asset tests (~878-890) for the new path.
  - tests/test_frontend_contract.py (:141, :152-154, :194-200, :317) reads static/index.html as a file and should keep passing if the file stays.
  - C1 also edits tests/test_guard.py; the second to merge rebases.
- PixiJS: remove pixi.js (frontend/package.json; main.jsx:5 "pixi.js/unsafe-eval") only after confirming nothing else uses it. README :117 and :166 call the client "React + PixiJS", so check the scene renderer. Regenerate THIRD_PARTY_NOTICES.txt and static/app/THIRD_PARTY_NOTICES.txt (the postbuild step copies it; scripts/verify_wheel.py:195 pins the name).
- Records: record the result in the body of docs/decisions/ADR-005-launch-operations.md (around :20 and :74, which say retirement is undecided; check the exact lines). Do not change any ADR Status line. Edit directly the README.md route lines you make untrue (:111, :117, :159, :166, :168). Standing counts and what-has-shipped lines go in as Status: lines in your fragment.

Non-scope for both PRs:
- L5 AI-disclosure UI (queued next, after X2).
- ADR-036 batch 1b (not yet assigned).
- ADR-041 naming client changes (Claude).
- Item 35 / ADR-037 de-labelling.
- server/participation.py notice text.
- Status documents (docs/CHANGELOG.md, docs/roadmap/README.md, beta-launch-checklist.md, tests/test_beta_checklist_counts.py).
- Migrations.
- Working rules (AGENTS.md, .claude/, the PR template, the rule guides).
- docs/infrastructure/fly-deployment.md.
- server/moderation.py.

Verification:
- Run ./setup.sh, then iterate with focused Vitest/Playwright plus tests/test_server.py, tests/test_frontend_contract.py and tests/test_guard.py.
- Before marking ready, run ./scripts/check.sh with ENFOLDED_E2E=1 (Chromium installed), including the bundle-freshness and installed-wheel gates.
- Inspect "/", "/app" and the named path in a browser and attach screenshots.

Records:
- One changelog fragment per PR in docs/changelog.d/, named after the lowercased branch (.claude/skills/changelog-entry/SKILL.md). Include Status: lines for the roadmap's route/map text and the checklist evidence for entry requirement 2, and record the actual checks.
- Run the irreversibility check (.claude/skills/irreversibility-check/SKILL.md) on the real diff. For X1, expect no door. For X2, expect no birth, migration, chronicle or continuity door, but an authentication change (the invite-gate exemption) and a reversible change of public entry URL. Say so explicitly; X2 waits for the owner's read.

Process:
- Open each PR as a draft and state in the PR body that it holds the client bundle.
- Mark ready only after checks pass, then request the one Copilot review on the final commit.
- Answer each finding in its thread, ending with your footer. Claude Code does the executing review.
- Never merge, enable auto-merge, deploy, spend or recruit.
- Stopping point: if the owner rejects /map or a design reading in review, change only that. Anything outside item 2 goes in the PR body as a handoff, not built.
```

### 5c. Grok Bot / Cursor (model runtime and operations; no bundle, no status docs)

```
You are Grok Bot working in mark-weeks/hello-nested-worlds-adventure (Enfolded), main at 372d77f (#181), on cursor/ branches. First read:
- AGENTS.md: "Current delivery priority", "Provider and model optionality", "Working in parallel", "Verification and completion", and the failure-stays-in-fiction and no-voice-pretends-to-be-human covenants.
- docs/roadmap/owner-decisions-2026-11-18.md: D-A; items 3, 7 and 24-29; section 5.
- ADR-034, ADR-035, ADR-039, docs/development/model-policy.md and docs/development/agent-runtime.md.

Your concern is model runtime and operations.

Owner direction served:
- D-A / item 3: the watch runs AI-on under the controlled policy.
- Watch entry requirement 5 in docs/roadmap/beta-launch-checklist.md#admission-gate: frozen policy, explicit spend limits, enforcement, and live success/hold/failure probes (S2, E1, E2, M4, D3).

PR G1 - watch model-policy kit
- Example policy:
  - Add config/model-policy.watch.example.json in the enabled shape that consciousness/model_policy.py validates (:194-199, :208, :262-264). That includes adapter, endpoint, model, resolved_models, timeout_seconds, options, input_bound_kind (value "provider_context_maximum"), input_bound_evidence, prices, data_use_note, approval_reference, limits.global_daily_usd, limits.participant_daily_usd and ledger_retention_days (>= 2).
  - Every owner value is a clearly marked placeholder that the check refuses.
  - Show $15/day global and $3/day per participant as unconfirmed placeholders in the policy JSON.
  - The $150 provider console limit is not a policy field: the strict parse refuses unknown keys (model_policy.py:246-247, :262-264). Record it in the PR body and in the runbook as a separate owner step on the provider account (owner decisions O4).
- Reservation report: extend the existing `python main.py model-policy --check` output (cmd_model_policy, main.py:191; no new command; the logic lives in consciousness/model_policy.py, reserve_microusd at :379). Per route, report the full-context reservation and how many reservations fit under the participant and global ceilings. The owner confirms amounts against this report (item 26).
- Endpoint check: write docs/evaluation/2026-11-2x-chat-completions-endpoint-check.md, the item 24 check. It covers both candidates of owner decision O3, the incumbent provider's Chat Completions-compatible endpoint and OpenAI's own Chat Completions endpoint, and asks whether each satisfies consciousness/openai_compat_provider.py on:
  - structured outputs for intention and moderation;
  - send_store_false;
  - max_tokens_param;
  - usage counts for settlement;
  - the reported model, for resolved_models.
  Verify against current official docs (the AGENTS.md external-contract rule), and mark anything that cannot be confirmed without a live key as unverified.
  - For each candidate, name the models it serves for voice, intention and moderation. Moderation needs structured output, and the record names the model each candidate would pin.
  - End with one recommendation: the candidate that passes the desk checks. The owner signs the data-use note for that account and endpoint, then G3's first live run on the twin establishes final acceptance (O3). Signing does not wait for live proof, because the live proof needs the signed note.
- Rubric-run brief: add a one-page brief for item 27's single-grader live rubric run with scripts/model_eval.py --live --max-usd --max-calls --allow-destination. Do not run it.
  - Controlled mode refuses live eval wrappers (docs/development/model-policy.md:123-128; evals/harness.py RecordingProvider).
  - So the brief runs it isolated from the twin, with no NESTED_WORLDS_MODEL_POLICY and no twin database, against the same endpoint and pinned ids.
  - It has its own --max-usd, and its spend is reconciled against the provider console limit (owner decisions O13).
- Runbook: in docs/infrastructure/fly-deployment.md edit ONLY these parts:
  1. Section 3a step 6: replace the "no-provider watch" text. Keep the label "step 6"; Claude's teardown text refers to it.
  2. Section 3a step 7: its check greps '"ai": false' for the no-provider watch (about :402-423), which is untrue for an AI-on watch.
  3. "Approved live controlled text" (:566): how the approved immutable policy file reaches the machine and NESTED_WORLDS_MODEL_POLICY.
  4. The NESTED_WORLDS_TEST_DATA_USE row (:516), which currently says "A no-provider watch must have no provider credentials set".
  5. Item 7: production section 3 :248 already says "Mint your own key at once" and section 6 (:956) documents minting. If no numbered deploy step mints the first key, turn the :248 note into a numbered section 3 step. Otherwise record item 7 as already met.
  Never mint keys in CI; keep deploy-staging.yml's no-key rule.
- Cap secrets (item 29): list them with <OWNER: integer> placeholders, and say that each neutral name and its legacy name must be set to the same integer in one `fly secrets set` (fly-deployment.md:1793). The pairs: NESTED_WORLDS_VOICE_DAILY_CALLS with NESTED_WORLDS_ANTHROPIC_DAILY_CALLS, and the same for _PER_USER. Also list NESTED_WORLDS_MODERATION_DAILY_CALLS, ..._PER_USER and NESTED_WORLDS_MODEL_ACTIONS_PER_USER. Check server/ for any further legacy names.
- Tests: tests/test_model_policy.py and tests/test_model_policy_activation.py prove that the example is refused until filled and that the report numbers are correct.

PR G2 - procedure for clearing the latched accounting stop (items 3, 28; ADR-039)
- Write a procedure only: no clearing command, no audit table, no migration. ADR-039:69-70 supplies "no automatic refund or unlatch", and an explicit tool is an ADR-039 "Revisit when" trigger.
- Put it in a new "Clearing the stop" section of docs/development/model-policy.md and in docs/infrastructure/incident-response.md. State plainly what is true on main:
  - The stop is a singleton model_spend_latch row with no reset path (persistence/migrations/0032_model_spend.sql:44-51; persistence/model_spend.py:159-181).
  - A doc-only clear therefore means hand SQL on the volume.
  - An unsettled_startup latch also leaves status='reserved' rows, which re-latch at the next start unless they are resolved.
- Cover:
  - the evidence the operator records before a clear (for example, the provider console spend for the UTC day);
  - that a clear never refunds the day's spend or shortens retention;
  - that a restart or a re-created twin does not count as a clear.
- If a command is needed, write a handoff in the PR body naming the owner approval it needs (an ADR-039 revision and the migration slot). Do not build it.
- Cover the process-local stop. `_settlement_fault` (consciousness/model_dispatch.py:49, :113-125, :337-356) survives a database clear, and the startup unsettled-row check runs once per process. So the procedure:
  1. quiesces dispatch;
  2. reconciles outstanding reservations;
  3. clears the latch row;
  4. restarts the machine;
  5. confirms `python main.py models` / voice-health report not stopped, and that one controlled call settles.
- Write rehearsal steps, including that restart and post-restart settled call, for a separate throwaway Fly app; do not run them.
- Rebase on G1 for model-policy.md.

PR G3 - authenticated live-route probe
You may open it as a draft now, but mark it ready only after Claude's C1 (moderation holds) merges. Its hold assertions use C1's semantics.
- scripts/live_route_probe.py drives the ordinary gameplay endpoints with an acknowledged check key: /speak, /agent/voice, an Act free-text intention, and a moderation-held shared line. It asserts:
  - Success, asserted per endpoint against that endpoint's own response contract:
    - /speak and /agent/voice: HTTP 200 and ai:true. A shared line that passes model classification and reaches live voice creates two reservations, one for task moderation and one for voice.
    - Act free-text intention: the accepted contract, `accepted: true` with a receipt (no `ai` field), and one intent reservation.
    - Every expected dispatch is checked by task. Each one's model_spend_reservations row has:
      - status `settled`, never `uncertain`, `anomaly` or `reserved`;
      - accounted_microusd <= reserved_microusd;
      - usage_json carrying prompt, completion and cached-token counts;
      - a resolved_model in that task's approved resolved_models.

    Report any `uncertain` row as a failed ADR-035 requirement 4 (tests/test_model_dispatch.py:469-480 shows a usable reply can leave one).
  - Hold, as separate cases using C1's semantics:
    - (a) An unclassified shared line, or the AI kill switch on, the dollar ceiling spent, or a classify / model-action cap spent: shared Speak and agent voice return HTTP 200, moderation.HOLD_LINE, held:true, ai:false. Ideas and profile publishing return 422 IDEAS_HOLD / PROFILE_HOLD.
    - (b) Quiet failure: only the voice cap spent, with classification still succeeding. /speak and /agent/voice return HTTP 200, ai:false and guard.QUIET_RESPONSE (handlers.py:1262, :1355, :1572, :1656), with held absent or false. The successful classification leaves one settled moderation reservation; assert that row and the absence of any voice reservation.
  - With the kill switch on, a sincere identity question still gets the consciousness.honesty answer: HTTP 200, ai:false.
- It refuses any non-temporary world. Direct --probe stays refused in controlled mode.
- tests/test_live_route_probe.py runs it against a local controlled server with a fake Chat Completions endpoint, reusing the tests/test_openai_compat_provider.py fixtures.
- Runbook: edit only the section 8 checklist bullet "Model-state and gameplay checks" (fly-deployment.md:1695; section 8 has no model-state heading). Keep the phrase "authenticated live-voice probe" there true, because Claude's teardown text cites it. Rebase on G1.

PR G4 - backup job in a main-only environment (owner decisions O7; added after Codex's review of #182)
- Problem: the backup workflow reads secrets.FLY_API_TOKEN (.github/workflows/backup.yml:43) and needs `flyctl ssh console` and `flyctl ssh sftp get` (:95-108). A token that can do that can read testers' chat on the twin, and a repository secret is readable by a workflow on any branch (fly-deployment.md:344-351).
- Change: add `environment: backup` to the job, with deployment branches main only, so cron and dispatch runs from main keep working.
- Secrets: the environment holds FLY_API_TOKEN and every ENFOLDED_BACKUP_S3_* secret, both the write pair and the read-only list pair. Between them they can read every snapshot, and the write pair can delete them. Today all of them are read only in the one `backup` job.
- Docs: update docs/infrastructure/backup-bucket.md's settings table to say "`backup` environment secret" and to tell the owner to delete the repository copies.
- Token: check whether a Fly token with SSH and sftp but no deploy authority exists (`fly tokens create --help`). Record the result as verified or unverified; prefer that token if it works.
- Ordering: open this before the twin collects any participant text. It touches deployment, so it waits for the owner's read.
- Tests: tests/test_deploy_staging_workflow.py and any backup-workflow reader that the rg search finds.

Non-scope for all four PRs:
- frontend/ and static/app/ (Codex holds the bundle).
- Status documents (docs/CHANGELOG.md, docs/roadmap/README.md, beta-launch-checklist.md).
- Any ADR Status line: ADR-035 and ADR-039 stay Proposed until the owner accepts them.
- The watch kit; fly-deployment.md "Teardown before launch" and "Participation notice" (except row :516). These are Claude C2's.
- server/moderation.py (Claude C1).
- Working rules (AGENTS.md, .claude/, the PR template, the rule guides).
- New endpoint or command logic in server/handlers.py or main.py.
- Migrations.
- Committing a real filled policy, real model ids, prices or amounts.
- Next batch, not now: item 18 presence rows, the backup bound-proof tool, the dispatcher handoff, AI-on soak mode.

Verification: behaviour tests, not string-presence checks. Use focused suites while iterating, then run ./scripts/check.sh before marking ready. G1, G3 and G4 change code or workflows. G2 is Markdown under docs/ and may use the documentation-only test-run rule: run the two named tests, search for and run the document readers, validate relative links, and stay in draft until CI is green on the exact head SHA.

Records:
- One changelog fragment per PR in docs/changelog.d/, named after the lowercased branch, with Status: lines (for example S2, E2, M4 evidence), the actual checks, and anything unverified.
- Run the irreversibility check on the real diff. Spend limits, the provider data destination, authentication (key mint) and the deployment runbook all wait for the owner's read.
- Give Claude a one-line watch-kit pointer in each PR body rather than editing the kit.

Process:
- Draft PRs. Mark ready only after checks pass, then request the one Copilot review on the final commit.
- Answer findings in their threads, ending with your footer. Claude Code does the executing review.
- Never merge, enable auto-merge, deploy, spend, run anything against a live provider, set secrets, or recruit.
- Stopping points: wherever the endpoint/vendor, signed data-use note, model ids, USD amounts, ledger retention, cap integers or Fly account are needed, stop at a named placeholder (for example "<OWNER: USD/day per participant for route voice>") and list the exact missing input in the PR body.
```

## 6. Owner's own batch (Mark only), ordered by what it unblocks

*Decided on 2026-11-20:* each item below has an adopted recommendation in
[the 20 November owner decisions](owner-decisions-2026-11-20.md) (O1 to O17).
The table is kept as planned.

| # | Action | Unblocks | Exact form of input |
|---|---|---|---|
| O1 | Say "go" on this batch. Say who owns ADR-036 batch 1b: Codex built 1a (#170), but the puzzle rule is server-side. Confirm the queue size: six PRs will wait on your read, while the adopted item 45 limit is three (not yet a working rule). Either allow it or name which three go first. | Agents start; bundle queue after X2 | "1b → Codex/Claude Code"; "queue: allow all" or a named order |
| O2 | Fly account and billing; `fly tokens create deploy -a enfolded-staging`; GitHub `staging` environment (main-only) with `FLY_API_TOKEN_STAGING`; first terminal deploy (§3a steps 1–5); mint the check key per §3a step 5 (:368-377) from a terminal | Every live run (G3 probe, soak, stop rehearsal); hosted S4 18+ proof; Codex hosted smoke | done / not done; key never minted in CI |
| O3 | Choose the watch endpoint and vendor; accept ADR-035 for that one endpoint; sign the L4 data-use note; name the model ids | Filling G1's policy; the G3 live run; the vendor name in the notice and in L5 | Endpoint URL + vendor; signed note reference; ids for voice, intention and moderation; staging-only key set with `fly secrets` |
| O4 | Confirm amounts after reading G1's reservation report | Committing and approving the policy file | USD/day global (start $15); USD/day per participant (start $3); provider console limit (start $150); `ledger_retention_days` (integer ≥ 2) |
| O5 | Set the call and cap integers as deploy secrets (item 29), each neutral name and its legacy name to the same integer in one `fly secrets set` | C1 holds behave as intended; G1 runbook | `NESTED_WORLDS_VOICE_DAILY_CALLS` + `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` (~1,000); both `_PER_USER` (150); `NESTED_WORLDS_MODERATION_DAILY_CALLS` (2,000); `_PER_USER` (60); `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` (200) |
| O6 | Notice and community-policy values (item 6) | C2 placeholders; twin first boot | Contact address read daily; twin destroy date; provider name; country (adults 18+); `backup_notice` wording |
| O7 | Bucket account and the delete-lock definition (item 12) | C2 teardown step; backup proof; P3 | S3-compatible bucket + both key pairs, bucket and endpoint as `backup` environment secrets (G4); the backup job's Fly token in the main-only `backup` environment (G4), never a repository secret; repository **variable** `ENFOLDED_BACKUP_REQUIRED=true` (`.github/workflows/backup.yml:22,46`); one sentence on what the 7-day delete lock counts from; whether the bucket is versioned |
| O8 | Name the second operator (item 31: "named before recruiting"), then testers and dates (item 5, by 11 Dec 2026) | Watch kit; capacity rehearsal | One trusted adult; 2–3 adult tester names; session dates; desktop Chromium |
| O9 | Approve G2's stop-clearing evidence rule and choose the mechanism: the documented hand-SQL clear, or an ADR-039 revision for an audited command (which needs a migration). Then run the ADR-039 rehearsal on a **separate throwaway app** and accept or hold ADR-039. | AI-on watch survives a latch; required before any live route on a kept world | "Clear requires: <evidence>"; "hand SQL" or "revise ADR-039"; rehearsal date; ADR-039 accept/hold and which PR records it |
| O10 | Approve the old map's named path in X2 (default `/map`, kept until the cohort read-out). Confirm or replace X1's reading of "shared React Map view". | X1/X2 merge | In-PR comments |
| O11 | Read the irreversibility checks and merge one PR at a time: C0, X1, C1, C2, G1, G4, X2, G2, G3. C1 must come before G3; G4 before the twin collects participant text. | Everything downstream | Per-PR merge instruction (auto-merge never enabled) |
| O12 | At deploy: install the approved community policy and model policy (validated offline with `community-policy --check` and `model-policy --check`; loaded at restart via `NESTED_WORLDS_COMMUNITY_POLICY` and `NESTED_WORLDS_MODEL_POLICY`, plus `NESTED_WORLDS_DISABLE_AI=0`); verify `/community`, `/participation` and `ai: true` with the check key; then revoke it | Watch entry requirements 4 and 5 on the twin | done / not done; name the deployed commit (feeds Claude's F2 evidence record) |
| O13 | Operator runs: G3 probes live; single-grader rubric run (item 27, a recorded deviation; isolated from the twin, because controlled mode refuses eval wrappers); 3-client capacity rehearsal (three distinct rehearsal keys); block/unblock; sanction suspend/lift; `main.py redact`; urgent escalation; twice-daily checks of open and acknowledged reports; `fly machine stop/restart`; `beta_metrics.py --days 1`; operator-key entry demands the 18+ acknowledgement | Watch entry requirements 4–7 | Dated log in the private record |
| O14 | Observability and alerts: `SENTRY_ENVIRONMENT=staging`, then `SENTRY_DSN`; alert address; scheduler service and a separately hosted freshness check; uptime checker; who holds the dispatch credential (items 11, 13) | B1/B3/P5; Grok's next-batch dispatcher handoff; the 7-day proof on the twin | DSN secret; one email; service names; "fine-grained token" or "GitHub App" |
| O15 | Records only the owner can supply: the 15 Nov decision page (item 42, the Version 4 record AGENTS.md cites); the issue #89 hold note; Copilot budget if it is spent | Citations in records; Copilot tier | File or text; GitHub comment; budget setting |
| O16 | Set up the next agent batch: (a) restate the ADR-041 re-pin approval **inside** the naming PR after seeing the exact pin diff and the D4 comparison; (b) supply or authorize re-deriving the puzzle design record draft (item 23) and judge the samples (A10, D6, D10 held); (c) answer ADR-037 question 5, second half: is an AI traveler's honesty answer kept, including with AI off and for a repeat within ten minutes (§5 item 18 / item 40; this blocks the ADR-037 chat batch); (d) request the working-rules PR and approve its three wordings (live presence, agent-solve covenant, ADR-038 D8; items 44, 45); (e) ADR-038 B2 salts | Claude's next batch; ADR-036 batch 2; ADR-037 chat batch; salt B1 production audit | In-PR approval comment; doc or "re-derive"; Q5 answer; explicit working-rules request; salts set as `fly secrets` (staging first) |
| O17 | Recruit the watch newcomers. Admission (playable keys) waits for every applicable Watch requirement's evidence against the O12 commit, including X2, L5, F2, G3 live probes and O13. At the watch read-out: declare world status (item 10), sign the exception list (item 37, Y4/Y6), set the cohort start date (item 39), choose the cohort model route (item 24), confirm or change the playtest tripwire (item 38), and answer yes or no on alignment (§3). Then: cohort membership, cohort device list (Y5), terms page (item 36), and the 8–12 cohort start record in `docs/roadmap/README.md`. | End of the delivery priority; the cohort | Names; signed declarations; dates |

## 7. Explicitly deferred

| Item | Reason |
|---|---|
| ADR-041 naming (re-pin 1, migration 0034, client) | Cohort gate, not Watch. Needs the bundle after X2, the free migration slot and the owner's in-PR pin approval. Next Claude batch, after salt B1. |
| ADR-038 salt B1 | Cohort (before the first production boot). Touches `fly.toml`/`deploy.sh`, which overlap Grok's runbook edits this batch. Next Claude batch, before naming (both touch `puzzles/generators.py`). |
| Records hygiene (items 21, 33, 15) | Cohort. Item 21 collides with ADR-036 1b in the handler; sequence it once 1b has an owner. |
| ADR-036 batch 1b and batch 2 | Cohort. 1b needs the bundle and an owner (O1). Batch 2 waits for the agent-solve covenant wording in the working-rules PR. |
| Puzzle design record (item 23) and redesign (re-pin 2) | Waits for the owner's draft and sample judgment. The redesign follows naming. The watch is not held for it. |
| Item 35 and ADR-037 batches 2/3a | Cohort. Need the bundle, the working-rules rewording and the answer to ADR-037 Q5. |
| L5 AI-disclosure UI | Watch-applicable (requirement 1 inventory, checklist :72, :287 "Not started"). Next on the bundle directly after X2. A disclosure that names the vendor waits for O3. |
| Selected-commit evidence record (F2 schema-33 wheel smoke) | Needs the merged batch and the owner's chosen commit (O12). Next Claude batch. |
| Clearing-stop command / audit table | Only if the owner chooses an ADR-039 revision in O9. Needs the migration slot. |
| Item 18 presence rows; backup bound-proof tool; dispatcher/alert handoff; AI-on soak mode | Grok's next batch. The bound-proof tool should start before the twin's 7-day run. |
| Working-rules PR (items 44, 45; ADR-019..022 pointer) | Only when the owner asks for it (single-writer 4). It never rides inside a feature. |
| Y4/Y6 accessibility, Y5 cohort devices, L2 terms link | Wait for the owner's read-out exceptions, device list and terms page. |
| Era materialization (item 16), PixiJS-dependent work, any new feature or abstraction | Not justified under the delivery priority until the cohort starts, unless the owner directs it. |

## Verification notes

**Corrections applied, with evidence:**

1. **C1 and the e2e suite.** C1 may not touch `frontend/e2e/`, and local or no-classifier runs keep publishing clean lines. Evidence: `frontend/e2e/server.js:17` sets `NESTED_WORLDS_DISABLE_AI=1`, and Ideas/profile specs would otherwise break.
2. **C1 code citations and hold text.**
   - The escalation point is `screen()` :207; `needs_model` :269 is a predicate.
   - The honesty dependency is named (`handlers.py:251`, `:1291`, `:1605`).
   - The chat (`websocket.py:659`) and puzzle (`handlers.py:2175`) surfaces are named.
   - "A spent voice cap holds nothing" is added.
   - Hold responses are corrected to HOLD_LINE/200 for Speak and agent voice and IDEAS_HOLD/PROFILE_HOLD/422 for Ideas and profiles, replacing "quiet or pace line".
3. **C2 community policy.** No enabled watch policy is committed; it becomes a documented template with temp-file tests (ADR-040:53-56, `community_policy.py:109-112`, runbook :443-462). O12 now installs a private policy file.
4. **C2 runbook scope.** Its scope is now the teardown section (:853-886) plus the participation notice section (:485), excluding row :516, which goes to G1. This replaces the contradictory "non-scope §3a" wording.
5. **C2 teardown wording.** It now carries the versioned-bucket caveat (item 12). "Serves" adds Watch req. 1 (checklist :72).
6. **X2 is an authentication change** (`_is_public_asset`, invite gate :602). It moves to the owner-read list, and the path is cited as :621-641.
7. **X2 citations.**
   - Test lines corrected to `test_guard.py:1001` and ~878-890; `test_frontend_contract.py` reads the file.
   - The unverifiable "14 specs" count is replaced by the verified 11 + 4 list (expressive is in both).
   - `static/journal.html:3` added.
   - The notices file name corrected to `THIRD_PARTY_NOTICES.txt` (both copies).
   - README route lines are edited directly, per AGENTS.md item 1; the draft wrongly said they go in as `Status:` lines.
   - The old map is kept until the cohort read-out, and the owner approves the path (O10).
8. **X1 import.** The import is cited as `frontend/src/main.jsx:3`, not SceneView. X1 must state its reading of "shared React Map view" for the owner and show it does not duplicate SceneView's navigation surface.
9. **G1.**
   - Field list corrected (`input_bound_kind`, `input_bound_evidence`, `adapter`, `timeout_seconds`, `options`, `limits.*`).
   - Step 7 and row :516 added.
   - Legacy cap names added, also in O5 (runbook :1793).
   - Key-mint wording now checks :248 / §6 :956 before adding a step.
10. **G2 is procedure-only.** No command, audit table or migration. The latch facts are stated (`0032_model_spend.sql:44-51`, ADR-039:69-70), and the mechanism choice goes to the owner (O9). The draft's "migrations only if…" wording is removed throughout.
11. **G3.**
    - It depends on C1, not G1, for code; G1 is only a runbook rebase.
    - The runbook scope is bounded to the §8 checklist bullet at :1695. I verified there is no model-state heading: §8 is "Launch window" at :1616.
    - Its hold assertion now uses HOLD_LINE.
12. **Authority fixes.**
    - Agents never set secrets (the C1 non-scope is corrected).
    - No agent changes an ADR Status line (the draft sent ADR-035/039 through C0).
    - C0 gets Codex's executing review if it changes a test file.
    - C0 applies only the fragments' Status: lines, folds whatever is on main at its final rebase, and lists other mismatches.
13. **Owner list.**
    - Added: the queue-size confirmation (item 45), approval of the map path and design reading, ADR-037 Q5 second half, and the four missing read-out decisions.
    - Moved: the second operator now comes before recruiting.
    - Corrected: `ENFOLDED_BACKUP_REQUIRED` is a repository variable, not a secret; O2 mints the check key per §3a step 5.
14. **Takeaway.** It no longer claims that only owner inputs remain: L5 and the F2 record are named.
15. **Collision rules** added for `tests/test_guard.py` (C1/X2), for keeping the "step 6" label and the §8 probe wording so the teardown cross-references stay true, and for `main.py`, which is now only G1's.

**Still unverified:**
- The incumbent provider's Chat Completions endpoint behaviour; G1 records it.
- Whether Vite imports `static/d3.v7.min.js` cleanly; X1 checks first.
- Whether the scene renderer depends on PixiJS beyond `main.jsx:5`; X2 checks before removal.
- ADR-005 line references (~20, ~74).
- The exact runbook line numbers inside the §3a steps 6–7 (about :398-423).
- Whether any C0 status edit needs a row-status change that touches the count test.
- Whether further legacy cap-secret names exist beyond the voice pair; G1 checks `server/`.

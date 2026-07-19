# Enfolded — Expert Ensemble Evaluation (2026-07-19)

Method note: this evaluation convenes **eleven expert personas** — critics,
publishers, partners, players, designers, and production specialists — and runs
each against the shipped code and record, asking two questions: *is the project
set up to achieve its objectives and realize its vision,* and *is the player
experience rich and complete across the key experiences* (navigation,
interaction, visual, auditory, puzzle, presence, persistence). It complements
the two prior audits without repeating them: the 2026-07-04 deep evaluation
judged map against territory, the 2026-07-18 critical evaluation judged the
record against itself; this one judges the *experience* against the audiences
it must eventually satisfy.

Everything load-bearing below was verified in this session, not quoted from
prior docs: the full suite was executed (789 passed + 1 skipped here — the
skip is the `websockets` dev extra absent in this sandbox; 789 + its 3
conformance tests = the advertised 792), the canonical seed-42 world was
regenerated (4,439 nodes, per-level counts matching the freeze pins), a
puzzle census was computed across all 4,439 nodes, fallback voices and bible
sizes were sampled (world bible 18,456 chars, agent bible 17,825 — both past
the 4096-token cache minimum), and the live server was run to test one
suspected defect by execution (§ the register finding, below). Three parallel
read passes covered the frontend/clients, the world/puzzle/causality systems,
and the agents/voice/server/ops layers in full.

**The one new defect found while convening the ensemble, up front:**
`/register` — the self-service invite flow shipped in #66 — serves its entire
registration logic as an inline `<script>` (`static/register.html:62-101`)
under a `Content-Security-Policy: script-src 'self'` with no `unsafe-inline`
and no nonce (`server/handlers.py:464-471`; header confirmed by running the
server and fetching the page). A CSP-enforcing browser blocks that script:
the invite parameter is never read, the submit handler never attaches, and
the flow silently fails. Every other page avoids inline scripts for exactly
this reason (it is why `nodeart-global.js` exists), the E2E smoke suite
covers `/` and `/app` but not `/register`, and the repo has already shipped
one CSP-killed surface (the PixiJS blank-scene P0). Operator-minted
`invite mint` URLs are unaffected. Fix is mechanical (externalize the script;
add `/register` to the smoke suite) and pre-launch.

---

## 1. The ensemble

Composition principle: every audience the project must eventually convince
gets a seat, and every key experience named in the brief gets at least one
persona whose job is to judge it. Five benches:

| # | Persona | Bench | What they judge |
|---|---------|-------|-----------------|
| 1 | The ambient-games critic | Critics & market | Does the thesis land as felt experience; emotional arc; comparables |
| 2 | The boutique-publisher scout | Critics & market | Audience, positioning, retention economics, signability |
| 3 | The platform partner (Claude-ecosystem evaluator) | Critics & market | AI-native craft: prompt engineering, cost, safety, honesty of AI claims |
| 4 | The systems designer | Design | Core loop, entropy/restoration economy, causality as gameplay |
| 5 | The puzzle designer | Design | Content quality, variety, fairness, ceiling; co-op; seals and composition |
| 6 | The narrative director | Design | Voice, registers, memory, fiction covenant, chronicle as story |
| 7 | The art director | Senses | Generative art, style system, scene readability, client disparity |
| 8 | The audio director | Senses | The soundscape: composition, integration, discoverability |
| 9 | The first-session player (UX researcher composite) | Players | Onboarding, navigation, wayfinding, accessibility, device coverage |
| 10 | The returning resident (retention persona) | Players | The multi-day arc, presence, co-op, community and safety as lived |
| 11 | The technical director / live-ops producer | Production | Readiness, test culture, operational risk, launch posture |

Two perspectives are deliberately folded rather than seated: accessibility
rides with persona 9 (it is a first-session concern here, not a separate
compliance track), and trust & safety rides with personas 10 and 11 (the
moderation/redaction machinery is built; what remains is lived-experience
judgment).

---

## 2. Bench I — Critics & market

### 2.1 The ambient-games critic

**Verdict: the thesis is now mechanically true — and the launch posture hides
most of the evidence.** Judged against the games this one actually resembles
(Proteus's deterministic islands, Kind Words' gentle co-presence, Journey's
anonymous encounter, Outer Wilds' knowledge-as-key), Enfolded has done the
hard thing those games never attempted: a *persistent, shared* contemplative
world that runs unattended (`server/heartbeat.py`, 180s ticks, zero API
spend), where consequences travel visibly at world speed (12s/hop staged
cascades), and where the places themselves remember you by name across
sessions (per-(node, speaker) transcripts). The 2026-07-04 verdict —
"beautifully documented ledger wearing the costume of a living world" — no
longer holds; the world demonstrably moves.

But the critic reviews the session a player actually has, and at launch that
session is: the D3 tree explorer (the generative art reduced to a sidebar
sigil), sound off behind a small toggle, fal.ai imagery absent (explorer
never calls `/image`), and the voice — the emotional headline — silent
without a key and budget. Each of these is individually defensible (ADR-005
§3 argues the explorer default well; audio autoplay policy forces a gesture;
quiet degradation is a covenant). Collectively they compound: **quiet by
design becomes quiet by default**, and the first session risks reading as a
handsome tree viewer with poetry attached. The sensory half of the game — the
eleven form families, the mode-shifting soundscape, the composed scene — is
all *present* and all *elsewhere*: behind an alternate client, a muted
toggle, an optional key.

Two smaller aesthetic findings. The path-suffix naming (`Stillcrest
Wastes-111111`, `Veriunon-11111111111`) is determinism made visible — a real
engineering achievement — but at depth it reads as debug output inside the
fiction; an 11-digit tail is a heavy price for O(depth) resolution on every
displayed surface. (Display-side softening is derived at render time and
would not touch the frozen names.) And the subtitle "Nested World
*Adventure*" promises a goal-shaped experience the game deliberately refuses;
the brief's own language — contemplative, quiet, returning-visitors as the
success metric — is the honest register, and the packaging should match it.

**Asks:** (1) let the default surface lead with the senses — hero-size the
sigil, add a one-click in-fiction sound invitation; (2) a display-name
treatment for deep scales; (3) align the packaging with the contemplative
register before critics do it for you.

### 2.2 The boutique-publisher scout

**Verdict: not signable as a commercial game today — genuinely interesting as
an art-project-with-operations, which is a category boutique publishers do
sign.** The scout's checklist: audience, hook, retention, content runway,
team risk.

*Audience:* contemplative multiplayer fiction is a micro-niche, and the
project knows it — the success metric is players active on 2+ distinct days
(`scripts/beta_metrics.py`), not session length. That honesty is rare and
bankable. What's missing is the one-sentence audience definition ("for people
who…") that every pitch meeting opens with; the beta brief describes the
object, not the person.

*Hook:* the deterministic-screenshot property is a genuinely novel trust
device — "any capture is reproducible; run seed 42 and check" — and no pitch
the scout has seen can say that. But the brief ships with four
`PLACEHOLDER-*.png` slots where the captures should be. A pitch whose
central claim is visual reproducibility, with no visuals, undersells itself
exactly where it is strongest.

*Content runway:* the scout's sharpest structural finding — **the content
ceiling freezes at launch.** The identity banks freeze permanently at first
production deploy (CLAUDE.md one-way doors), and the puzzle digests are
pinned at epochs 0–2, so the puzzle variety the beta launches with is,
for existing nodes, the variety forever; renewal re-seeds *within* existing
families, never adds new ones. See §3.2 for the numbers. This is survivable
for a 20-person beta and a real constraint for anything larger; it deserves
a conscious pre-launch decision, not an implicit one.

*Team risk:* a solo project with an unusually strong record (792 tests, two
adversarial self-audits, ADRs with revisit triggers) — but a bus factor of
one, and a two-client maintenance tax the repo itself measures at ~350-400
duplicated lines with a 15%-executed parity harness.

**Asks:** (1) capture the four placeholder assets from seed 42 before any
outreach; (2) write the audience sentence; (3) put the frozen-ceiling
decision in writing (ADR or CHANGELOG) so a partner reads a choice, not an
oversight.

### 2.3 The platform partner (Claude-ecosystem evaluator)

**Verdict: one of the most disciplined Claude cost-and-safety postures this
evaluator would see at beta scale; the AI's *role* is narrower than the
project's language historically implied — and the docs have now mostly caught
up.** The craft list is long and verified: both bibles engineered past the
real 4096-token Opus cache minimum with a startup guard
(`cached_prefix_meets_minimum`, `warn_if_cache_ineffective` — the 1024-token
trap this repo shipped twice, now fenced); per-call cache-usage logging;
global + per-credential daily budgets checked before spend; a concurrency
semaphore protecting org-level RPM; two-tier moderation that costs zero API
calls on clean input, escalates ambiguity to a deliberately-uncached Haiku
classify on its own budget line, and fails open so a classifier outage never
censors a player; render-time delimiting of recorded speech framed as
"testimony, never instructions" (the P3 injection seam); and a model bump to
`claude-opus-4-8` reasoned in ADR-005 with a staged live-voice probe. This is
a case study in running a consumer Claude product on single-digit dollars a
day, and worth publishing as one.

The honest gap: **Claude never acts, initiates, or persists as an agent.**
Every Anthropic call in the codebase is a human-pulled request/response —
node voice (`/speak`), agent voice (`/agent/voice`), moderation classify.
The walking cast is a deterministic FSM with authored banter (zero calls
by design — a *good* design), voiced by Claude only when dialed. The doc
sweep has largely fixed the language ("Claude-adjacent"), and the blur
covenant was re-scoped honestly. What remains is opportunity, not
misrepresentation: the world has budget headroom (500 global calls/day
against ~100 expected) for one bounded experiment in Claude-initiated
life — e.g., a single budgeted call per world per day in which a node with
fresh history composes an opening line for its next visitor.

**Asks:** (1) run the post-launch Sonnet 5 A/B as ADR-005 schedules; (2) one
budgeted "the world speaks first" experiment; (3) write up the cost
engineering — it is reference material.

---

## 3. Bench II — Design

### 3.1 The systems designer

**Verdict: the causal economy is real, closed, and legible — the rare "living
world" claim backed by tests — with three places where the loop thins out.**
The economy: entropy decays the world (destabilizer agents emit
STRUCTURAL_CHANGE/DANGER_ALERT on heartbeat ticks), eleven scale-native verbs
restore it (each the counterpart of a decay path), decay on solved nodes
re-arms their puzzles (renewal epochs), and every act rides one standard rail
(`causality/wiring.py`) shared by players, agents, heartbeat, and CLI. The
scales genuinely play differently: twelve laws of physics route cascades
(measured: the same solve reaches 6 nodes in a Newtonian universe, 22 in an
Inverted one), cosmic verbs mature on deep time (2–30 min), 118 entangled
particles resolve as pairs, ENFOLD puzzles make the nesting itself content.
This is the project's signature system and its strongest answer to "is it set
up to realize the vision."

Where it thins: **(a)** material change requires event strength ≥ 0.3
(`multiverse/effects.py::EFFECT_THRESHOLD`), which at 0.5/hop dampening means
substance changes at the origin and roughly one ring out; the farther rings a
player watches arrive carry ripple and history only. The 12s/hop theater is
honest about *reach* but most of what arrives is atmosphere, not
consequence — defensible, worth knowing. **(b)** The seal gates only
movement (scope-decided 2026-07-18): from outside a sealed subtree you can
still `/speak`, `/act`, and solve its puzzles, and `/world` ships its
contents — the door is real for walking and notional for everything else.
**(c)** Goal scaffolding is two levels deep: constellations exist only at
Galaxy ("systems") and Region ("rooms"); the nine other scales offer no arc
above the single node. And one live inconsistency: FSM agents build epoch-0
puzzles regardless of renewal, so post-renewal they roll against a puzzle
that no longer exists — while their solves still feed the re-arm epoch
condition.

**Asks:** (1) close the agent/epoch mismatch; (2) extend constellation-style
arcs to at least one more scale pair post-launch; (3) record the
threshold-vs-theater trade-off (a one-line ADR note) so a future tuner knows
it was chosen.

### 3.2 The puzzle designer

**Verdict: mechanically exemplary, content-capped — and the cap becomes
permanent at launch.** The fairness engineering survives professional
scrutiny: server-validated answers, measured zero leaks (answer never in
prompt/hints/shipped properties), graduated hints, more attempts for harder
puzzles, per-node difficulty spread flat across all scales (census:
1,151/1,075/1,176/1,037 across tiers 1–4), reproducible per node for co-op,
pooled room sessions that rehydrate across deploys. Nobody ships puzzle
infrastructure this careful.

The content, censused across all 4,439 nodes: **three decode families —
anagram (1,184), pattern (1,159), cipher (965) — carry 74% of the world.**
Distinct answers: 1,037 (~23%); the most common answer, "16", answers 109
nodes ("64" 103, "48" 101) — a numerate player can farm the pattern tail.
Hand-authored content is 41 puzzles total (3–6 per level, none at Region),
throttled to read as rare treats — appearing on ~47 nodes. The genuinely
novel families are the world-reading ones: LOCK (1,064 — answer is a property
one scale up), lineage sigils (517 — an acrostic assembled from three
enclosing scales), bonds (447 — chemistry read from the parent molecule),
enfolds (19 — the nesting itself). These are the puzzles only this game could
have, they teach the world's structure, and they make players *move* — and
they are underexposed: 66 of 165 locked rooms don't serve the LOCK their
`locked` fiction promises (the parent lacks a usable key property, so the
seal works but the travel-key story doesn't), and the guide leads with the
decode families.

The strategic finding echoes the publisher's: the banks freeze at first
deploy and puzzle digests are pinned through epoch 2, so **this census is the
permanent puzzle experience for existing nodes** unless a sanctioned
evolution path is designed. One exists in the current architecture's grain:
new families could be gated to renewal epochs the pins don't yet cover
(epoch ≥ 3), so frozen surfaces stay byte-stable while renewed nodes draw
from a wider set — the same trick the renewal system already plays with
content, applied to families. Deciding this *before* launch costs a
paragraph; after launch it is a covenant negotiation.

**Asks:** (1) the frozen-ceiling decision memo, naming the epoch-gated
escape hatch; (2) lead the guide with LOCK/lineage — the signature, not the
warm-up; (3) post-launch, examine the numeric answer tail.

### 3.3 The narrative director

**Verdict: the writing is the best material in the project, it now actually
reaches players — and the world still never speaks first.** What shipped
since July 04 answers most of that audit's harshest experiential findings:
per-scale registers *and* deep lore for all eleven scales, real
per-(node, speaker) transcripts keyed to the credential (same-name strangers
stay strangers), memory with content on both sides of the exchange, causal
pressure coloring the voice, and — the covenant this evaluator would teach
from — **failure that stays in fiction**: eleven authored lines of silence
(sampled live: "The land lies quiet from horizon to horizon. Whatever watches
from the terrain does not speak."), an authored image-quiet line, an authored
pace line for 429s. The era-named chronicle ("The Vigil of Emberglass") turns
the database into scripture, which is exactly the register the premise wants.

The structural silence that remains: every utterance in the game is
player-pulled. No node greets an arrival, no agent hails a passer-by, nothing
knocks. For a world whose fiction is "you are witnessed" — nodes literally
told "you are not alone in time" — the absence of a single world-initiated
line is the last un-kept promise. Even one authored (non-API) arrival line
per node family, or the partner's budgeted speak-first experiment, would
close the loop the fiction opens. Secondary: the blur covenant's re-scoping
("the chronicle blurs; live presence may distinguish") was the right honest
move, but it should be understood as a thesis narrowing, not a wording fix —
the travelers panel taxonomizes what the README's concept statement still
romanticizes. And the numeric name suffixes puncture the diction at depth
(§2.1).

**Asks:** (1) one world-initiated moment, authored or budgeted; (2) a
display-name treatment; (3) keep the bibles growing — they are the game's
real script, and the 4096 floor is a floor.

---

## 4. Bench III — The senses

### 4.1 The art director

**Verdict: a real visual identity system, shipped, deterministic, and
demoted by the launch posture.** `static/nodeart.js` is the strongest kind of
game art direction: eleven per-scale form families (folds, filaments, spiral
arms, orbits, horizon limbs, ridges, panels, sigils, bond graphs, shells,
probability speckle), one deterministic module shared verbatim by both
clients, with world state *bending* the art — causal pressure saturates and
jitters, stabilization draws a halo, corruption slice-glitches, danger
vignettes, activity etches tally marks, inscriptions cut five-bar strokes.
History is legible in the image at zero API spend, and any screenshot is
reproducible. The adaptive style matrix for fal.ai imagery is fully live
(all seven design-doc rows), correctly cache-keyed on a style signature, and
correctly subordinated: a translucent wash *over* the always-present art,
never a dependency.

The demotion: at launch, invitees land on the explorer, where this system
renders as a sidebar sigil canvas while the composed scene — art base, image
wash, hotspot plates with affordance studs, presence markers, event
transients — lives in `/app`, which the guide names as an alternate, which
fetches only depth 6 (deep nodes are approximated, not reached), and which
has no responsive CSS for phones (fixed 65%/300px flex split). ADR-005's
risk logic is sound; the cost it accepts — "hides the product's visual half
from first impressions" — is exactly what this bench exists to protest.
The cheapest partial remedy doesn't touch the posture: make the sigil the
explorer's hero element rather than a sidebar thumbnail.

**Asks:** (1) hero-size the sigil in the explorer; (2) capture the
eleven-family art grid for the brief; (3) post-launch, the `/app` mobile
pass and depth parity ADR-005 already gestures at.

### 4.2 The audio director

**Verdict: the most sophisticated unheard system in the project.** The
soundscape (`static/nodesound.js`) is genuinely *composed*, not ambient
filler: harmonic mode chosen from the node's condition (danger darkens to
Phrygian, corruption to insen, stabilization brightens to Lydian), root
pitch-class derived from the art's hue so a place sounds the color it looks,
a three-voice pad breathing through minutes-long filter weather, atmosphere
properties shaping the noise band, a scale-aware generative music box
(cosmic bells every ~9–16s, quantum sparkle every ~2–5s), and — the touch
this evaluator would steal — *audible history*: activity adds tape wow,
corruption gates dropouts, inscriptions get a two-note knock motif. Eleven
musical-contract tests plus an e2e that builds the full WebAudio graph in
real Chromium. Deliberately unfrozen (derived at listen time), so it can be
retuned forever — the one sensory surface with an open ceiling.

And almost nobody will hear it. It is off by default (autoplay policy makes
*a* gesture mandatory — but the gesture shipped is a small toggle, not an
invitation), the player guide's how-to-play page does not mention sound at
all (verified: zero occurrences of "sound"/"audio" in `static/guide.html`),
and the terminal client has no audio. A system this good, discoverable only
by noticing a button, is a mix decision no audio director would sign.

**Asks:** (1) an in-fiction listen invitation, once per session ("the world
hums — listen?" is one authored line and satisfies the gesture requirement);
(2) a sound section in the guide; (3) keep it unfrozen — it is the safest
place to keep improving the game after launch.

---

## 5. Bench IV — Players

### 5.1 The first-session player

**Verdict: the first session is thought-through end to end — invite, intro,
deterministic mid-world drop-in, guide — and one of its two front doors is
broken.** The good path is genuinely good: a one-click invite URL, an intro
modal with three verbs and a promise, a drop-in at a node with places to go
both up and down chosen from your name (determinism you can feel in the
first three seconds), a working keyless experience that degrades in
character, cross-device resume keyed to the credential, and a mobile-capable
default client. Accessibility groundwork is real: `prefers-reduced-motion`
honored in both clients, `role="img"` + aspect-built labels on the art
canvases, `aria-pressed` on toggles, CSP-clean event wiring.

The frictions, in severity order: **(1)** the `/register` CSP defect (header
finding, top of this doc) — a self-service invitee hits a page that silently
does nothing; this is the single worst possible first session and it is the
*new-player* path specifically. **(2)** The explorer still hands a first-time
player the engine room: Seed / Depth / Breadth inputs and a Generate button
in the header — the 2026-07-04 "admin console wearing a theme" finding,
softened by the intro modal but still the frame around the fiction.
**(3)** No per-node deep links — a player cannot send "meet me here" as a
URL; position sharing rides only on the travelers panel. **(4)** Keyboard
navigation of the tree itself is absent (mouse/click only). **(5)** If the
cohort's key or budget hiccups, the first session is voice-silent by design —
the runbook's live-voice probe (`"ai": true`) is the safeguard; it must
actually be run.

**Asks:** (1) fix `/register` and add it to the smoke suite; (2) tuck the
world-generation controls behind an "advanced" affordance; (3) per-node
deep links.

### 5.2 The returning resident

**Verdict: the return visit is the game's strongest design bet, and the
design mostly keeps it.** What a second-day player finds: their exact node
(cross-device, seal-checked at write time), a world that moved without them
(heartbeat traversals, decay, matured cosmic verbs landing), places that
remember what they said and answered, an era-stamped chronicle to page
backward through, puzzles that may have renewed ("· Renewal 2" — the world
no longer consumes its content monotonically), and constellations that stay
lit forever. The per-user budget (150 Anthropic calls/day) is generous
enough that a heavy resident never feels the meter. The safety floor for a
permanent record is genuinely built: two-tier fail-open moderation, content
redaction that preserves mechanics, names bound to credentials.

The honest risks are social density and proof. A 20-person cohort spread
across a 4,439-node world at contemplative pace will rarely co-occur; the
ambient cast carries co-presence most hours, and the runbook's synchronized
onboarding with a shared LOCK expedition is the right instinct — once. There
is no recurring rhythm (a weekly gathering, a cohort-wide constellation
push) to re-concentrate the cohort, and the returning-visitor metric —
correctly chosen — is still a hypothesis with zero data points. One texture
note: the "what changed since you left" story exists (feed backfill of the
last 12 mutations) but is generic; a resident's resume moment wants *their*
delta ("since you left: Tessera passed your room; the Wastes renewed their
puzzle"), which the chronicle can already answer.

**Asks:** (1) a recurring cohort-gathering cadence in the runbook, not just
launch day; (2) a personal since-you-left recap on resume; (3) read
`beta_metrics.py` weekly and let the returning-visitor number govern
phase-2 pulls.

---

## 6. Bench V — Production

### 6.1 The technical director / live-ops producer

**Verdict: launch-readiness engineering far above the norm for a project
this size; the remaining risks are known, mostly accepted on the record, and
two are procedural gates that must actually be walked.** The evidence this
bench weighs: 792 behavior tests (789+1 executed here, delta accounted),
freeze pins covering *both* depths plus epochs 0–2 and verb overlay keys,
a deploy script that refuses to deploy over an unbacked chronicle, an
ADR-ratified staging rehearsal before the permanent world begins, soak-test
numbers on the record (96/96 WS clients, p95 13.9ms, 0 errors), cost caps at
three layers, CI gates for the bundle-freshness and lint classes of drift,
and two adversarial self-audits with closed-out recommendation lists. The
determinism contract held against a fresh adversarial read (three
independent passes this session found zero unseeded entropy in frozen
surfaces beyond the already-recorded heartbeat scheduler).

Open risk register, ranked: **(1)** the `/register` CSP defect — new, real,
launch-path, trivial fix. **(2)** `backup.yml` no-ops until `FLY_API_TOKEN`
is set — the hourly-backup decision (ADR-005 §1) is currently paper until
that secret exists; runbook §8 lists it, and it must precede the first
invite. **(3)** Accepted architecture: single VM, single region, single
SQLite volume; every deploy drops live WS sessions (reconnect + resume
mitigate); `busy_timeout=5000` defends contention with Postgres as the
named trigger. **(4)** `server/handlers.py` at ~1,700 lines carries
routing, auth, the WS loop, co-op, constellations, and entanglement — the
next session's merge-conflict magnet; a post-launch split is cheap
insurance. **(5)** The two-client tax with a 15%-executed parity harness —
scheduled debt (ADR-005), fine, but the schedule should survive contact with
post-launch enthusiasm. **(6)** The meta-risk the 2026-07-18 audit named:
verification decays into prose; the CI-executed share of claims should keep
growing (a `/register` smoke test is this week's instance).

**Asks:** (1) `/register` in the smoke suite; (2) `FLY_API_TOKEN` set and
one dispatched backup run verified before invites; (3) the handlers split on
the post-launch board.

---

## 7. The scorecard — richness and completeness across the key experiences

Ratings: **Rich / Solid / Thin** for richness (how much well-crafted
substance exists); **Complete / Uneven / Gapped** for completeness (does it
reach the player everywhere it should). Evidence inline; benches that drove
each row in parentheses.

| Experience | Richness | Completeness | The one-line truth |
|---|---|---|---|
| Arrival & onboarding | Rich | **Gapped** | Deterministic drop-in + intro + guide is genuinely good; `/register` is CSP-dead for self-service invitees (9) |
| Navigation & wayfinding | Rich | Uneven | Explorer reaches all 11 scales, deepens to travelers, resumes cross-device; `/app` approximates below depth 6, no breadcrumb; no per-node deep links (9, 1) |
| Interaction & conversation | Rich | Uneven | Registers, lore, transcripts, memory, addressable agents — all key-gated; nothing in the world ever initiates (6, 3) |
| Puzzle experience | Solid | Complete-but-capped | Fair, leak-free, co-op, renewable; 74% decode families, 23% distinct answers, ceiling freezes at launch (5) |
| Visual experience | Rich | Uneven | 11 history-legible form families + live style matrix; demoted to a sidebar sigil on the default surface (7) |
| Auditory experience | Rich | **Gapped** | A composed, history-audible soundscape — off by default, absent from the guide, discoverable only by accident (8) |
| Consequence & causality | Rich | Complete | Laws route cascades, staged hops arrive live, deep time, entanglement; material change reaches ~1 ring (4) |
| Presence & multiplayer | Solid | Complete | Travelers panel, pooled co-op, heartbeat cast, restart-proof solves; density at 20 users is the open bet (10) |
| Persistence & return | Rich | Complete | Chronicle + eras + renewal + resume; the metric is right and unproven (10, 2) |
| Fiction & failure states | Rich | Complete | Eleven authored silences, image/pace lines, in-fiction declines; perimeter scoped in writing (6) |
| Production readiness | Rich | Complete* | *pending two procedural gates: `FLY_API_TOKEN`, staging rehearsal (11) |

---

## 8. Where the ensemble converges, and where it splits

**Convergence (four findings, independently reached by 3+ personas):**

1. **The infrastructure has outrun the presentation.** Critic, art, audio,
   and partner all found the same shape: the systems that would most move a
   first-time player — the composed scene, the soundscape, the live voice —
   are respectively behind an alternate client, a mute toggle, and an API
   key, while the default surface leads with a tree diagram. The July-04
   audit's closing instruction ("take the loops that exist and put them in
   front of the player's senses") is *almost* finished: the loops now exist
   and reach the senses — of a player who knows where to look.
2. **`/register` is the one broken front door** — found here, confirmed by
   execution, trivially fixable, and exactly the class of seam (CSP,
   external contract, untested surface) the repo's own blind-spot rule
   names.
3. **The frozen ceiling is the biggest unmade decision.** Publisher, puzzle
   designer, and TD all land on it: launch permanently freezes the puzzle
   experience for existing nodes. The epoch-gated family hatch preserves
   every pinned surface; it costs a paragraph now and a covenant fight
   later.
4. **The honesty culture is a differentiating asset.** Every bench
   remarked on it unprompted: the measured CHANGELOG, the adversarial
   self-audits, the in-doc admissions ("nobody should pitch this as a
   hard-puzzle game"). For partners and critics alike this is the project's
   most unusual property after the determinism contract.

**Splits (real disagreements, left standing):**

- **Client posture.** The art director wants `/app` promoted; the TD and
  ADR-005 hold the explorer default for risk reasons. Resolution proposed,
  not imposed: keep the posture, move the senses (hero sigil, sound
  invitation) into the default surface.
- **Pitch production.** The publisher wants captures and a video; the
  narrative director warns an overproduced pitch contradicts the quiet
  register the game monetizes on. Both agree on the four reproducible
  captures; the video stays contested.
- **Cascade depth.** The systems designer would consider lowering
  EFFECT_THRESHOLD so consequence travels materially farther; the TD notes
  the current setting is load-bearing for overlay volume and the theater is
  honest. Left as a recorded tuning question, not a recommendation.

---

## 9. Ranked recommendations

By leverage per unit effort, launch-relative:

1. **Fix `/register`** — externalize the inline script, add `/register` to
   the Playwright smoke suite. Pre-launch, hours. (Bench 9, 11.)
2. **Walk the two procedural gates before the first invite** — set
   `FLY_API_TOKEN` + verify one dispatched backup run; run the ADR-005
   staging rehearsal including the live-voice probe. Pre-launch, scheduled
   already — this is a "do the thing the paper says" item. (11.)
3. **Decide the frozen puzzle ceiling in writing** — one ADR-004/005
   addendum or CHANGELOG paragraph: either "the launch census is the
   permanent ceiling, accepted," or "new families may enter via renewal
   epochs the pins don't cover, re-pinned deliberately." Pre-launch, a
   paragraph. (5, 2, 11.)
4. **Let the default surface lead with the senses** — hero-size the
   explorer's sigil; add a once-per-session in-fiction sound invitation; add
   a sound section to the guide. Pre- or launch-week, small. (1, 7, 8.)
5. **Capture the four placeholder pitch assets** from a live seed-42 run.
   Whenever outreach begins. (2.)
6. **Give the cohort a recurring rhythm** — extend runbook §8's one-time
   shared expedition into a weekly gathering cadence; read
   `beta_metrics.py` weekly. Launch week onward. (10.)
7. **Close the FSM-agent renewal-epoch mismatch** (agents roll epoch-0
   puzzles post-renewal while their solves feed the re-arm condition).
   Post-launch, small. (4.)
8. **Post-launch experience batch, in this order:** personal since-you-left
   recap on resume; per-node deep links; one budgeted world-speaks-first
   experiment; `/app` mobile pass + parity-harness completion (already
   scheduled); handlers.py split. (9, 10, 3, 7, 11.)

---

## 10. Closing assessment

Asked whether the project is set up to achieve its objectives, the ensemble's
answer is a qualified yes with an unusual shape: the *hard* half — a
deterministic permanent world, truthful causality, durable memory, honest
degradation, launch-grade operations — is done to a standard several
personas called reference-quality, and the *easy* half — putting the game's
own best material where a first session will meet it — is the bulk of what
remains. The player experience is rich in nearly every dimension measured;
its completeness gaps are concentrated at doors and defaults (one broken
registration page, one muted soundscape, one demoted scene view), not in
missing substance. The vision statement's deliberate blur between player,
agent, and world has been honestly renegotiated rather than achieved — the
chronicle blurs, presence taxonomizes, and Claude speaks only when spoken
to — and the project's own record says so, which is why the ensemble, on
balance, trusts it. The launch decision this document supports: fix the
register door, walk the two procedural gates, write down the ceiling
decision — then open the world and let the returning-visitor number answer
the question no audit can: whether the felt experience earns the
architecture.

---

## 11. Irreversibility check (house rule)

This change adds one evaluation document and one CHANGELOG entry. It re-pins
no golden world, adds no migration, and adds no `world_mutations` write
path — none; the diff is docs-only.

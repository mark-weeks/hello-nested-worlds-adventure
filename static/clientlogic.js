// Browser-client rules shared by the no-build D3 explorer and the Vite app.
//
// This file is deliberately a classic script rather than an ES module: `/`
// loads it directly before explorer.js, while Vite imports it for its side
// effect and the small frontend wrappers re-export the same functions. Keeping
// the rules here removes the hand-mirrored entry, badge, and chronicle logic.
(function installClientLogic(root) {
  // A rotated key still belongs to the same named traveler. A different
  // invitation must not inherit the previous traveler's cached arrival.
  function rememberInvite(params, storage) {
    // The server counts Unicode code points. Cutting a UTF-16 surrogate pair
    // would make an otherwise valid invitation fail WebSocket URL encoding.
    const normalize = value => Array.from((value || "").trim()).slice(0, 32).join("").trim();
    const name = normalize(params.get("name"));
    const key = params.get("key");
    if (!key || !storage) return name;
    const previousKey = storage.getItem("nw_beta_key");
    const previousName = normalize(storage.getItem("nw_player_name"));
    if (name ? name !== previousName : key !== previousKey) {
      storage.removeItem("nw_last_node");
      storage.removeItem("nw_view_depth");
    }
    storage.setItem("nw_beta_key", key);
    if (name) storage.setItem("nw_player_name", name);
    else if (key !== previousKey) storage.removeItem("nw_player_name");
    return name;
  }

  // Blocking is a private live-view preference. History and shared effects
  // intentionally have no liveParticipant marker and stay visible.
  function withoutBlockedLiveEvents(events, blocks) {
    const hidden = new Set(blocks.map(b => b.id));
    return events.filter(e => (!e.liveParticipant || !hidden.has(e.liveParticipant))
      && !(e.liveParticipants || []).some(id => hidden.has(id)));
  }

  function liveEventsAfterWelcome(events, previousViewer, viewer) {
    // A server restart replaces opaque targeting handles. Old live lines and
    // encounter effects can no longer be matched to a new blocking choice.
    if (!previousViewer || !viewer || previousViewer === viewer) return events;
    return events.filter(e => !e.liveParticipant && !(e.liveParticipants || []).length);
  }

  async function savePersonalBlock(url, participant, blocked, request = root.fetch) {
    const retry = 'Your block could not be saved. Try again.';
    let response, data;
    try {
      response = await request(url, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({participant, blocked}),
      });
      data = await response.json();
    } catch {
      throw new Error(retry);
    }
    if (!response.ok) throw new Error(typeof data?.error === 'string' && data.error || retry);
    if (!Array.isArray(data?.blocks)) throw new Error(retry);
    return data.blocks;
  }

  function findPath(node, name) {
    if (!node) return null;
    if (node.name === name) return [node];
    for (const child of node.children || []) {
      const sub = findPath(child, name);
      if (sub) return [node, ...sub];
    }
    return null;
  }

  function findNodeByName(node, name) {
    const path = findPath(node, name);
    return path ? path[path.length - 1] : null;
  }

  // HTTP acceptance and its socket echo describe one durable event. Read it
  // once per viewer; a later landing is a different event. This cache never
  // deduplicates requests to act, and carries no participant identity.
  function createNodeRefresher(read, apply) {
    const events = new Map();
    const latest = new Map();
    let serial = 0;
    return function refresh(seed, name, notice = {}) {
      const nodeKey = `${seed}:${name}`;
      const event = notice.matured && notice.work_id != null
        ? `landing:${notice.work_id}`
        : notice.event_id != null ? `acceptance:${notice.event_id}` : null;
      const key = event && `${nodeKey}:${event}`;
      if (key && events.has(key)) return events.get(key);
      const order = ++serial;
      latest.set(nodeKey, order);
      const request = Promise.resolve().then(() => read(seed, name)).then(node => {
        if (latest.get(nodeKey) === order) apply(node, seed, name);
      }).catch(error => {
        if (key) events.delete(key); // A failed read must be retryable.
        throw error;
      }).finally(() => {
        if (latest.get(nodeKey) === order) latest.delete(nodeKey);
      });
      if (key) {
        events.set(key, request);
        if (events.size > 128) events.delete(events.keys().next().value);
      }
      return request;
    };
  }

  function entryHash(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i++) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function dropInCandidates(rootNode) {
    const mids = [];
    const nonRoot = [];
    (function walk(node, depth) {
      if (depth > 0) {
        nonRoot.push(node);
        if (node.children && node.children.length) mids.push(node);
      }
      for (const child of node.children || []) walk(child, depth + 1);
    })(rootNode, 0);
    return mids.length ? mids : (nonRoot.length ? nonRoot : [rootNode]);
  }

  function dropInNode(rootNode, key) {
    const pool = dropInCandidates(rootNode);
    return pool[entryHash(key || "anon") % pool.length];
  }

  function entryPath(rootNode, savedNodeName, playerKey) {
    if (savedNodeName) {
      const resumed = findPath(rootNode, savedNodeName);
      if (resumed) return resumed;
    }
    const target = dropInNode(rootNode, playerKey);
    return findPath(rootNode, target.name) || [rootNode];
  }

  function resumeDepth(savedDepth, savedNodeName, minDepth = 6, maxDepth = 11) {
    const numericDepth = Number(savedDepth);
    const requested = Number.isFinite(numericDepth)
      ? Math.trunc(numericDepth)
      : minDepth;
    const suffix = String(savedNodeName || "").split("-").pop() || "";
    const nodeDepth = /^\d+$/.test(suffix) ? suffix.length : minDepth;
    return Math.min(maxDepth, Math.max(minDepth, requested, nodeDepth));
  }

  const BADGE_RULES = [
    { key: "danger",     color: 0xf05a5a, css: "#f05a5a" },
    { key: "corrupted",  color: 0xc88af0, css: "#c88af0" },
    { key: "disturbed",  color: 0xff8a4a, css: "#ff8a4a" },
    { key: "stabilized", color: 0x4af0c8, css: "#4af0c8" },
    { key: "pressure",   color: 0xa078ff, css: "#a078ff" },
    { key: "locked",     color: 0x8a93b0, css: "#8a93b0" },
  ];
  const badgeColors = Object.fromEntries(BADGE_RULES.map(rule => [rule.key, rule]));

  function passageBadges(node) {
    const properties = (node && node.properties) || {};
    const out = [];
    const push = (key, label) => out.push({ key, label, ...badgeColors[key] });
    if (typeof properties.danger_level === "number" && properties.danger_level >= 7) {
      push("danger", `danger ${properties.danger_level}`);
    }
    if (properties.condition === "corrupted") push("corrupted", "corrupted");
    if (properties.disturbed) push("disturbed", "disturbed");
    if (properties.stabilized) push("stabilized", "stabilized");
    if ((node && node.ripple_score) >= 0.3) push("pressure", "≈ pressure");
    if (properties.locked) push("locked", "locked");
    return out;
  }

  function nodeMark(node) {
    const badges = passageBadges(node);
    return badges.length ? badges[0].css : null;
  }

  // ── The wrap passage (ADR-008) ─────────────────────────────────────────
  // The loop's affordance rule, shared so both browser clients offer the
  // same passage: below any particle is the whole; beyond the root is the
  // world's one hinge particle. `wrapInfo` is the /world response's `wrap`
  // block (landings + authored lines) — the server owns the hinge.

  function wrapAffordance(node, wrapInfo) {
    if (!node || !wrapInfo) return null;
    if (node.level === "SubatomicParticle") {
      return {
        direction: "inward",
        target: wrapInfo.root,
        passage: wrapInfo.descent_passage,
        line: wrapInfo.descent_line,
      };
    }
    if (node.level === "Multiverse") {
      return {
        direction: "outward",
        target: wrapInfo.hinge,
        passage: wrapInfo.ascent_passage,
        line: wrapInfo.ascent_line,
      };
    }
    return null;
  }

  const WRAP_CROSSED_KEY = "nw_wrap_crossed";

  function firstWrapCrossing(direction, storage) {
    // True exactly once per browser per direction — the first crossing
    // gets the authored line; after that the passage is a way you know.
    // Storage failures (private mode, disabled) err toward speaking it.
    const store = storage || (typeof localStorage !== "undefined" ? localStorage : null);
    if (!store) return true;
    try {
      const seen = (store.getItem(WRAP_CROSSED_KEY) || "").split(",").filter(Boolean);
      if (seen.includes(direction)) return false;
      seen.push(direction);
      store.setItem(WRAP_CROSSED_KEY, seen.join(","));
      return true;
    } catch (_) {
      return true;
    }
  }

  // ── Display names ──────────────────────────────────────────────────────
  // A node's canonical name is `<three-word phrase>-<path digits>`: the
  // phrase is the readable identity, the digit suffix is its ADDRESS (the
  // path from the root — deterministic coordinates, not randomness). The
  // display layer shows the phrase and keeps the address one gesture away
  // (hover / a dedicated field); the canonical full name remains the sole
  // identity everywhere data is keyed or sent. Mirrors the puzzle layer's
  // own reading (puzzles/generators.py `_living_name`): answers were already
  // the phrase, never the address.

  function nodeAddress(name) {
    const s = String(name || "");
    const cut = s.lastIndexOf("-");
    if (cut <= 0) return null;   // no separator, or nothing before it
    const suffix = s.slice(cut + 1);
    return /^\d+$/.test(suffix) ? suffix : null;
  }

  function displayName(name) {
    const s = String(name || "");
    return nodeAddress(s) === null ? s : s.slice(0, s.lastIndexOf("-"));
  }

  // Live narration builders, shared so both clients' feeds and observation
  // tables speak the same display-layer language (and so the behavior is
  // testable once, here, rather than per presentation shell).

  function causalFeedLine(kind, node, strength) {
    const kindFmt = String(kind || "").replace(/_/g, " ").toLowerCase();
    const shown = Number.isFinite(strength) ? ` ×${strength.toFixed(2)}` : "";
    return `↯ ${kindFmt} · ${displayName(node)}${shown}`;
  }

  function observationRow({ node, kind, strength }) {
    return {
      name: displayName(node),
      event: String(kind || "").replace(/_/g, " ").toLowerCase(),
      pct: Math.round((strength || 0) * 100),
    };
  }

  function mutationLine(mutation) {
    // Authoritative read projection is shared with speech and live notices.
    if (mutation.narration?.text) return mutation.narration.text;
    const data = mutation.data || {};
    const label = value => typeof value === "string" && value.trim() ? value : null;
    const hasPatch = value => value && typeof value === "object" && !Array.isArray(value)
      && Object.keys(value).length > 0;
    const material = hasPatch(mutation.delta) || hasPatch(data.changed);
    const delayed = typeof data.matures_in === "number" && Number.isFinite(data.matures_in)
      && data.matures_in >= 0;
    const who = label(mutation.player) || label(data.actor) || label(data.agent) || "someone";
    const place = displayName(mutation.node);
    // Conservative compatibility with older servers/raw legacy rows. Never
    // turn a hop into a second performance of the original verb.
    if (data._origin || data._hop || data.delivery?.queue === "causal_queue") {
      const origin = label(data._origin) ? ` at ${displayName(data._origin)}` : "";
      return `A ripple from ${who}'s ${data.verb || "action"}${origin} reached ${place}. The exact original action is unrecorded.`;
    }
    switch (mutation.type) {
      case "PUZZLE_SOLVED": return `${who} solved a puzzle at ${place}`;
      case "PUZZLE_FAILED": return `a puzzle resisted ${who} at ${place}`;
      case "PLAYER_SPEAK": return `${who} spoke with ${place}`;
      case "PLAYER_CHAT": return `${who} said something at ${place}`;
      case "AGENT_VISIT": return `${who} passed through ${place}`;
      case "DANGER_ALERT": return `danger stirred at ${place}`;
      case "SCALE_ACT": return delayed
        ? `${who} chose to ${data.verb || "act"} at ${place}. A delayed outcome was accepted.`
        : material
          ? `${who} chose to ${data.verb || "act"} at ${place}. The recorded change took effect.`
          : `A trace of ${data.verb || "act"} attributed to ${who} was recorded at ${place}. No material change is recorded.`;
      case "SCALE_ACT_MATURED": return data.semantics_version === 2 && data.flavor
        ? `${place}: ${data.flavor}`
        : `A delayed ${data.verb || "act"} outcome was recorded at ${place}. The exact original action is unrecorded.`;
      case "AGENT_TALK": return `${data.a || "someone"} and ${data.b || "someone"} spoke at ${place}`;
      case "AGENT_VOICE": return `${who} spoke with ${data.agent || "a wanderer"} at ${place}`;
      case "PLAYER_JOIN": return `${who} arrived in the world`;
      case "PLAYER_LEAVE": return `${who} departed from ${place}`;
      case "PLAYER_MOVE": return `${who} passed into ${place}`;
      case "PUZZLE_ATTEMPT": return `${who} worked at a puzzle in ${place}`;
      // Expressive actions carry their authored line; a hop without one still
      // stays in fiction rather than falling to the mechanical default.
      case "INTERVENTION_COMMITTED": return label(data.flavor)
        ? `At ${place}, ${data.flavor}`
        : `${who} set an arrangement in motion at ${place}.`;
      case "INTERVENTION_ARRIVED": return label(data.flavor)
        ? `At ${place}, ${data.flavor}`
        : `A change from an earlier arrangement reached ${place}.`;
      default: return `something happened at ${place}`;
    }
  }

  function scaleActLine(message) {
    return mutationLine({ type: message.matured ? "SCALE_ACT_MATURED" : "SCALE_ACT",
      node: message.node, player: message.actor, narration: message.narration,
      data: { verb: message.verb, changed: message.changed, matures_in: message.matures_in,
        semantics_version: message.outcome ? 2 : undefined,
        flavor: message.flavor, outcome: message.outcome } });
  }

  function causalNoticeLine(message) {
    // The producer already emits the attributed acceptance notice. Its origin
    // pressure still animates, but must not appear to be a second action.
    if (message.action_notice) return null;
    return message.narration?.text || causalFeedLine(message.kind, message.node, message.strength);
  }

  function describeMutation(mutation) {
    return `${(mutation.at || "").slice(0, 10)} · ${mutationLine(mutation)}`;
  }

  function describeChronicleEntry(mutation) {
    return mutationLine(mutation);
  }

  // ── Wayback (ADR-011) ─────────────────────────────────────────────────
  // The API returns only the historical sensory inputs. Keep the live node's
  // navigation identity/children/verb while replacing properties, pressure,
  // and activity with the selected state so either client can feed the result
  // directly to today's deterministic art and sound functions.

  function waybackNode(liveNode, snapshotNode) {
    if (!liveNode || !snapshotNode) return liveNode;
    return {
      ...liveNode,
      name: snapshotNode.name || liveNode.name,
      level: snapshotNode.level || liveNode.level,
      properties: { ...(snapshotNode.properties || {}) },
      senses: snapshotNode.senses ? {...snapshotNode.senses} : undefined,
      ripple_score: Number(snapshotNode.ripple_score) || 0,
      activity: Math.max(0, Number(snapshotNode.activity) || 0),
    };
  }

  function _waybackValue(value) {
    if (value === null) return "fell away";
    if (typeof value === "object") return `became ${JSON.stringify(value)}`;
    return `became ${String(value)}`;
  }

  // The server closes a socket that receives nothing for 60s
  // (server/websocket.py `sock.settimeout(60)`). A browser cannot send an
  // RFC 6455 ping, so clients send the application ping the session loop
  // already answers with `{"type":"pong"}`. One owner, one interval: arm() replaces
  // any timer it started, and stop() is close and unmount. Page visibility
  // does not pause it — the scene renderer skips hidden frames, and pausing
  // here would let that 60s deadline drop a player who is still connected.
  const KEEPALIVE_INTERVAL_MS = 20000;

  function socketIsOpen(socket) {
    const openState = typeof WebSocket === "function" ? WebSocket.OPEN : 1;
    return !!socket && socket.readyState === openState;
  }

  function createSocketKeepalive(send, intervalMs) {
    const period = intervalMs == null ? KEEPALIVE_INTERVAL_MS : intervalMs;
    let timer = null;
    function stop() {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    }
    function arm(socket) {
      stop();
      timer = setInterval(function () {
        if (!socketIsOpen(socket)) return;
        try { send(socket); }
        catch (_) { /* a socket can close between the check and the write */ }
      }, period);
    }
    return { arm: arm, stop: stop };
  }

  function waybackMomentLine(timeline) {
    const moment = (timeline && timeline.moment) || { kind: "birth" };
    if (moment.kind === "birth") return "the node rests in its born state";
    if (moment.kind === "trace") return "a trace entered the record; its substance held";
    if (moment.kind === "ripple") {
      const strength = Number(moment.strength);
      return Number.isFinite(strength)
        ? `a ripple reached this place at strength ${strength.toFixed(2)}`
        : "a ripple reached this place";
    }
    const changes = Object.entries(moment.delta || {}).map(([key, value]) =>
      `${key.replace(/_/g, " ")} ${_waybackValue(value)}`);
    return changes.length
      ? changes.join(" · ")
      : "the node changed, though no visible property survived the fold";
  }

  // ── Chat drafts ────────────────────────────────────────────────────────
  // A chat line the moderation screen holds or declines reached nobody and
  // was stored nowhere. The server answers it with a sender-only
  // `chat_declined` that echoes the frame's `ref`. Both answers ask the
  // player to say it another way, so a held line and a declined line are
  // handled alike: the player's own words go back into the input to resend
  // or revise. Only the most recent line comes back, and only into an empty
  // input; anything typed since is kept. An answer without a matching ref
  // (an older line, an older server) restores nothing.

  function createChatDraft() {
    let serial = 0;
    let latest = null;
    return {
      // Record a line about to be sent; returns the ref for its frame.
      sent(text) {
        serial += 1;
        latest = { ref: `c${serial}`, text: String(text) };
        return latest.ref;
      },
      // The line a `chat_declined` gives back, or null. Each line is given
      // back at most once.
      declined(message) {
        if (!latest || !message || message.ref !== latest.ref) return null;
        const { text } = latest;
        latest = null;
        return text;
      },
    };
  }

  // The input's next value. A returned line fills an empty input and
  // never replaces text the player has typed since sending.
  function restoreChatInput(current, line) {
    return line && current === "" ? line : current;
  }

  // ── A world that does not open ──────────────────────────────────────────
  // The invite key lives only in this browser's storage once the address is
  // cleaned, so a bookmark, a private window, another device or cleared site
  // data arrives with none, and the gate answers /world with a bare 403. The
  // gate answers an unknown, revoked or sanctioned key with the same bare
  // 403 and gives no reason. The line says only what this browser knows,
  // which is whether it presented an invitation at all.
  const WORLD_INVITE_LINE = "The world opens only to an invitation, and this "
    + "browser holds none. To return, open the invite link you were sent, "
    + "here on this device.";
  const WORLD_REFUSED_LINE = "The invitation this browser holds does not open "
    + "the world. If you were sent another invite link, open it here on this "
    + "device.";
  const WORLD_UNREACHED_LINE = "The world could not be reached. Try opening "
    + "the view again.";
  // Shared with /speak and /agent/voice when the words do not reach the
  // place (see hearSpeech).
  const SPEAK_UNREACHED_LINE = "Your words did not reach this place. Try "
    + "speaking again.";

  // `kind` is "invite" or "refused" while the gate holds this browser out
  // (asking again changes nothing until an invite link is opened), and
  // "retry" for everything else. Two answers keep the server's own line: the
  // pace line (429) is authored, and a refused depth (400) names the range
  // the player chose outside of on the map. Any other status, such as a 404
  // or 401 from a proxy in front of the server, says nothing a player
  // should read, so it gets the retry line.
  const WORLD_LINE_STATUSES = [400, 429];
  function worldUnopened(status, hasKey, serverLine) {
    if (status === 403) {
      return hasKey
        ? { kind: "refused", line: WORLD_REFUSED_LINE }
        : { kind: "invite", line: WORLD_INVITE_LINE };
    }
    if (WORLD_LINE_STATUSES.includes(status) && typeof serverLine === "string" && serverLine) {
      return { kind: "retry", line: serverLine };
    }
    return { kind: "retry", line: WORLD_UNREACHED_LINE };
  }

  // The invite gate's own refusal: a 403 whose JSON body is exactly the one
  // the server's gate sends (`{"error": "forbidden"}`). A 403 from anything
  // in front of the server (a proxy, a firewall) says nothing about the
  // invitation, whatever its body.
  function isGateRefusal(status, data) {
    return status === 403 && !!data && typeof data === "object"
      && data.error === "forbidden";
  }

  // A /world answer both clients can draw from: the world's seed and its
  // tree. Every answer of the server's /world carries both.
  function opensWorld(data) {
    return !!data && typeof data === "object" && !data.error
      && Number.isFinite(data.seed)
      && !!data.world && typeof data.world === "object";
  }

  // Read /world through `read` (fetch, in both clients). Resolves to
  // `{ data }` when the world opened and `{ unopened }` otherwise. It never
  // rejects, so no raw transport message reaches a player.
  async function openWorld(read, url, hasKey) {
    let response;
    try {
      response = await read(url);
    } catch (_) {
      return { unopened: worldUnopened(0, hasKey) };
    }
    let data = null;
    let parsed = false;
    try {
      data = await response.json();
      parsed = true;
    } catch (_) { /* a proxy's HTML error page, or a cut-off body */ }
    if (response.ok && opensWorld(data)) return { data };
    // Only the gate's own answer speaks for the invitation. A 403 page from a
    // proxy in front of the server, a 403 with any other body, or a cut-off
    // body gets the retry line like any other failed read.
    if (!parsed || (response.status === 403 && !isGateRefusal(response.status, data))) {
      return { unopened: worldUnopened(0, hasKey) };
    }
    return { unopened: worldUnopened(response.status, hasKey, data && data.error) };
  }

  // ── Speech that is not answered ─────────────────────────────────────────
  // What a player reads after speaking to a place or a presence (/speak and
  // /agent/voice), by the same rule as a world read. Resolves to
  // `{ kind, line }` and never rejects. `kind` is:
  //   "reply"   the answer itself: any 2xx (a voice, the authored fallback,
  //             a hold or a decline), with the server's line;
  //   "invite" / "refused"  the invite gate's own 403 (a key revoked or
  //             sanctioned mid-session), with the world read's lines;
  //   "retry"   the words did not reach the place: a transport failure, a
  //             5xx, a body that is not JSON, or a 403 that is not the gate's;
  //   "server"  the server's own line for any other answer: the pace line
  //             (429) and the client-shaped refusals (400, 404, 413).
  const SPEECH_UNREACHED = Object.freeze({ kind: "retry", line: SPEAK_UNREACHED_LINE });
  async function hearSpeech(read, url, hasKey) {
    let response;
    let data;
    try {
      response = await read(url);
      data = await response.json();
    } catch (_) {
      return SPEECH_UNREACHED;
    }
    if (!data || typeof data !== "object") return SPEECH_UNREACHED;
    const { status } = response;
    if (status >= 200 && status < 300) {
      return { kind: data.error ? "server" : "reply", line: data.error || data.response };
    }
    if (isGateRefusal(status, data)) return worldUnopened(403, hasKey);
    if (status === 403 || status >= 500) return SPEECH_UNREACHED;
    const line = data.error || data.response;
    return typeof line === "string" && line ? { kind: "server", line } : SPEECH_UNREACHED;
  }

  root.EnfoldedClient = Object.freeze({
    withoutBlockedLiveEvents,
    liveEventsAfterWelcome,
    savePersonalBlock,
    BADGE_RULES,
    causalFeedLine,
    createChatDraft,
    createNodeRefresher,
    createSocketKeepalive,
    describeChronicleEntry,
    describeMutation,
    displayName,
    dropInNode,
    entryHash,
    entryPath,
    findNodeByName,
    findPath,
    firstWrapCrossing,
    hearSpeech,
    KEEPALIVE_INTERVAL_MS,
    mutationLine,
    scaleActLine,
    causalNoticeLine,
    nodeAddress,
    nodeMark,
    observationRow,
    openWorld,
    passageBadges,
    rememberInvite,
    restoreChatInput,
    resumeDepth,
    SPEAK_UNREACHED_LINE,
    waybackMomentLine,
    waybackNode,
    WORLD_INVITE_LINE,
    WORLD_REFUSED_LINE,
    WORLD_UNREACHED_LINE,
    worldUnopened,
    wrapAffordance,
  });
})(globalThis);

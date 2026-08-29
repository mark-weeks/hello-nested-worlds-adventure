// Browser-client rules shared by the no-build D3 explorer and the Vite app.
//
// This file is deliberately a classic script rather than an ES module: `/`
// loads it directly before explorer.js, while Vite imports it for its side
// effect and the small frontend wrappers re-export the same functions. Keeping
// the rules here removes the hand-mirrored entry, badge, and chronicle logic.
(function installClientLogic(root) {
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
  // own reading (puzzles/generators.py `_base_name`): answers were already
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

  function mutationLine(mutation) {
    const data = mutation.data || {};
    const who = mutation.player || data.agent || "someone";
    const place = displayName(mutation.node);
    switch (mutation.type) {
      case "PUZZLE_SOLVED": return `${who} solved a puzzle at ${place}`;
      case "PUZZLE_FAILED": return `a puzzle resisted ${who} at ${place}`;
      case "PLAYER_SPEAK": return `${who} spoke with ${place}`;
      case "PLAYER_CHAT": return `${who} said something at ${place}`;
      case "AGENT_VISIT": return `${who} passed through ${place}`;
      case "DANGER_ALERT": return `danger stirred at ${place}`;
      case "SCALE_ACT": return `${who} chose to ${data.verb || "act"} at ${place}`;
      case "AGENT_TALK": return `${data.a || "someone"} and ${data.b || "someone"} spoke at ${place}`;
      case "AGENT_VOICE": return `${who} spoke with ${data.agent || "a wanderer"} at ${place}`;
      case "PLAYER_JOIN": return `${who} arrived in the world`;
      case "PLAYER_LEAVE": return `${who} departed from ${place}`;
      case "PLAYER_MOVE": return `${who} passed into ${place}`;
      case "PUZZLE_ATTEMPT": return `${who} worked at a puzzle in ${place}`;
      default: return `something happened at ${place}`;
    }
  }

  function describeMutation(mutation) {
    return `${(mutation.at || "").slice(0, 10)} · ${mutationLine(mutation)}`;
  }

  function describeChronicleEntry(mutation) {
    return mutationLine(mutation);
  }

  root.EnfoldedClient = Object.freeze({
    BADGE_RULES,
    describeChronicleEntry,
    describeMutation,
    displayName,
    dropInNode,
    entryPath,
    findNodeByName,
    findPath,
    firstWrapCrossing,
    mutationLine,
    nodeAddress,
    nodeMark,
    passageBadges,
    resumeDepth,
    wrapAffordance,
  });
})(globalThis);

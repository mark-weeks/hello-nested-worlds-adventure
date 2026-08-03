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

  function mutationLine(mutation) {
    const data = mutation.data || {};
    const who = mutation.player || data.agent || "someone";
    switch (mutation.type) {
      case "PUZZLE_SOLVED": return `${who} solved a puzzle at ${mutation.node}`;
      case "PUZZLE_FAILED": return `a puzzle resisted ${who} at ${mutation.node}`;
      case "PLAYER_SPEAK": return `${who} spoke with ${mutation.node}`;
      case "PLAYER_CHAT": return `${who} said something at ${mutation.node}`;
      case "AGENT_VISIT": return `${who} passed through ${mutation.node}`;
      case "DANGER_ALERT": return `danger stirred at ${mutation.node}`;
      case "SCALE_ACT": return `${who} chose to ${data.verb || "act"} at ${mutation.node}`;
      case "AGENT_TALK": return `${data.a || "someone"} and ${data.b || "someone"} spoke at ${mutation.node}`;
      case "AGENT_VOICE": return `${who} spoke with ${data.agent || "a wanderer"} at ${mutation.node}`;
      case "PLAYER_JOIN": return `${who} arrived in the world`;
      case "PLAYER_LEAVE": return `${who} departed from ${mutation.node}`;
      case "PLAYER_MOVE": return `${who} passed into ${mutation.node}`;
      case "PUZZLE_ATTEMPT": return `${who} worked at a puzzle in ${mutation.node}`;
      default: return `something happened at ${mutation.node}`;
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
    dropInNode,
    entryPath,
    findNodeByName,
    findPath,
    mutationLine,
    nodeMark,
    passageBadges,
  });
})(globalThis);

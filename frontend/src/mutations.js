// One canonical rendering of a chronicle/history row, shared by every React
// surface that narrates the world's past (the event feed backfill and the
// chronicle overlay). static/explorer.js carries a hand-mirrored copy — it
// is served raw with no build step — and mutations.test.js executes BOTH
// copies over every event type, failing if they ever drift (the same
// harness entry.js uses). Four hand copies of this switch once existed;
// the React feed's copy was missing SCALE_ACT and AGENT_TALK, so those
// events rendered as "something happened" on one surface only.

export function mutationLine(m) {
  const who = m.player || (m.data && m.data.agent) || "someone";
  switch (m.type) {
    case "PUZZLE_SOLVED": return `${who} solved a puzzle at ${m.node}`;
    case "PUZZLE_FAILED": return `a puzzle resisted ${who} at ${m.node}`;
    case "PLAYER_SPEAK":  return `${who} spoke with ${m.node}`;
    case "PLAYER_CHAT":   return `${who} said something at ${m.node}`;
    case "AGENT_VISIT":   return `${who} passed through ${m.node}`;
    case "DANGER_ALERT":  return `danger stirred at ${m.node}`;
    case "SCALE_ACT":     return `${who} chose to ${(m.data && m.data.verb) || "act"} at ${m.node}`;
    case "AGENT_TALK":    return `${(m.data && m.data.a) || "someone"} and ${(m.data && m.data.b) || "someone"} spoke at ${m.node}`;
    case "AGENT_VOICE":   return `${who} spoke with ${(m.data && m.data.agent) || "a wanderer"} at ${m.node}`;
    case "PLAYER_JOIN":   return `${who} arrived in the world`;
    case "PLAYER_LEAVE":  return `${who} departed from ${m.node}`;
    case "PLAYER_MOVE":   return `${who} passed into ${m.node}`;
    case "PUZZLE_ATTEMPT": return `${who} worked at a puzzle in ${m.node}`;
    default:              return `something happened at ${m.node}`;
  }
}

// The event-feed variant: the same line prefixed with the record's date.
export function describeMutation(m) {
  const when = (m.at || "").slice(0, 10);
  return `${when} · ${mutationLine(m)}`;
}

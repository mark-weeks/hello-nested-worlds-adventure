// Pure WebSocket message dispatch — shared by the useWorldSocket hook and
// unit-testable without a DOM or a socket. Every server message type is
// routed here; a type without a handler is silently ignored.
//
// `welcome` matters most: it carries the roster snapshot of everyone ALREADY
// in the world when you connect. Dropping it (as an earlier version of the
// hook did) made every pre-existing player invisible until they next moved —
// the exact inversion of "a world already in motion."

export function dispatchMessage(msg, h) {
  if (!msg || typeof msg !== "object") return;
  switch (msg.type) {
    case "welcome":         h.onWelcome?.(msg); break;
    case "player_join":     h.onPlayerJoin?.(msg); break;
    case "player_leave":    h.onPlayerLeave?.(msg); break;
    case "player_move":     h.onPlayerMove?.(msg); break;
    case "chat":            h.onChat?.(msg); break;
    case "causal_event":    h.onCausalEvent?.(msg); break;
    case "puzzle_solved":   h.onPuzzleSolved?.(msg); break;
    case "agent_done":      h.onAgentDone?.(msg); break;
    case "agent_encounter": h.onAgentEncounter?.(msg); break;
    case "scale_act":       h.onScaleAct?.(msg); break;
    default: break;
  }
}

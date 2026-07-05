// Behavior tests for the WebSocket message dispatch — the layer whose
// silent gaps (a dropped `welcome` roster) previously made every
// already-present player invisible to new arrivals.
import { describe, expect, it, vi } from "vitest";
import { dispatchMessage } from "../dispatch.js";

describe("dispatchMessage", () => {
  it("routes the welcome roster — the world must not look empty on arrival", () => {
    const onWelcome = vi.fn();
    const msg = {
      type: "welcome",
      session_id: "me",
      players: [{ name: "Ada", session_id: "a1", node: "Vault-11" }],
    };
    dispatchMessage(msg, { onWelcome });
    expect(onWelcome).toHaveBeenCalledWith(msg);
  });

  it.each([
    ["player_join", "onPlayerJoin"],
    ["player_leave", "onPlayerLeave"],
    ["player_move", "onPlayerMove"],
    ["chat", "onChat"],
    ["causal_event", "onCausalEvent"],
    ["puzzle_solved", "onPuzzleSolved"],
    ["agent_done", "onAgentDone"],
    ["agent_encounter", "onAgentEncounter"],
    ["scale_act", "onScaleAct"],
    ["agent_talk", "onAgentTalk"],
  ])("routes %s to %s", (type, handlerName) => {
    const handler = vi.fn();
    dispatchMessage({ type }, { [handlerName]: handler });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("ignores unknown types and missing handlers without throwing", () => {
    expect(() => dispatchMessage({ type: "player_move" }, {})).not.toThrow();
    expect(() => dispatchMessage({ type: "mystery" }, {})).not.toThrow();
    expect(() => dispatchMessage(null, {})).not.toThrow();
    expect(() => dispatchMessage("garbage", {})).not.toThrow();
  });
});

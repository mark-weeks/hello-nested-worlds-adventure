// Wayback presentation is one shared rule in both clients: historical sensory
// inputs replace live state without replacing navigation identity, and moment
// narration never exposes an actor class.
import { describe, expect, it } from "vitest";
import { soundscapeKey } from "../../../static/nodesound.js";
import { waybackMomentLine, waybackNode } from "../wayback.js";

const live = {
  id: "live-id",
  name: "Quiet Brass Chamber-1121",
  level: "Room",
  properties: { danger_level: 8, lighting: "dim" },
  ripple_score: 0.9,
  activity: 12,
  verb: { name: "inscribe" },
  children: [{ id: "child" }],
};

describe("waybackNode", () => {
  it("feeds historical state to the senses while preserving live navigation", () => {
    const historical = waybackNode(live, {
      name: live.name,
      level: live.level,
      properties: { lighting: "bright", stabilized: true },
      ripple_score: 0.15,
      activity: 3,
    });
    expect(historical).toMatchObject({
      id: "live-id",
      properties: { lighting: "bright", stabilized: true },
      ripple_score: 0.15,
      activity: 3,
      verb: { name: "inscribe" },
      children: [{ id: "child" }],
    });
    expect(live.properties).toEqual({ danger_level: 8, lighting: "dim" });
  });
});

describe("waybackMomentLine", () => {
  it("describes birth, traces, ripples, and mechanical changes", () => {
    expect(waybackMomentLine({ moment: { kind: "birth" } }))
      .toBe("the node rests in its born state");
    expect(waybackMomentLine({ moment: { kind: "trace" } }))
      .toBe("a trace entered the record; its substance held");
    expect(waybackMomentLine({ moment: { kind: "ripple", strength: 0.5 } }))
      .toBe("a ripple reached this place at strength 0.50");
    expect(waybackMomentLine({
      moment: { kind: "change", delta: { danger_level: 7, disturbed: null } },
    })).toBe("danger level became 7 · disturbed fell away");
  });

  it("ignores actor-shaped fields instead of taxonomizing the chronicle", () => {
    const line = waybackMomentLine({
      moment: {
        kind: "trace",
        player: "Ada",
        actor: "Tessera",
        actor_type: "agent",
      },
    });
    expect(line).not.toMatch(/Ada|Tessera|agent|human/i);
  });
});

describe("soundscapeKey", () => {
  it("is stable for equal state and changes when the same node evolves", () => {
    const a = { ...live, properties: { lighting: "dim", danger_level: 8 } };
    const reordered = {
      ...live,
      properties: { danger_level: 8, lighting: "dim" },
    };
    const past = { ...live, activity: 2, ripple_score: 0.1 };
    expect(soundscapeKey(382, a)).toBe(soundscapeKey(382, reordered));
    expect(soundscapeKey(382, a)).not.toBe(soundscapeKey(382, past));
  });
});


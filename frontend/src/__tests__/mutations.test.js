// Behavior tests for the canonical chronicle/history renderer shared by both
// browser clients.
import { describe, expect, it } from "vitest";
import {
  describeChronicleEntry, describeMutation, mutationLine,
} from "../mutations.js";

// One fixture per event type the world records, plus the fallbacks: a
// typeless row, an agent-attributed row, and rows with missing data.
const FIXTURES = [
  { type: "PUZZLE_SOLVED", player: "Ada", node: "Vault-1121", at: "2026-07-19T02:00" },
  { type: "PUZZLE_FAILED", player: "Ada", node: "Vault-1121", at: "2026-07-19T02:00" },
  { type: "PLAYER_SPEAK", player: "Ada", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PLAYER_CHAT", player: "Ada", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "AGENT_VISIT", data: { agent: "Tessera" }, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "DANGER_ALERT", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "SCALE_ACT", player: "Ada", data: { verb: "ward" }, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "SCALE_ACT", player: "Ada", data: {}, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "AGENT_TALK", data: { a: "Tessera", b: "Karst" }, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "AGENT_TALK", data: {}, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "AGENT_VOICE", player: "Ada", data: { agent: "Tessera" }, node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "AGENT_VOICE", player: "Ada", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PLAYER_JOIN", player: "Ada", node: "Aethon-1", at: "2026-07-19T02:00" },
  { type: "PLAYER_LEAVE", player: "Ada", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PLAYER_MOVE", player: "Ada", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PUZZLE_ATTEMPT", player: "Ada", node: "Vault-1121", at: "2026-07-19T02:00" },
  { type: "SOMETHING_NEW", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PLAYER_MOVE", node: "Mire-112", at: "2026-07-19T02:00" },
  { type: "PLAYER_MOVE", player: "Ada", node: "Mire-112" },
];

describe("mutationLine", () => {
  it("narrates the two event kinds the old React copy dropped", () => {
    expect(mutationLine(FIXTURES[6])).toBe("Ada chose to ward at Mire-112");
    expect(mutationLine(FIXTURES[8]))
      .toBe("Tessera and Karst spoke at Mire-112");
  });

  it("falls back gracefully on missing actors, verbs, and speakers", () => {
    expect(mutationLine(FIXTURES[7])).toBe("Ada chose to act at Mire-112");
    expect(mutationLine(FIXTURES[9]))
      .toBe("someone and someone spoke at Mire-112");
    expect(mutationLine(FIXTURES[17])).toBe("someone passed into Mire-112");
  });

  it("never renders an unknown event type as broken text", () => {
    expect(mutationLine(FIXTURES[16])).toBe("something happened at Mire-112");
  });
});

describe("describeMutation", () => {
  it("is the same line with the record's date in front", () => {
    for (const m of FIXTURES) {
      expect(describeMutation(m))
        .toBe(`${(m.at || "").slice(0, 10)} · ${mutationLine(m)}`);
    }
  });
});

describe("chronicle entry", () => {
  it("uses the canonical undated mutation line", () => {
    for (const m of FIXTURES.filter(f => f.at)) {
      expect(describeChronicleEntry(m)).toBe(mutationLine(m));
    }
  });
});

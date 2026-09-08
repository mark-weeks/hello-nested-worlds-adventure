// Behavior tests for the canonical chronicle/history renderer shared by both
// browser clients.
import { describe, expect, it } from "vitest";
import {
  describeChronicleEntry, describeMutation, mutationLine, scaleActLine, causalNoticeLine,
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
    expect(mutationLine(FIXTURES[6])).toBe("A trace of ward attributed to Ada was recorded at Mire. Its source is unrecorded.");
    expect(mutationLine(FIXTURES[8]))
      .toBe("Tessera and Karst spoke at Mire");
  });

  it("falls back gracefully on missing actors, verbs, and speakers", () => {
    expect(mutationLine(FIXTURES[7])).toBe("A trace of act attributed to Ada was recorded at Mire. Its source is unrecorded.");
    expect(mutationLine(FIXTURES[9]))
      .toBe("someone and someone spoke at Mire");
    expect(mutationLine(FIXTURES[17])).toBe("someone passed into Mire");
  });

  it("never renders an unknown event type as broken text", () => {
    expect(mutationLine(FIXTURES[16])).toBe("something happened at Mire");
  });

  it("explains M2 terminal no-ops from durable history without inventing a material success", () => {
    const landed = { type: "SCALE_ACT_MATURED", node: "Mire-112", data: {
      semantics_version: 2, outcome: "already_satisfied",
      flavor: "The kindle finds this work already fulfilled. Nothing more changes.",
    } };
    expect(mutationLine(landed)).toBe("Mire: The kindle finds this work already fulfilled. Nothing more changes.");
    expect(describeChronicleEntry(landed)).toBe(mutationLine(landed));
    expect(mutationLine({ ...landed, data: { verb: "kindle" } })).toBe("A delayed kindle outcome was recorded at Mire. The exact original action is unrecorded.");
  });
});

describe("M3 shared live/history narration", () => {
  it.each(["accepted", "arrival", "outcome", "trace"])("preserves the authoritative %s projection across all surfaces", phase => {
    const narration = { phase, text: `Recorded ${phase} from action #7 at Source [11].` };
    const row = { type: "SCALE_ACT", player: "Unrelated live name", node: "Receiver-12", narration };
    expect(mutationLine(row)).toBe(narration.text);
    expect(describeChronicleEntry(row)).toBe(narration.text);
    expect(describeMutation(row)).toContain(narration.text);
    expect(scaleActLine({ ...row, actor: "Unrelated live name" })).toBe(narration.text);
    expect(causalNoticeLine({ ...row, kind: "SCALE_ACT" })).toBe(narration.text);
  });

  it("does not narrate an origin pressure notice as another accepted act", () => {
    expect(causalNoticeLine({ kind: "SCALE_ACT", action_notice: true })).toBeNull();
  });

  it.each(["actor", "agent"])("uses surviving %s labels on legacy ripples without repeating the verb", field => {
    const row = { type: "SCALE_ACT", node: "Receiver-12", data: {
      verb: "seed", _origin: "Source-11", [field]: "Ada" } };
    expect(mutationLine(row)).toContain("A ripple from Ada's seed at Source reached Receiver");
    expect(mutationLine(row)).not.toContain("chose");
    expect(mutationLine(row)).toContain("exact original action is unrecorded");
  });

  it("keeps queued zero distinct from an immediate change", () => {
    const message = { actor: "Ada", node: "Source-11", verb: "kindle", changed: null, matures_in: 0 };
    expect(scaleActLine(message)).toContain("delayed outcome was accepted");
    expect(scaleActLine({ ...message, changed: { kindled: true }, matures_in: null }))
      .toContain("recorded change took effect");
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

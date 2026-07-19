// Behavior tests for the canonical chronicle/history line renderer — and
// the cross-client parity harness that executes the hand-mirrored copy in
// static/explorer.js against it. Four hand copies of this switch once
// existed; the React feed's copy was missing SCALE_ACT and AGENT_TALK, so
// those events rendered as "something happened" on one surface only. One
// canonical module + this executed parity is the fix (same harness as
// entry.test.js).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { describeMutation, mutationLine } from "../mutations.js";

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

describe("explorer.js parity", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const explorerSrc = readFileSync(
    join(here, "../../../static/explorer.js"), "utf8");

  function extract(name) {
    const start = explorerSrc.indexOf(`function ${name}(`);
    if (start === -1) throw new Error(`function ${name} not found in explorer.js`);
    let depth = 0, i = explorerSrc.indexOf("{", start);
    for (; i < explorerSrc.length; i++) {
      if (explorerSrc[i] === "{") depth++;
      if (explorerSrc[i] === "}") depth--;
      if (depth === 0) break;
    }
    return explorerSrc.slice(start, i + 1);
  }

  it("the hand-mirrored describeMutation agrees on every event type", () => {
    // eslint-disable-next-line no-new-func
    const explorerDescribe = new Function(
      `${extract("describeMutation")}\nreturn describeMutation;`)();
    for (const m of FIXTURES) {
      expect(explorerDescribe(m)).toBe(describeMutation(m));
    }
  });

  it("the explorer's chronicle rows agree with mutationLine", () => {
    // describeChronicleEntry derives from describeMutation by stripping the
    // date prefix — it must land exactly on the canonical undated line.
    // eslint-disable-next-line no-new-func
    const explorerChronicle = new Function(
      `${extract("describeMutation")}\n${extract("describeChronicleEntry")}\n` +
      "return describeChronicleEntry;")();
    for (const m of FIXTURES.filter(f => f.at)) {
      expect(explorerChronicle(m)).toBe(mutationLine(m));
    }
  });
});

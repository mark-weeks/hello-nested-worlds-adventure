// Names, addresses and keys (ADR-041). A name is shown as it reads. The
// address and the identity key are fields the server sends; a client never
// works either out of a name. A world born before names and addresses were
// separated stores names ending in "-<digits>", and those still display
// without the digits.
import { describe, expect, it } from "vitest";
import { causalFeedLine, displayName, nodeAddress, nodeKey, observationRow } from "../names.js";

describe("displayName", () => {
  it("shows a three-word name whole", () => {
    expect(displayName("Hidden Thorn Quark")).toBe("Hidden Thorn Quark");
    expect(displayName("Elder Reed Cosmos")).toBe("Elder Reed Cosmos");
  });

  it("shows an earlier world's stored name without its digits", () => {
    expect(displayName("Hidden Thorn Quark-11431112111")).toBe("Hidden Thorn Quark");
    expect(displayName("Elder Reed Cosmos-1")).toBe("Elder Reed Cosmos");
  });

  it("leaves names without a path suffix untouched", () => {
    expect(displayName("Aethon")).toBe("Aethon");
    expect(displayName("no-suffix-here")).toBe("no-suffix-here");
    expect(displayName("Vault-12a")).toBe("Vault-12a");
  });

  it("never displays an empty name", () => {
    // A bare address is not a phrase; nothing readable can be stripped.
    expect(displayName("-123")).toBe("-123");
    expect(displayName("")).toBe("");
    expect(displayName(null)).toBe("");
  });
});

describe("live narration builders", () => {
  // One shared implementation feeds both clients' live surfaces, so a
  // CAUSAL_EVENT or an observer row can never leak an address again.
  it("the causal feed line speaks the display name", () => {
    expect(causalFeedLine("PUZZLE_SOLVED", "Hidden Thorn Quark-11431112111", 0.5))
      .toBe("↯ puzzle solved · Hidden Thorn Quark ×0.50");
  });

  it("the causal feed line survives a missing strength", () => {
    expect(causalFeedLine("DANGER_ALERT", "Distant Compass Reach-114311", undefined))
      .toBe("↯ danger alert · Distant Compass Reach");
  });

  it("the observer row speaks the display name and keeps the real strength", () => {
    const row = observationRow({
      node: "Hidden Thorn Quark-11431112111",
      kind: "AGENT_VISIT",
      strength: 0.5,
    });
    expect(row).toEqual({ name: "Hidden Thorn Quark", event: "agent visit", pct: 50 });
  });
});

describe("nodeAddress", () => {
  it("reads the address the server sent with the node", () => {
    expect(nodeAddress({ name: "Hidden Thorn Quark", address: "11431112111" })).toBe("11431112111");
    expect(nodeAddress({ name: "Elder Reed Cosmos", address: "1" })).toBe("1");
    // An earlier world's node carries the field too; the name is not consulted.
    expect(nodeAddress({ name: "Hidden Thorn Quark-11431112111", address: "11431112111" })).toBe("11431112111");
  });

  it("never derives a position from a name", () => {
    expect(nodeAddress("Hidden Thorn Quark-11431112111")).toBeNull();
    expect(nodeAddress({ name: "Hidden Thorn Quark-11431112111" })).toBeNull();
    expect(nodeAddress({ name: "Aethon", address: "12a" })).toBeNull();
    expect(nodeAddress({ name: "Aethon", address: "" })).toBeNull();
    expect(nodeAddress(null)).toBeNull();
  });
});

describe("nodeKey", () => {
  it("is the key the server sent, never a join of name and address", () => {
    expect(nodeKey({ name: "Hidden Thorn Quark", address: "11431112111", key: "Hidden Thorn Quark-11431112111" }))
      .toBe("Hidden Thorn Quark-11431112111");
    // An earlier world's key is its stored name alone.
    expect(nodeKey({ name: "Elder Reed Cosmos-1", address: "1", key: "Elder Reed Cosmos-1" }))
      .toBe("Elder Reed Cosmos-1");
  });

  it("falls back to the name for a node built without a key", () => {
    expect(nodeKey({ name: "Aethon", address: "12" })).toBe("Aethon");
    expect(nodeKey(null)).toBe("");
  });
});

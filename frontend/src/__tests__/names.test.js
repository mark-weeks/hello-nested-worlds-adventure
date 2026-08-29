// The display layer: the readable phrase is shown, the address (the
// path-digit suffix — deterministic coordinates, not randomness) stays one
// gesture away, and the canonical full name remains the identity.
import { describe, expect, it } from "vitest";
import { causalFeedLine, displayName, nodeAddress, observationRow } from "../names.js";

describe("displayName", () => {
  it("shows the phrase without the address", () => {
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
  it("extracts the path digits", () => {
    expect(nodeAddress("Hidden Thorn Quark-11431112111")).toBe("11431112111");
    expect(nodeAddress("Elder Reed Cosmos-1")).toBe("1");
  });

  it("returns null when a name carries no address", () => {
    expect(nodeAddress("Aethon")).toBeNull();
    expect(nodeAddress("Vault-12a")).toBeNull();
    expect(nodeAddress("-123")).toBeNull();
    expect(nodeAddress("")).toBeNull();
  });
});

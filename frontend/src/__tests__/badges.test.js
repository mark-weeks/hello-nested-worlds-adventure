// Passage affordances: what a player is told about a passage before
// committing to it — and, just as deliberately, what they are NOT told.
import { describe, expect, it } from "vitest";
import { nodeMark, passageBadges } from "../badges.js";

const node = (properties = {}, ripple_score = 0) =>
  ({ properties, ripple_score });

describe("passageBadges", () => {
  it("flags high danger with the level shown", () => {
    const badges = passageBadges(node({ danger_level: 8 }));
    expect(badges.map(b => b.key)).toContain("danger");
    expect(badges.find(b => b.key === "danger").label).toBe("danger 8");
  });

  it("does not flag mild danger", () => {
    expect(passageBadges(node({ danger_level: 4 }))).toEqual([]);
  });

  it("flags the causal-effect properties the world writes", () => {
    expect(passageBadges(node({ stabilized: true })).map(b => b.key))
      .toEqual(["stabilized"]);
    expect(passageBadges(node({ disturbed: true })).map(b => b.key))
      .toEqual(["disturbed"]);
    expect(passageBadges(node({ condition: "corrupted" })).map(b => b.key))
      .toEqual(["corrupted"]);
  });

  it("flags accumulated causal pressure at the style threshold's foothill", () => {
    expect(passageBadges(node({}, 0.35)).map(b => b.key)).toEqual(["pressure"]);
    expect(passageBadges(node({}, 0.1))).toEqual([]);
  });

  it("never badges ubiquitous traits — a puzzle everywhere is a badge nowhere", () => {
    expect(passageBadges(node({ has_puzzle: true, exits: 3 }))).toEqual([]);
  });

  it("survives malformed nodes", () => {
    expect(passageBadges(null)).toEqual([]);
    expect(passageBadges({})).toEqual([]);
  });
});

describe("explorer marker", () => {
  it.each([
    [{ danger_level: 9 }, 0, "danger"],
    [{ condition: "corrupted" }, 0, "corrupted"],
    [{ disturbed: true }, 0, "disturbed"],
    [{ stabilized: true }, 0, "stabilized"],
    [{}, 0.4, "pressure"],
    [{ locked: true }, 0, "locked"],
  ])("marks %o with the same color as the React badge", (props, ripple, key) => {
    const badge = passageBadges(node(props, ripple)).find(b => b.key === key);
    expect(nodeMark({ properties: props, ripple_score: ripple })).toBe(badge.css);
  });

  it("marks unremarkable nodes with null", () => {
    expect(nodeMark({ properties: { danger_level: 2 }, ripple_score: 0 })).toBeNull();
  });

  it("always shows the highest-priority badge — all six rules", () => {
    const cases = [
      [{ danger_level: 9, locked: true }, 0],
      [{ condition: "corrupted", stabilized: true }, 0],
      [{ locked: true }, 0.4],
      [{ locked: true }, 0],
      [{ disturbed: true, locked: true }, 0.4],
      [{}, 0],
    ];
    for (const [props, ripple] of cases) {
      const badges = passageBadges(node(props, ripple));
      expect(nodeMark({ properties: props, ripple_score: ripple }))
        .toBe(badges.length ? badges[0].css : null);
    }
  });
});

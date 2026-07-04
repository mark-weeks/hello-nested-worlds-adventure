// Passage affordances: what a player is told about a passage before
// committing to it — and, just as deliberately, what they are NOT told.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { passageBadges } from "../badges.js";

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

describe("explorer.js parity", () => {
  // The explorer's nodeMark() is a hand-mirrored priority-ordered version of
  // these rules; execute it against the same inputs so the two clients can't
  // silently drift on what counts as remarkable.
  const here = dirname(fileURLToPath(import.meta.url));
  const src = readFileSync(join(here, "../../../static/explorer.js"), "utf8");
  const start = src.indexOf("function nodeMark(");
  const bodyEnd = src.indexOf("\n}", start);
  // eslint-disable-next-line no-new-func
  const nodeMark = new Function(`${src.slice(start, bodyEnd + 2)}; return nodeMark;`)();

  it.each([
    [{ danger_level: 9 }, 0, "danger"],
    [{ condition: "corrupted" }, 0, "corrupted"],
    [{ disturbed: true }, 0, "disturbed"],
    [{ stabilized: true }, 0, "stabilized"],
    [{}, 0.4, "pressure"],
  ])("marks %o with the same color as the React badge", (props, ripple, key) => {
    const badge = passageBadges(node(props, ripple)).find(b => b.key === key);
    expect(nodeMark({ properties: props, ripple_score: ripple })).toBe(badge.css);
  });

  it("marks unremarkable nodes with null", () => {
    expect(nodeMark({ properties: { danger_level: 2 }, ripple_score: 0 })).toBeNull();
  });
});

// The wrap passage's affordance rule (ADR-008): which passage a node
// offers, where it lands, and when the authored crossing line is spoken.
// One canonical implementation serves both browser clients.
import { describe, expect, it } from "vitest";
import { firstWrapCrossing, wrapAffordance } from "../wrap.js";

const WRAP = {
  root: "Elder Reed Cosmos-1",
  hinge: "Hidden Thorn Quark-11431112111",
  descent_passage: "the way inward opens onto the whole",
  ascent_passage: "the way beyond narrows to a single particle",
  descent_line: "You lean into the particle…",
  ascent_line: "You pass beyond the last membrane…",
};

describe("wrapAffordance", () => {
  it("offers every particle the descent onto the whole", () => {
    const aff = wrapAffordance({ level: "SubatomicParticle", name: "Any Quark-12111111111" }, WRAP);
    expect(aff.direction).toBe("inward");
    expect(aff.target).toBe(WRAP.root);
    expect(aff.passage).toBe(WRAP.descent_passage);
    expect(aff.line).toBe(WRAP.descent_line);
  });

  it("offers the root the ascent to the one hinge", () => {
    const aff = wrapAffordance({ level: "Multiverse", name: WRAP.root }, WRAP);
    expect(aff.direction).toBe("outward");
    expect(aff.target).toBe(WRAP.hinge);
    expect(aff.passage).toBe(WRAP.ascent_passage);
    expect(aff.line).toBe(WRAP.ascent_line);
  });

  it("offers nothing at any middle scale", () => {
    for (const level of ["Universe", "Galaxy", "Room", "Object", "Atom"]) {
      expect(wrapAffordance({ level }, WRAP)).toBeNull();
    }
  });

  it("offers nothing before the world's wrap block arrives", () => {
    expect(wrapAffordance({ level: "SubatomicParticle" }, null)).toBeNull();
    expect(wrapAffordance(null, WRAP)).toBeNull();
  });
});

describe("firstWrapCrossing", () => {
  const memoryStorage = () => {
    const store = new Map();
    return {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
    };
  };

  it("speaks the authored line exactly once per direction", () => {
    const storage = memoryStorage();
    expect(firstWrapCrossing("inward", storage)).toBe(true);
    expect(firstWrapCrossing("inward", storage)).toBe(false);
    // The other direction still deserves its own first line.
    expect(firstWrapCrossing("outward", storage)).toBe(true);
    expect(firstWrapCrossing("outward", storage)).toBe(false);
  });

  it("errs toward speaking the line when storage is unavailable", () => {
    const broken = {
      getItem: () => { throw new Error("storage disabled"); },
      setItem: () => { throw new Error("storage disabled"); },
    };
    expect(firstWrapCrossing("inward", broken)).toBe(true);
  });
});

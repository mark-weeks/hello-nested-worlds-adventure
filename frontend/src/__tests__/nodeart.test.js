// Per-node generative art: deterministic, unique, and expressive of the
// node's properties and history. Params are pure, so they test without a
// canvas; the full renderer is exercised against a stub 2D context.
import { describe, expect, it } from "vitest";
import {
  drawNodeArt, hashString, mulberry32, nodeArtParams,
} from "../../../static/nodeart.js";

const node = (name, level, properties = {}, ripple = 0, activity = 0) =>
  ({ name, level, properties, ripple_score: ripple, activity });

describe("nodeArtParams", () => {
  it("is deterministic per (seed, node)", () => {
    const a = nodeArtParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    const b = nodeArtParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    expect(a).toEqual(b);
  });

  it("differs across nodes and across seeds", () => {
    const a = nodeArtParams(42, node("Emberglass Vault-1121", "Room"));
    const b = nodeArtParams(42, node("Saltfall Archive-1122", "Room"));
    const c = nodeArtParams(7,  node("Emberglass Vault-1121", "Room"));
    expect(a.prng).not.toBe(b.prng);
    expect(a.prng).not.toBe(c.prng);
  });

  it("gives every level its own form family", () => {
    const families = new Set(
      ["Multiverse", "Universe", "Galaxy", "Planetary System", "Planet",
       "Region", "Room", "Object", "Molecule", "Atom", "SubatomicParticle"]
        .map(l => nodeArtParams(1, node("X-1", l)).family));
    expect(families.size).toBe(11);
  });

  it("expresses what has happened to the node", () => {
    const calm = nodeArtParams(1, node("A-1", "Room"));
    const pressured = nodeArtParams(1, node("A-1", "Room", {}, 0.8));
    expect(pressured.saturation).toBeGreaterThan(calm.saturation);
    expect(pressured.jitter).toBeGreaterThan(calm.jitter);

    expect(nodeArtParams(1, node("A-1", "Object", { condition: "corrupted" })).glitch).toBe(true);
    expect(nodeArtParams(1, node("A-1", "Region", { stabilized: true })).halo).toBe(true);
    expect(nodeArtParams(1, node("A-1", "Region", { danger_level: 9 })).dangerVignette).toBe(true);
    expect(nodeArtParams(1, node("A-1", "Room", {}, 0, 12)).activity).toBe(12);
  });

  it("draws the node's atmosphere and inscriptions", () => {
    const a = nodeArtParams(1, node("T-1", "Room", { air: "dry and papery" }));
    const b = nodeArtParams(1, node("T-1", "Room", { air: "cool and mineral" }));
    expect(a.atmo).not.toBeNull();
    expect(a.atmo.grain).not.toBe(b.atmo.grain); // each atmosphere its own texture
    expect(nodeArtParams(1, node("T-1", "Room", {})).atmo).toBeNull();
    expect(nodeArtParams(1, node("T-1", "Room", { inscriptions: 7 })).inscriptions).toBe(7);
    expect(nodeArtParams(1, node("T-1", "Room", { inscriptions: 999 })).inscriptions).toBe(30); // capped
  });

  it("reads structural properties into the composition", () => {
    const sparse = nodeArtParams(1, node("G-1", "Galaxy", { star_density: 50 }));
    const dense = nodeArtParams(1, node("G-1", "Galaxy", { star_density: 500 }));
    expect(dense.count).toBeGreaterThan(sparse.count);
  });
});

describe("mulberry32 / hashString", () => {
  it("streams are reproducible", () => {
    const a = mulberry32(hashString("x")); const b = mulberry32(hashString("x"));
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
});

describe("drawNodeArt", () => {
  function stubCanvas() {
    const calls = [];
    const gradient = { addColorStop: () => {} };
    const ctx = new Proxy({}, {
      get(_, prop) {
        if (prop === "createLinearGradient" || prop === "createRadialGradient")
          return () => gradient;
        if (prop === "getImageData") return () => ({});
        return (...args) => { calls.push(String(prop)); };
      },
      set() { return true; },
    });
    return { canvas: { width: 320, height: 200, getContext: () => ctx }, calls };
  }

  it.each([
    "Multiverse", "Universe", "Galaxy", "Planetary System", "Planet",
    "Region", "Room", "Object", "Molecule", "Atom", "SubatomicParticle",
  ])("renders a %s without throwing", (level) => {
    const { canvas, calls } = stubCanvas();
    drawNodeArt(canvas, 42, node("Test-11", level,
      { star_density: 200, planet_count: 4, bond_count: 6, moons: 2,
        exits: 3, lighting: "dim", shape: "spiral", coherence: 0.4,
        atomic_number: 26, condition: "corrupted", stabilized: true,
        danger_level: 8 }, 0.6, 10));
    expect(calls.length).toBeGreaterThan(10);
  });
});

// Ambient sound params: deterministic, register follows scale depth, and the
// node's condition is audible (danger roughens, stabilization purifies).
// The WebAudio graph itself needs a browser; the params are pure.
import { describe, expect, it } from "vitest";
import { ambienceParams } from "../../../static/nodesound.js";

const node = (name, level, properties = {}) => ({ name, level, properties });

describe("ambienceParams", () => {
  it("is deterministic per (seed, node)", () => {
    const a = ambienceParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    const b = ambienceParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    expect(a).toEqual(b);
  });

  it("differs across nodes", () => {
    const a = ambienceParams(42, node("A-11", "Room"));
    const b = ambienceParams(42, node("B-12", "Room"));
    expect(a.freq).not.toBe(b.freq);
  });

  it("register climbs as the scale shrinks", () => {
    const multiverse = ambienceParams(1, node("M-1", "Multiverse"));
    const room = ambienceParams(1, node("R-1111111", "Room"));
    const particle = ambienceParams(1, node("P-11111111111", "SubatomicParticle"));
    expect(multiverse.freq).toBeLessThan(room.freq);
    expect(room.freq).toBeLessThan(particle.freq);
  });

  it("danger is audible as roughness — unless the place was stabilized", () => {
    expect(ambienceParams(1, node("X-1", "Region", { danger_level: 8 })).rough).toBe(true);
    expect(ambienceParams(1, node("X-1", "Region", { danger_level: 8, stabilized: true })).rough).toBe(false);
    expect(ambienceParams(1, node("X-1", "Region", { danger_level: 2 })).rough).toBe(false);
  });

  it("stays ambience-quiet", () => {
    expect(ambienceParams(1, node("X-1", "Room")).gain).toBeLessThan(0.1);
  });
});

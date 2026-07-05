// The soundscape spec: deterministic, musically coherent, and expressive of
// the same node state the art draws and the voice speaks. The WebAudio
// graph needs a browser; the params are pure and carry the whole musical
// contract — harmony, register, density, history marks.
import { describe, expect, it } from "vitest";
import { ambienceParams, soundscapeParams } from "../../../static/nodesound.js";

const node = (name, level, properties = {}, activity = 0) =>
  ({ name, level, properties, ripple_score: 0, activity });

describe("soundscapeParams", () => {
  it("is deterministic per (seed, node)", () => {
    const a = soundscapeParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    const b = soundscapeParams(42, node("Velkarith Vault-1121", "Room", { lighting: "dim" }));
    expect(a).toEqual(b);
  });

  it("gives different nodes different music", () => {
    const a = soundscapeParams(42, node("A-11", "Room"));
    const b = soundscapeParams(42, node("B-12", "Room"));
    expect(a.rootHz !== b.rootHz || a.mode !== b.mode ||
           a.pad.filterBase !== b.pad.filterBase).toBe(true);
  });

  it("register climbs as the scale shrinks", () => {
    const m = soundscapeParams(1, node("M-1", "Multiverse"));
    const r = soundscapeParams(1, node("R-1111111", "Room"));
    const p = soundscapeParams(1, node("P-11111111111", "SubatomicParticle"));
    expect(m.rootHz).toBeLessThan(r.rootHz);
    expect(r.rootHz).toBeLessThan(p.rootHz);
  });

  it("events quicken as the scale shrinks — cosmic bells, quantum sparkle", () => {
    const m = soundscapeParams(1, node("M-1", "Multiverse"));
    const p = soundscapeParams(1, node("P-11111111111", "SubatomicParticle"));
    expect(m.events.intervalMin).toBeGreaterThan(p.events.intervalMin);
    expect(m.events.decay).toBeGreaterThan(p.events.decay);
  });

  it("harmony follows the node's condition", () => {
    expect(soundscapeParams(1, node("X-1", "Region", { danger_level: 8 })).mode)
      .toBe("phrygian");
    expect(soundscapeParams(1, node("X-1", "Region", { stabilized: true })).mode)
      .toBe("lydian");
    expect(soundscapeParams(1, node("X-1", "Object", { condition: "corrupted" })).mode)
      .toBe("insen");
    expect(soundscapeParams(1, node("X-1", "Region", { danger_level: 5 })).mode)
      .toBe("aeolian");
    const calm = soundscapeParams(1, node("X-1", "Room")).mode;
    expect(["majorPent", "mixolydian", "dorian"]).toContain(calm);
  });

  it("a warded (stabilized) place is never rough, whatever the danger", () => {
    const p = soundscapeParams(1, node("X-1", "Region",
      { danger_level: 8, stabilized: true }));
    expect(p.rough).toBe(false);
    expect(p.shimmer).toBe(true);
    expect(p.space.feedback).toBeGreaterThan(0.4); // haloed places ring longer
  });

  it("every music-box note is locked to the node's scale", () => {
    const p = soundscapeParams(7, node("Bell-111", "Atom", { danger_level: 2 }));
    for (const f of p.events.notePool) {
      const semisFromRoot = Math.round(12 * Math.log2(f / p.rootHz));
      expect(p.scale).toContain(((semisFromRoot % 12) + 12) % 12);
    }
  });

  it("history is audible: activity adds wow, corruption gates dropouts", () => {
    const worn = soundscapeParams(1, node("W-1", "Room", {}, 30));
    const fresh = soundscapeParams(1, node("W-1", "Room", {}, 0));
    expect(worn.wow.depthCents).toBeGreaterThan(fresh.wow.depthCents);
    expect(soundscapeParams(1, node("W-1", "Room", {}, 400)).wow.depthCents)
      .toBeLessThanOrEqual(12); // capped: worn, never seasick
    expect(soundscapeParams(1, node("C-1", "Object",
      { condition: "corrupted" })).dropouts).toBe(true);
  });

  it("the texture band comes from the node's own atmosphere", () => {
    const a = soundscapeParams(1, node("T-1", "Room", { air: "dry and papery" }));
    const b = soundscapeParams(1, node("T-1", "Room", { air: "cool and mineral" }));
    expect(a.texture.center).not.toBe(b.texture.center);
  });

  it("stays ambience-quiet", () => {
    expect(soundscapeParams(1, node("X-1", "Room")).gain).toBeLessThan(0.1);
  });

  it("keeps the legacy alias and fields", () => {
    const p = ambienceParams(1, node("X-1", "Room"));
    expect(p.freq).toBe(p.rootHz);
    expect(typeof p.rough).toBe("boolean");
  });
});

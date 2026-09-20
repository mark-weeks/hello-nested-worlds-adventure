// Behavior tests for the shared scene renderer: motion runs on a frame counter,
// so the same served node draws the same frame everywhere and nothing reads
// the wall clock. The browser surface is stubbed with a recording 2D context.
import { beforeAll, describe, expect, it, vi } from "vitest";

let startSensory, nextFrame;
function recordingContext(log) {
  const gradient = () => ({ addColorStop: (...a) => log.push(["stop", ...a]) });
  return new Proxy({}, {
    get: (_, key) => (key === "createLinearGradient" || key === "createRadialGradient")
      ? (...a) => { log.push([key, ...a]); return gradient(); }
      : (...a) => { log.push([key, ...a.map(v => (typeof v === "object" ? "obj" : v))]); },
    set: (_, key, value) => { log.push(["set", key, typeof value === "object" ? "obj" : value]); return true; },
  });
}
function canvasFor(log) {
  return { width: 0, height: 0, getContext: () => recordingContext(log),
           getBoundingClientRect: () => ({ width: 320, height: 180 }) };
}
beforeAll(async () => {
  const frames = [];
  nextFrame = () => { const pending = frames.splice(0); for (const cb of pending) cb(); };
  globalThis.requestAnimationFrame = cb => { frames.push(cb); return frames.length; };
  globalThis.cancelAnimationFrame = () => {};
  globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  globalThis.ResizeObserver = class { constructor(cb) { this.cb = cb; } observe() {} disconnect() {} };
  globalThis.document = { hidden: false };
  globalThis.devicePixelRatio = 1;
  globalThis.Image = class { set src(_) {} };
  globalThis.performance = { now: () => { throw new Error("the renderer read the wall clock"); } };
  ({ startSensory } = await import("../../../static/sensory.js"));
});

const node = { name: "Elder River Instrument-11111111", level: "Object", senses: {
  texture: "filament", material: "woven light", atmosphere: "dust", polarity: 1, echo: 9,
  energy: .4, woven: true, memory: "3fa9", scar: 2, light: "#efc07b", shadow: "#071b24" } };

function render(frames, transients = () => []) {
  const log = [];
  const stop = startSensory(canvasFor(log), node, { transients });
  for (let i = 0; i < frames; i++) nextFrame();
  stop();
  return log;
}

describe("scene renderer determinism", () => {
  it("draws the same frame for the same served node without reading the clock", () => {
    const first = render(0), again = render(0);
    expect(first.length).toBeGreaterThan(50);
    expect(again).toEqual(first);
    expect(render(40)).toEqual(render(40));
  });

  it("advances motion by frame, so later frames differ from the first", () => {
    expect(render(40)).not.toEqual(render(0));
  });

  it("progresses a transient from the frame it first appears, not from wall time", () => {
    const ripple = { kind: "ripple", strength: 1, duration: 1000, startedAt: 123456789 };
    const withRipple = render(10, () => [ripple]);
    const without = render(10);
    expect(withRipple.length).toBeGreaterThan(without.length);
    // A one-second ripple is drawn on frames 0..60 and never again, whatever startedAt says.
    const spent = render(70, () => [ripple]);
    const ellipses = log => log.filter(e => e[0] === "ellipse").length;
    expect(ellipses(spent) - ellipses(render(70))).toBe(61);
  });
});

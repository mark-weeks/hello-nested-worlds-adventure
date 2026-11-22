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

describe("scene artwork credits", () => {
  it.each([
    [undefined, "/media/places/gallery-v1.png", "AI-generated background, included with the game."],
    ["https://art.example/scene.png", null, "AI-generated background for this place."],
  ])("credits the painted background for image URL %s and bundled plate %s", (imageUrl, plate, expected) => {
    const images = [];
    vi.stubGlobal("Image", class {
      width = 320;
      height = 180;
      constructor() { images.push(this); }
    });
    const log = [];
    const credits = [];
    const place = { ...node, senses: { ...node.senses, plate } };
    const stop = startSensory(canvasFor(log), place, {
      imageUrl,
      onArtSource: text => credits.push({ text, painted: log.some(([op]) => op === "drawImage") }),
    });
    try {
      // An image still loading or one that never loads leaves the local art.
      expect(images[0].src).toBe(imageUrl || plate);
      expect(credits).toEqual([{ text: "Scene drawn from this place’s conditions.", painted: false }]);
      const loaded = images[0].onload;
      loaded();
      expect(credits.at(-1)).toEqual({ text: expected, painted: true });
      nextFrame();
      stop();
      loaded();  // A late callback from a closed scene cannot change its credit.
      expect(credits).toHaveLength(2);
    } finally {
      stop();
      vi.unstubAllGlobals();
    }
  });

  it("clears the credit when there is no drawing context", () => {
    const onArtSource = vi.fn();
    startSensory({ getContext: () => null }, node, { onArtSource })();
    expect(onArtSource).toHaveBeenCalledWith("");
  });
});

describe("scene renderer determinism", () => {
  it("draws the same frame for the same served node without reading the clock", () => {
    const first = render(0), again = render(0);
    expect(first.length).toBeGreaterThan(50);
    expect(again).toEqual(first);
    expect(render(40)).toEqual(render(40));
  });

  it("keeps every alpha within range, including a fully energised glow", () => {
    const charged = { ...node, senses: { ...node.senses, energy: 1 } };
    const log = [];
    const stop = startSensory(canvasFor(log), charged, {});
    stop();
    const alphas = log.filter(e => e[0] === "set" && e[1] === "globalAlpha").map(e => e[2]);
    expect(alphas.length).toBeGreaterThan(5);
    expect(alphas.every(a => a >= 0 && a <= 1)).toBe(true);
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

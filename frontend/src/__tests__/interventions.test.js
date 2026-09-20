// Behavior tests for the shared composer's outcome polling. The element is a
// plain script with no exports, so the custom-element registry captures it.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

let Composer;
beforeAll(async () => {
  class FakeElement {
    attachShadow() { this.shadowRoot = { activeElement: null, querySelector: () => null }; return this.shadowRoot; }
  }
  globalThis.HTMLElement = FakeElement;
  globalThis.customElements = { get: () => undefined, define: (_, cls) => { Composer = cls; } };
  globalThis.document = { createElement: () => ({ append() {}, style: {} }) };
  globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
  await import("../../../static/interventions.js");
});

function composer(responses) {
  const c = new Composer();
  c.isConnected = true;
  c.render = () => {}; c.renderRecent = () => {}; c.renderPending = () => {};
  const changed = vi.fn();
  c.ctx = { key: "invite", seed: 382, node: { name: "Mire-112" }, changed };
  c.request = vi.fn(async () => { const next = responses.shift(); if (next instanceof Error) throw next; return next; });
  return { c, changed };
}

describe("outcome polling", () => {
  afterEach(() => vi.useRealTimers());

  it("survives a failed poll, backs off once, and re-arms from the last known pending count", async () => {
    vi.useFakeTimers();
    const { c, changed } = composer([
      { participant: "p", recent: [{ pending: 2 }] },
      new Error("The world keeps its own pace."),
      { participant: "p", recent: [{ pending: 0 }] },
    ]);
    await c.load();
    expect(c.request).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(4000);
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.message).toBe("The world keeps its own pace.");
    await vi.advanceTimersByTimeAsync(4000);
    expect(c.request).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(4000);
    expect(c.request).toHaveBeenCalledTimes(3);
    expect(changed).toHaveBeenCalledTimes(1);
    expect(c.message).toBe("");
    await vi.advanceTimersByTimeAsync(30000);
    expect(c.request).toHaveBeenCalledTimes(3);
  });

  it("does not poll without pending arrivals and stops once the element is gone", async () => {
    vi.useFakeTimers();
    const idle = composer([{ participant: "p", recent: [{ pending: 0 }] }, new Error("unreachable")]);
    await idle.c.load();
    await vi.advanceTimersByTimeAsync(30000);
    expect(idle.c.request).toHaveBeenCalledTimes(1);
    const gone = composer([{ participant: "p", recent: [{ pending: 1 }] }, new Error("lost"), { recent: [{ pending: 1 }] }]);
    await gone.c.load();
    await vi.advanceTimersByTimeAsync(4000);
    expect(gone.c.request).toHaveBeenCalledTimes(2);
    gone.c.disconnectedCallback();
    await vi.advanceTimersByTimeAsync(30000);
    expect(gone.c.request).toHaveBeenCalledTimes(2);
  });
});

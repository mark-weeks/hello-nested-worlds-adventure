// Behavior tests for the shared composer's outcome polling. The element is a
// plain script with no exports, so the custom-element registry captures it.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

let Composer;
beforeAll(async () => {
  class FakeElement {
    attachShadow() { this.shadowRoot = { activeElement: null, querySelector: () => null, replaceChildren() {}, append() {} }; return this.shadowRoot; }
  }
  globalThis.HTMLElement = FakeElement;
  globalThis.customElements = { get: () => undefined, define: (_, cls) => { Composer = cls; } };
  globalThis.document = { createElement: tag => ({ tag, children: [], attrs: {}, style: {},
    append(...nodes) { this.children.push(...nodes); }, setAttribute(k, v) { this.attrs[k] = v; } }) };
  const stored = new Map();
  globalThis.localStorage = { getItem: k => stored.get(k) ?? null, setItem: (k, v) => stored.set(k, v), removeItem: k => stored.delete(k) };
  globalThis.EnfoldedIntents = { begin: async () => ({ request_id: "req-1" }), finish() {} };
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

describe("choices and context", () => {
  it("commits a suggestion directly and composes only when requested", async () => {
    const { c } = composer([{ participant: "p", recent: [] }]);
    await c.load(); c.commit = vi.fn();
    await c.choose({op:"engrave"});
    expect(c.commit).toHaveBeenCalledWith({steps:[{op:"engrave",amount:1}],version:3});
    c.compose=true;
    await c.choose({op:"polish"});
    expect(c.steps).toEqual([{op:"polish",amount:1}]);
    expect(c.commit).toHaveBeenCalledTimes(1);
    expect(c.request).toHaveBeenCalledTimes(1);
  });

  it("hands its acceptance to the host so the host's refresh coalesces with the broadcast", async () => {
    const result = { accepted: true, event_id: 41, node: "Mire-112", flavor: "Ada acts: Engrave.", changed: { surface: "engraved" } };
    const { c, changed } = composer([{ participant: "p", recent: [] }, result, { participant: "p", recent: [] }]);
    c.ctx.ensure = async () => {};
    await c.load();
    await c.commit({steps:[{op:"engrave",amount:1}],version:3});
    expect(changed).toHaveBeenCalledTimes(1);
    expect(changed.mock.calls[0][0]).toBe(result);
    expect(c.message).toBe("Ada acts: Engrave.");
    expect(c.pending).toBeNull();
  });

  it("reloads on a new served revision, never on a fresh node object", () => {
    const c = new Composer();
    c.isConnected = true;
    c.render = () => {}; c.renderRecent = () => {}; c.renderPending = () => {};
    c.request = vi.fn(async () => ({ participant: "p", recent: [] }));
    const at = (name, revision) => ({ key: "invite", seed: 382, node: { name, senses: { revision } } });
    c.context = at("Mire-112", "a");
    expect(c.request).toHaveBeenCalledTimes(1);
    c.context = at("Mire-112", "a");
    c.context = at("Mire-112", "a");
    expect(c.request).toHaveBeenCalledTimes(1);
    c.context = at("Mire-112", "b");
    expect(c.request).toHaveBeenCalledTimes(2);
    c.context = at("Vault-1121", "b");
    expect(c.request).toHaveBeenCalledTimes(3);
  });
});

function walk(node, out = []) {
  if (node && typeof node === "object") { out.push(node); for (const child of node.children || []) walk(child, out); }
  return out;
}

function rendered(c) {
  const roots = [];
  c.shadowRoot.replaceChildren = (...nodes) => roots.push(...nodes);
  c.shadowRoot.append = (...nodes) => roots.push(...nodes);
  c.shadowRoot.querySelector = () => null;
  c.render();
  return roots.flatMap(r => walk(r));
}

describe("resilience and accessibility", () => {
  it("offers a retry when the first read fails, and recovers on it", async () => {
    const { c } = composer([new Error("The world keeps its own pace."), { participant: "p", recent: [], choices: [] }]);
    delete c.render;
    await c.load();
    expect(c.data).toBeFalsy();
    const nodes = rendered(c);
    const again = nodes.find(n => n.tag === "button" && n.textContent === "Listen again");
    expect(again).toBeTruthy();
    expect(nodes.some(n => n.textContent === "The world keeps its own pace.")).toBe(true);
    await again.onclick();
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.data).toBeTruthy();
    expect(c.message).toBe("");
  });

  it("names why an action is unavailable, visibly and in the accessible name", async () => {
    const { c } = composer([{ participant: "p", recent: [], choices: [
      { op: "engrave", label: "Engrave", description: "Cut a pattern.", available: false, reason: "The surface is already engraved." },
      { op: "polish", label: "Polish", description: "Smooth it.", available: true, reason: null },
    ] }]);
    delete c.render;
    await c.load();
    const buttons = rendered(c).filter(n => n.tag === "button" && n.attrs["aria-label"]);
    const engrave = buttons.find(b => b.attrs["aria-label"].startsWith("Engrave"));
    const polish = buttons.find(b => b.attrs["aria-label"] === "Polish");
    expect(engrave.attrs["aria-label"]).toBe("Engrave. The surface is already engraved.");
    expect(engrave.disabled).toBe(true);
    expect(walk(engrave).some(n => n.tag === "small" && n.textContent === "The surface is already engraved.")).toBe(true);
    expect(polish.disabled).toBe(false);
    expect(walk(polish).every(n => n.textContent !== "Already as it would be.")).toBe(true);
  });
});

describe("receipt and observed-history recovery", () => {
  it("recovers an older saved preview-shaped commitment without previewing or moving again", async () => {
    const preview={steps:[{op:"engrave",amount:1}],expected:"e".repeat(24),version:2};
    const intent={key:"old-key",request_id:"old-accepted"};
    localStorage.setItem("nw_arrangement:p:382:Mire-112",JSON.stringify({intent,preview}));
    const receipt={accepted:true,event_id:12,node:"Mire-112",flavor:"Ada acts: Engrave."};
    const {c}=composer([{participant:"p",recent:[]},receipt,{participant:"p",recent:[]}]);
    c.ctx.ensure=vi.fn();
    await c.load();
    expect(c.pending).toEqual(intent);
    await c.commit();
    expect(c.request.mock.calls[1]).toEqual(["/interventions/commit",{...preview,request_id:"old-accepted"}]);
    expect(c.ctx.ensure).not.toHaveBeenCalled();
    expect(c.pending).toBeNull();
    expect(localStorage.getItem("nw_arrangement:p:382:Mire-112")).toBeNull();
  });

  it("refreshes missed observations even when one pending hop replaces another", async () => {
    const {c,changed}=composer([
      {participant:"p",recent:[{pending:1,event_id:1,arrivals:[]}]},
      {participant:"p",recent:[{pending:1,event_id:1,arrivals:[{event_id:2}]}]},
    ]);
    await c.load(); await c.load(true); c.disconnectedCallback();
    expect(changed).toHaveBeenCalledTimes(1);
  });
});

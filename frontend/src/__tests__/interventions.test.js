// Behavior tests for the shared composer's outcome polling. The element is a
// plain script with no exports, so the custom-element registry captures it.
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

let Composer;
beforeAll(async () => {
  class FakeElement {
    attachShadow() { this.shadowRoot = { activeElement: null, querySelector: () => null, replaceChildren() {}, append() {} }; return this.shadowRoot; }
  }
  globalThis.HTMLElement = FakeElement;
  globalThis.customElements = { get: () => undefined, define: (_, cls) => { Composer = cls; } };
  globalThis.document = { createElement: tag => ({ tag, children: [], attrs: {}, style: {},
    append(...nodes) { this.children.push(...nodes); }, setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] ?? null; }, focus() { globalThis.__focused = this; } }) };
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
      Object.assign(new Error("The world keeps its own pace."), {status:429}),
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
    const { c } = composer([new Error("Failed to fetch"), { participant: "p", recent: [], choices: [] }]);
    delete c.render;
    await c.load();
    expect(c.data).toBeFalsy();
    const nodes = rendered(c);
    const again = nodes.find(n => n.tag === "button" && n.textContent === "Listen again");
    expect(again).toBeTruthy();
    expect(nodes.some(n => n.textContent === "This place could not be heard. Listen again.")).toBe(true);
    await again.onclick();
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.data).toBeTruthy();
    expect(c.message).toBe("");
  });

  it("offers four directly usable suggestions without predicted availability", async () => {
    const choices = ["engrave", "polish", "mend", "fracture"].map(op => ({op,label:op,description:"Attempt it."}));
    const {c} = composer([{participant:"p",recent:[],choices}]);
    delete c.render;
    await c.load();
    const buttons = rendered(c).filter(n => n.tag === "button" && n.attrs["aria-label"]);
    expect(buttons).toHaveLength(4);
    expect(buttons.every(b => !b.disabled)).toBe(true);
    c.commit=vi.fn();await buttons[0].onclick();
    expect(c.commit).toHaveBeenCalledWith({steps:[{op:"engrave",amount:1}],version:3});
  });

  it("blocks empty intentions before position, receipt or commit requests", async () => {
    const {c} = composer([{participant:"p",recent:[],choices:[]}]);
    c.ctx.ensure=vi.fn();
    await c.load();delete c.render;
    const nodes=rendered(c), input=nodes.find(n=>n.tag==="textarea");
    const button=nodes.find(n=>n.tag==="button" && n.textContent==="Act on this intention");
    expect(button.disabled).toBe(true);
    input.value="  ";input.oninput();expect(button.disabled).toBe(true);
    const begin=vi.spyOn(globalThis.EnfoldedIntents,"begin");
    await c.commit({intention:"  ",version:3});
    expect(c.ctx.ensure).not.toHaveBeenCalled();expect(begin).not.toHaveBeenCalled();
    expect(c.request).toHaveBeenCalledTimes(1);
    input.value="engrave";input.oninput();expect(button.disabled).toBe(false);
    begin.mockRestore();
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

describe("another player's accepted action", () => {
  // Node has no window: give the module the global event target hosts use.
  const target = new EventTarget();
  beforeAll(() => {
    globalThis.addEventListener = target.addEventListener.bind(target);
    globalThis.removeEventListener = target.removeEventListener.bind(target);
    globalThis.dispatchEvent = target.dispatchEvent.bind(target);
  });
  afterAll(() => { delete globalThis.addEventListener; delete globalThis.removeEventListener; delete globalThis.dispatchEvent; });

  it("re-reads outcomes for this place only, without asking the host for the node again", async () => {
    vi.useFakeTimers();
    const { c, changed } = composer([
      { participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 1 }] },
      { participant: "p", recent: [] },
    ]);
    c.connectedCallback();
    // A delayed acceptance leaves the served revision unchanged: only the
    // announcement can tell this viewer that new work is pending here.
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Elsewhere-9", id: "x" });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).not.toHaveBeenCalled();
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "a" });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.data?.recent?.[0]?.performer).toBe("Ada");
    expect(c.request).toHaveBeenCalledTimes(1);
    expect(c.request).toHaveBeenCalledWith("/interventions");
    expect(changed).not.toHaveBeenCalled();
    c.disconnectedCallback();
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "b" });
    await vi.advanceTimersByTimeAsync(5000);
    expect(c.request).toHaveBeenCalledTimes(1);
  });

  it("owes each notice until a read that began after it succeeds, and reads once for a burst", async () => {
    vi.useFakeTimers();
    const { c } = composer([{ participant: "p", recent: [] }, { participant: "p", recent: [] }, { participant: "p", recent: [] }]);
    c.connectedCallback();
    const announce = notice => globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", changed: {}, ...notice });
    // Two opposite material changes can leave the served revision where it
    // was: both notices still get one history read between them.
    announce({ id: "a", changed: { star_density: 438 } });
    announce({ id: "b", changed: { star_density: 418 } });
    await vi.advanceTimersByTimeAsync(999);
    expect(c.request).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(c.request).toHaveBeenCalledTimes(1);
    // A read that starts after the notice (the host's node-revision reload)
    // covers it, so no second read follows.
    announce({ id: "c" });
    await c.load();
    await vi.advanceTimersByTimeAsync(5000);
    expect(c.request).toHaveBeenCalledTimes(2);
    c.disconnectedCallback();
  });

  it("reads again for a notice that arrived while an earlier read was in flight", async () => {
    vi.useFakeTimers();
    let release;
    const { c } = composer([]);
    c.request = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { release = () => resolve({ participant: "p", recent: [] }); }))
      .mockResolvedValue({ participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 1 }] });
    c.connectedCallback();
    const inFlight = c.load();
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "a", changed: {} });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(1); // waits for the read in flight
    release(); await inFlight;
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.data.recent[0].performer).toBe("Ada");
    c.disconnectedCallback();
  });

  it("keeps a notice received during a submission that is not accepted", async () => {
    vi.useFakeTimers();
    let reply;
    const { c } = composer([]);
    c.request = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { reply = resolve; }))
      .mockResolvedValue({ participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 1 }] });
    c.data = { participant: "p", recent: [], choices: [] };
    c.storageKey = "nw_arrangement:test";
    c.connectedCallback();
    const submitting = c.commit({ intention: "kindle what", version: 3 });
    await vi.advanceTimersByTimeAsync(0);
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "peer", changed: {} });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(1); // the submission is still open
    reply({ accepted: false, response: "Which stars do you mean?" });
    await submitting;
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.request.mock.calls[1][0]).toBe("/interventions");
    expect(c.message).toBe("Which stars do you mean?");
    c.disconnectedCallback();
  });

  it("still reads for its own echo and later arrivals after its own history read failed", async () => {
    vi.useFakeTimers();
    const { c } = composer([
      { id: "mine", accepted: true, flavor: "Bea begins Kindle." },                 // commit reply
      Object.assign(new Error("The world keeps its own pace."), { status: 429 }),  // its history read
      { participant: "p", recent: [{ performer: "Bea", summary: "Kindle", pending: 1, arrivals: [] }] },
      { participant: "p", recent: [{ performer: "Bea", summary: "Kindle", pending: 0, arrivals: [{ event_id: 9 }] }] },
    ]);
    c.data = { participant: "p", recent: [], choices: [] };
    c.storageKey = "nw_arrangement:test";
    c.connectedCallback();
    await c.commit({ steps: [{ op: "kindle", amount: 1 }], version: 3 });
    expect(c.request).toHaveBeenCalledTimes(2);
    // The socket echo reuses the intervention id; nothing is skipped by id.
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "mine", event_id: 7, changed: {} });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(3);
    expect(c.data.recent[0].performer).toBe("Bea");
    clearTimeout(c.poll);
    // A later arrival under the same id that changes nothing is read too.
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "mine", event_id: 8, changed: {} });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(4);
    expect(c.data.recent[0].arrivals).toHaveLength(1);
    c.disconnectedCallback();
  });

  it("does not retry a background read the server refuses, and reads again on the next notice", async () => {
    vi.useFakeTimers();
    const refused = () => Object.assign(new Error("The seal still guards this place."), { status: 403 });
    const { c } = composer([refused(), refused()]);
    c.message = "Bea acts: the stars kindle.";
    c.connectedCallback();
    const announce = id => globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id, changed: {} });
    announce("a");
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000);   // no retry loop
    expect(c.request).toHaveBeenCalledTimes(1);
    expect(c.message).toBe("Bea acts: the stars kindle.");
    announce("b");                                       // the notice is still owed
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(2);
    c.disconnectedCallback();
  });

  it("reads within one window of the first notice under a steady stream", async () => {
    vi.useFakeTimers();
    const { c } = composer(Array.from({ length: 30 }, () => ({ participant: "p", recent: [] })));
    c.connectedCallback();
    const announce = id => globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id, changed: {} });
    announce("0");
    for (let i = 1; i <= 20; i++) { await vi.advanceTimersByTimeAsync(900); announce(String(i)); } // 18 s of notices
    // A restarting debounce gave 0 reads here; one read per window is expected.
    expect(c.request.mock.calls.length).toBeGreaterThanOrEqual(9);
    expect(c.request.mock.calls.length).toBeLessThanOrEqual(19);
    const during = c.request.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5000);             // the last notice is covered once
    expect(c.request.mock.calls.length).toBe(during + 1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(c.request.mock.calls.length).toBe(during + 1);
    c.disconnectedCallback();
  });

  it("keeps the receipt through polls that an announced read started", async () => {
    vi.useFakeTimers();
    const { c } = composer([
      { participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 1 }] },
      Object.assign(new Error("This place could not be heard."), { status: 503 }),
      { participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 0 }] },
    ]);
    c.message = "Bea acts: the stars kindle.";
    c.connectedCallback();
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "a", changed: {} });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(4000);   // the pending poll fails
    expect(c.request).toHaveBeenCalledTimes(2);
    expect(c.message).toBe("Bea acts: the stars kindle.");
    await vi.advanceTimersByTimeAsync(8000);   // and recovers
    expect(c.request).toHaveBeenCalledTimes(3);
    expect(c.message).toBe("Bea acts: the stars kindle.");
    c.disconnectedCallback();
  });

  it("keeps this viewer's own receipt when an announced read fails, and retries with backoff", async () => {
    vi.useFakeTimers();
    const { c } = composer([
      Object.assign(new Error("The world keeps its own pace."), {status:429}),
      Object.assign(new Error("The world keeps its own pace."), {status:429}),
      { participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 0 }] },
    ]);
    c.message = "Bea acts: the stars kindle.";
    c.connectedCallback();
    globalThis.EnfoldedInterventions.announce({ type: "intervention_changed", node: "Mire-112", id: "a" });
    await vi.advanceTimersByTimeAsync(1000);
    expect(c.request).toHaveBeenCalledTimes(1);
    expect(c.message).toBe("Bea acts: the stars kindle.");
    // Nothing was pending before, yet the failed announced read is retried: 8 s, then 16 s.
    await vi.advanceTimersByTimeAsync(8000);
    expect(c.request).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(15999);
    expect(c.request).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(c.request).toHaveBeenCalledTimes(3);
    expect(c.data.recent[0].performer).toBe("Ada");
    expect(c.message).toBe("Bea acts: the stars kindle.");
    await vi.advanceTimersByTimeAsync(120000);
    expect(c.request).toHaveBeenCalledTimes(3);
    c.disconnectedCallback();
  });

  it("keeps keyboard focus on the same observed arrival when history refreshes", () => {
    const { c } = composer([]);
    delete c.renderRecent;
    globalThis.EnfoldedClient = { displayName: name => name };
    const root = { children: [], replaceChildren(...nodes) { this.children = nodes; }, append(...nodes) { this.children.push(...nodes); },
      contains: node => node === focusedBefore,
      querySelectorAll() { return this.children.flatMap(n => n.children || []).filter(n => n.tag === "button"); } };
    const focusedBefore = { getAttribute: k => k === "data-focus-key" ? "observed:41" : null };
    c.shadowRoot.activeElement = focusedBefore;
    c.shadowRoot.querySelector = selector => selector === ".recent" ? root : null;
    c.data = { recent: [{ performer: "Ada", summary: "Kindle", pending: 1, origin: "Mire-112",
      arrivals: [{ node: "Mire-112", event_id: 40 }, { node: "Mire-1", event_id: 41 }] }] };
    globalThis.__focused = null;
    c.renderRecent();
    expect(globalThis.__focused?.getAttribute("data-focus-key")).toBe("observed:41");
    expect(globalThis.__focused).not.toBe(focusedBefore);
  });

  it("adds the first record's disclosure in place while a control keeps focus", async () => {
    const { c } = composer([{ participant: "p", recent: [{ performer: "Ada", summary: "Kindle", pending: 1, arrivals: [] }] }]);
    const section = { append: vi.fn() };
    let recent = null;
    c.shadowRoot.activeElement = { tag: "button" };
    c.shadowRoot.querySelector = selector => selector === ".choices" ? {} : selector === "section" ? section : selector === ".recent" ? recent : null;
    c.render = vi.fn();
    c.renderRecent = vi.fn();
    await c.load(false, true);
    clearTimeout(c.poll);
    expect(c.render).not.toHaveBeenCalled();
    expect(section.append).toHaveBeenCalledTimes(1);
    expect(section.append.mock.calls[0][0].tag).toBe("details");
    expect(c.renderRecent).toHaveBeenCalledTimes(1);
    // Once the disclosure exists, a later read only refreshes its rows.
    recent = {};
    c.ensureHistory();
    expect(section.append).toHaveBeenCalledTimes(1);
  });
});

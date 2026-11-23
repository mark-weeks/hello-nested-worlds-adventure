// Behavior tests for the canonical non-linear entry rules shared by both
// browser clients.
import { describe, expect, it } from "vitest";
import {
  addressDepth, addressPath, destinationAddress, dropInNode, entryPath, findNodeAddress,
  findPath, lookupNodeAddress, placeUnreachedLine, rememberAddress, resumeDepth, savedAddress,
} from "../entry.js";

function world() {
  // A small tree shaped like the real thing: names unique, mid nodes exist.
  return {
    name: "Aethon-1", children: [
      { name: "Aldric-11", children: [
        { name: "Vela-111", children: [] },
        { name: "Vela-112", children: [
          { name: "Kaelos-1121", children: [] },
        ]},
      ]},
      { name: "Mireth-12", children: [] },
    ],
  };
}

describe("findPath", () => {
  it("returns the full root→node ancestry", () => {
    const path = findPath(world(), "Kaelos-1121").map(n => n.name);
    expect(path).toEqual(["Aethon-1", "Aldric-11", "Vela-112", "Kaelos-1121"]);
  });

  it("returns null for unknown nodes", () => {
    expect(findPath(world(), "Nowhere-99")).toBeNull();
  });
});

describe("dropInNode", () => {
  it("is deterministic per player name", () => {
    const a = dropInNode(world(), "Ada");
    const b = dropInNode(world(), "Ada");
    expect(a.name).toBe(b.name);
  });

  it("prefers mid-world nodes (a parent and children both exist)", () => {
    const node = dropInNode(world(), "Ada");
    expect(node.name).not.toBe("Aethon-1");
    expect(node.children.length).toBeGreaterThan(0);
  });
});

describe("entryPath", () => {
  it("resumes a saved node when it still exists", () => {
    const path = entryPath(world(), "Vela-112", "Ada").map(n => n.name);
    expect(path[path.length - 1]).toBe("Vela-112");
  });

  it("falls back to a deterministic drop-in when the saved node is gone", () => {
    const a = entryPath(world(), "Gone-77", "Ada").map(n => n.name);
    const b = entryPath(world(), null, "Ada").map(n => n.name);
    expect(a).toEqual(b);
  });
});

describe("resumeDepth", () => {
  it("restores a saved view depth within the launch window", () => {
    expect(resumeDepth(8, "14322121")).toBe(8);
  });

  it("infers enough depth from a saved address when depth metadata is stale", () => {
    expect(resumeDepth(6, "1432212121")).toBe(10);
  });

  it("clamps untrusted saved depth to the eleven-scale world", () => {
    expect(resumeDepth(99, "1")).toBe(11);
  });

  it("reads no depth out of a name", () => {
    expect(resumeDepth(6, "Still River Gallery-1432212121")).toBe(6);
    expect(resumeDepth(6, "Still River Gallery")).toBe(6);
    expect(resumeDepth(6, null)).toBe(6);
  });
});

describe("addresses", () => {
  // The same tree with three-word names: position lives in `address` alone.
  function named() {
    return {
      name: "Aethon", address: "1", children: [
        { name: "Aldric", address: "11", children: [
          { name: "Vela", address: "111", children: [] },
          { name: "Sable", address: "112", children: [
            { name: "Kaelos", address: "1121", children: [] },
          ]},
        ]},
        { name: "Mireth", address: "12", children: [] },
      ],
    };
  }

  it("an address is as deep as it has steps", () => {
    expect(addressDepth("1")).toBe(1);
    expect(addressDepth("11431112111")).toBe(11);
    expect(addressDepth("Kaelos-1121")).toBeNull();
    expect(addressDepth("")).toBeNull();
    expect(addressDepth(undefined)).toBeNull();
  });

  it("walks from the root to the place an address names", () => {
    expect(addressPath(named(), "1121").map(n => n.name)).toEqual(["Aethon", "Aldric", "Sable", "Kaelos"]);
    expect(addressPath(named(), "12").map(n => n.name)).toEqual(["Aethon", "Mireth"]);
    expect(addressPath(named(), "1").map(n => n.name)).toEqual(["Aethon"]);
  });

  it("stops at the deepest ancestor this view holds", () => {
    expect(addressPath(named(), "11213").map(n => n.name)).toEqual(["Aethon", "Aldric", "Sable", "Kaelos"]);
    expect(addressPath(named(), "1211").map(n => n.name)).toEqual(["Aethon", "Mireth"]);
  });

  it("walks nowhere without an address", () => {
    expect(addressPath(named(), "Kaelos")).toBeNull();
    expect(addressPath(named(), null)).toBeNull();
    expect(addressPath(null, "11")).toBeNull();
  });
});

describe("the saved place's address", () => {
  const storage = (initial = {}) => {
    const values = new Map(Object.entries(initial));
    return {
      values,
      getItem: key => (values.has(key) ? values.get(key) : null),
      setItem: (key, value) => values.set(key, String(value)),
      removeItem: key => values.delete(key),
    };
  };

  it("is read back for the place it was saved with", () => {
    const store = storage({ nw_last_node: "Still River Gallery" });
    rememberAddress(store, "Still River Gallery", "14322121");
    expect(savedAddress(store)).toBe("14322121");
    expect(resumeDepth(6, savedAddress(store))).toBe(8);
  });

  it("is not read for a different saved place", () => {
    // Another tab, an older client or a test may write the name alone.
    const store = storage({ nw_last_node: "Still River Gallery" });
    rememberAddress(store, "Still River Gallery", "14322121");
    store.setItem("nw_last_node", "Elder Reed Cosmos");
    expect(savedAddress(store)).toBeNull();
  });

  it("is dropped when the place has no address", () => {
    const store = storage({ nw_last_node: "Still River Gallery" });
    rememberAddress(store, "Still River Gallery", "14322121");
    rememberAddress(store, "Still River Gallery", null);
    expect(store.values.has("nw_last_address")).toBe(false);
    expect(savedAddress(store)).toBeNull();
    expect(savedAddress(storage())).toBeNull();
  });
});

describe("lookupNodeAddress", () => {
  const answer = (status, body) => async () => ({
    ok: status >= 200 && status < 300, status, json: async () => body,
  });
  const MISSING = { status: "missing" };
  const RETRY = { status: "retry" };

  it("asks the server where a place known only by name stands", async () => {
    const read = answer(200, { node: { name: "Still River Gallery", address: "14322121" } });
    expect(await lookupNodeAddress(read, "/node?node_name=Still%20River%20Gallery"))
      .toEqual({ status: "resolved", address: "14322121" });
  });

  it("is missing when the server answers that the world holds no such place", async () => {
    expect(await lookupNodeAddress(answer(404, { error: "no such place in this world" }), "/node")).toEqual(MISSING);
    expect(await lookupNodeAddress(answer(400, { error: "invalid" }), "/node")).toEqual(MISSING);
    expect(await lookupNodeAddress(answer(403, { error: "invite required" }), "/node")).toEqual(MISSING);
    // A place sent without the address field: the name is never read for one.
    expect(await lookupNodeAddress(answer(200, { node: { name: "Still River Gallery-14322121" } }), "/node")).toEqual(MISSING);
    expect(await lookupNodeAddress(answer(200, {}), "/node")).toEqual(MISSING);
  });

  it("is retryable when the question was not answered", async () => {
    for (const status of [500, 502, 503, 504, 428, 429, 408]) {
      expect(await lookupNodeAddress(answer(status, { error: "later" }), "/node"), String(status)).toEqual(RETRY);
    }
    expect(await lookupNodeAddress(async () => { throw new Error("offline"); }, "/node")).toEqual(RETRY);
    expect(await lookupNodeAddress(
      async () => ({ ok: true, status: 200, json: async () => { throw new Error("not JSON"); } }), "/node",
    )).toEqual(RETRY);
  });

  it("never rejects and never hands back a bare null", async () => {
    for (const read of [answer(404, {}), answer(503, {}), async () => { throw new Error("x"); }]) {
      expect((await lookupNodeAddress(read, "/node")).status).toMatch(/^(missing|retry)$/);
    }
  });
});

describe("findNodeAddress", () => {
  const reply = (status, body = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
  // Answers in order, repeating the last; records the pauses between reads.
  function script(...replies) {
    const waits = [];
    let reads = 0;
    const read = async () => {
      const next = replies[Math.min(reads++, replies.length - 1)];
      if (next instanceof Error) throw next;
      return next;
    };
    return { read, waits, reads: () => reads, wait: async ms => { waits.push(ms); } };
  }
  const found = reply(200, { node: { name: "Cedar Anchor Quark", address: "11111111111" } });

  it("asks again after a failed read and arrives at the answer", async () => {
    const s = script(reply(503), found);
    expect(await findNodeAddress(s.read, "/node", { wait: s.wait }))
      .toEqual({ status: "resolved", address: "11111111111" });
    expect(s.reads()).toBe(2);
    expect(s.waits).toEqual([300]);
  });

  it("does not ask again once the answer is definite", async () => {
    const hit = script(found);
    await findNodeAddress(hit.read, "/node", { wait: hit.wait });
    expect([hit.reads(), hit.waits]).toEqual([1, []]);
    const miss = script(reply(404));
    expect(await findNodeAddress(miss.read, "/node", { wait: miss.wait })).toEqual({ status: "missing" });
    expect([miss.reads(), miss.waits]).toEqual([1, []]);
  });

  it("gives up after a bounded number of reads and stays retryable", async () => {
    const s = script(new Error("offline"));
    expect(await findNodeAddress(s.read, "/node", { wait: s.wait })).toEqual({ status: "retry" });
    expect(s.reads()).toBe(3);
    expect(s.waits).toEqual([300, 900]);
  });

  it("a failure that turns into a 404 is missing, not pending", async () => {
    const s = script(reply(502), reply(404));
    expect(await findNodeAddress(s.read, "/node", { wait: s.wait })).toEqual({ status: "missing" });
  });
});

describe("destinationAddress", () => {
  const never = async () => { throw new Error("the server must not be asked"); };

  it("uses the address that came with the name without asking", async () => {
    expect(await destinationAddress("Cedar Anchor Quark", "11111111111", never))
      .toEqual({ status: "resolved", address: "11111111111" });
  });

  it("has nothing to wait for when no place is named", async () => {
    expect(await destinationAddress(null, null, never)).toEqual({ status: "missing" });
    expect(await destinationAddress("", "112", never)).toEqual({ status: "missing" });
  });

  it("asks for a name-only place and passes each of the three answers through", async () => {
    const asked = [];
    for (const answer of [
      { status: "resolved", address: "1121" }, { status: "missing" }, { status: "retry" },
    ]) {
      const got = await destinationAddress("Still River Gallery", null, async name => {
        asked.push(name);
        return answer;
      });
      expect(got).toEqual(answer);
    }
    expect(asked).toEqual(Array(3).fill("Still River Gallery"));
  });

  it("asks when the address that came with the name is not one", async () => {
    const got = await destinationAddress("Still River Gallery", "not-digits", async () => ({ status: "retry" }));
    expect(got).toEqual({ status: "retry" });
  });

  // The rule both clients apply to the answer: only a retryable one holds
  // the arrival; a place saved by name alone keeps its record meanwhile.
  it("a pending place leaves the saved position as it was", async () => {
    const kept = new Map([["nw_last_node", "Cedar Anchor Quark"]]);
    const storage = {
      getItem: key => (kept.has(key) ? kept.get(key) : null),
      setItem: (key, value) => kept.set(key, String(value)),
      removeItem: key => kept.delete(key),
    };
    const name = storage.getItem("nw_last_node");
    const pending = await destinationAddress(name, savedAddress(storage), async () => ({ status: "retry" }));
    if (pending.status !== "retry") rememberAddress(storage, name, pending.address);
    expect([...kept]).toEqual([["nw_last_node", "Cedar Anchor Quark"]]);
    const found = await destinationAddress(name, savedAddress(storage),
      async () => ({ status: "resolved", address: "11111111111" }));
    if (found.status !== "retry") rememberAddress(storage, name, found.address);
    expect(savedAddress(storage)).toBe("11111111111");
    expect(resumeDepth(6, savedAddress(storage), 6, 11)).toBe(11);
  });
});

describe("placeUnreachedLine", () => {
  it("names the place as it reads and carries no raw error", () => {
    expect(placeUnreachedLine("Cedar Anchor Quark"))
      .toBe("… Cedar Anchor Quark could not be found just now. Try again in a moment.");
  });
});

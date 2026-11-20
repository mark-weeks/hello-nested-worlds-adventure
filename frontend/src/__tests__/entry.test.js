// Behavior tests for the canonical non-linear entry rules shared by both
// browser clients.
import { describe, expect, it } from "vitest";
import {
  addressDepth, addressPath, dropInNode, entryPath, findPath, readNodeAddress,
  rememberAddress, resumeDepth, savedAddress,
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

describe("readNodeAddress", () => {
  const answer = (status, body) => async () => ({
    ok: status >= 200 && status < 300, status, json: async () => body,
  });

  it("asks the server where a place known only by name stands", async () => {
    const read = answer(200, { node: { name: "Still River Gallery", address: "14322121" } });
    expect(await readNodeAddress(read, "/node?node_name=Still%20River%20Gallery")).toBe("14322121");
  });

  it("is null for an unknown place, a refusal or a lost read", async () => {
    expect(await readNodeAddress(answer(404, { error: "Node not found" }), "/node")).toBeNull();
    expect(await readNodeAddress(answer(200, { node: { name: "Still River Gallery-14322121" } }), "/node")).toBeNull();
    expect(await readNodeAddress(async () => { throw new Error("offline"); }, "/node")).toBeNull();
    expect(await readNodeAddress(async () => ({ ok: true, json: async () => { throw new Error("not JSON"); } }), "/node")).toBeNull();
  });
});

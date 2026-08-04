// Behavior tests for the canonical non-linear entry rules shared by both
// browser clients.
import { describe, expect, it } from "vitest";
import { dropInNode, entryPath, findPath, resumeDepth } from "../entry.js";

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
    expect(resumeDepth(8, "Still River Gallery-14322121")).toBe(8);
  });

  it("infers enough depth from a saved node when depth metadata is stale", () => {
    expect(resumeDepth(6, "Still River Gallery-1432212121")).toBe(10);
  });

  it("clamps untrusted saved depth to the eleven-scale world", () => {
    expect(resumeDepth(99, "Elder Reed Cosmos-1")).toBe(11);
  });
});

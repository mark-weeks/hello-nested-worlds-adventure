// Behavior tests for non-linear entry resolution. These functions are
// hand-mirrored in static/explorer.js — the parity test at the bottom
// executes BOTH copies on the same input and fails if they ever drift
// (previously they were guarded only by substring greps).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { dropInNode, entryPath, findPath } from "../entry.js";

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

describe("explorer.js parity", () => {
  // Execute the hand-mirrored copies from static/explorer.js against the
  // same inputs. A tweak to one client's hash or candidate-pool logic that
  // doesn't reach the other now fails a test instead of silently
  // desynchronizing cross-client entry points.
  const here = dirname(fileURLToPath(import.meta.url));
  const explorerSrc = readFileSync(
    join(here, "../../../static/explorer.js"), "utf8");

  function extract(name) {
    const start = explorerSrc.indexOf(`function ${name}(`);
    if (start === -1) throw new Error(`function ${name} not found in explorer.js`);
    let depth = 0, i = explorerSrc.indexOf("{", start);
    const open = i;
    for (; i < explorerSrc.length; i++) {
      if (explorerSrc[i] === "{") depth++;
      if (explorerSrc[i] === "}") depth--;
      if (depth === 0) break;
    }
    return explorerSrc.slice(start, i + 1);
  }

  it("dropInNode agrees between the two clients for many names", () => {
    const code = `${extract("_entryHash")}\n${extract("dropInNode")}\n` +
      // explorer's dropInNode calls _entryHash; expose it for the test.
      `return dropInNode;`;
    // eslint-disable-next-line no-new-func
    const explorerDropIn = new Function(code)();
    for (const name of ["Ada", "Bob", "Wendy", "Mallory", "æøå", ""]) {
      expect(explorerDropIn(world(), name).name)
        .toBe(dropInNode(world(), name).name);
    }
  });
});

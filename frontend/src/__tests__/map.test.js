import { describe, expect, it } from "vitest";
import { mapLayout, mapNeighbor } from "../components/MapView.jsx";

// Identical display names in different branches still have distinct positions.
function place(path, remaining) {
  return {
    name: `Harbor-${path}`,
    children: remaining ? [1, 2, 3, 4].map(i => place(path + i, remaining - 1)) : [],
  };
}

describe("browsing the shared world map", () => {
  const world = place("1", 6);
  const here = "Harbor-1111111";

  it("opens the selected lineage and its siblings without drawing each of 5,461 places", () => {
    const map = mapLayout(world, here, here);
    expect(map.nodes).toHaveLength(25);
    expect(map.links).toHaveLength(24);
    expect(map.nodes.map(node => node.data.name)).toContain("Harbor-1111114");
    expect(map.nodes.map(node => node.data.name)).not.toContain("Harbor-1444444");
    expect(map.trail.size).toBe(7);
  });

  it("can browse into another branch without moving the player's marker", () => {
    let browsing = here;
    function browse(key) {
      const map = mapLayout(world, here, browsing);
      expect(map.nodes.some(node => node.data.name === here)).toBe(true);
      const cursor = map.nodes.find(node => node.data.name === map.cursor);
      const next = mapNeighbor(cursor, key);
      if (next) browsing = next.data.name;
    }
    for (let level = 0; level < 6; level++) browse("ArrowLeft");
    browse("ArrowRight");
    browse("ArrowDown");
    browse("ArrowDown");
    browse("ArrowUp");
    for (let level = 0; level < 5; level++) browse("ArrowRight");
    expect(browsing).toBe("Harbor-1211111");
    browse("ArrowRight"); // No destination below a leaf.
    expect(browsing).toBe("Harbor-1211111");
  });
});

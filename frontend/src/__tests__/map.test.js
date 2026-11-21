import { describe, expect, it } from "vitest";
import { mapLayout, mapNeighbor, mapSealLabel } from "../components/MapView.jsx";

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

  it("gives every marker in a column a full row, including across browsed branches", () => {
    const map = mapLayout(world, here, "Harbor-1444444");
    for (let depth = 0; depth < map.columns; depth++) {
      const centers = map.nodes.filter(node => node.depth === depth)
        .map(node => node.top).sort((a, b) => a - b);
      expect(centers[0]).toBeGreaterThanOrEqual(0.5);
      expect(centers.at(-1)).toBeLessThanOrEqual(map.rows - 0.5);
      for (let i = 1; i < centers.length; i++) {
        expect(centers[i] - centers[i - 1]).toBeGreaterThanOrEqual(1);
      }
    }
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

  it("marks the Room threshold and its descendants while keeping the whole branch navigable", () => {
    const grain = { name: "Grain", level: "Molecule" };
    const bowl = { name: "Bowl", level: "Object", children: [grain] };
    const vault = { name: "Vault", level: "Room", properties: { locked: true }, children: [bowl] };
    const porch = { name: "Porch", level: "Room", properties: { locked: false } };
    const ridge = { name: "Ridge", level: "Region", properties: { locked: true }, children: [vault, porch] };

    // Browse from outside, then revisit the same branch from inside. Entering
    // can succeed after the Room's puzzle is solved, while its lock trait stays.
    for (const here of [ridge.name, bowl.name]) {
      const { nodes } = mapLayout(ridge, here, grain.name);
      const places = Object.fromEntries(nodes.map(node => [node.data.name, node]));
      expect(mapSealLabel(places.Ridge)).toBeNull(); // Only a Room can guard entry.
      expect(mapSealLabel(places.Porch)).toBeNull();
      expect(mapSealLabel(places.Vault)).toBe("Seal threshold");
      expect(mapSealLabel(places.Bowl)).toBe("Beyond a seal");
      expect(mapSealLabel(places.Grain)).toBe("Beyond a seal");
      expect(mapNeighbor(places.Vault, "ArrowRight")).toBe(places.Bowl);
      expect(mapNeighbor(places.Grain, "ArrowLeft")).toBe(places.Bowl);
    }
  });
});

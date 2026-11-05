import { afterEach, describe, expect, it, vi } from "vitest";

async function enter(address, saved = {}) {
  vi.resetModules();
  const values = new Map(Object.entries(saved));
  vi.stubGlobal("localStorage", {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  });
  vi.stubGlobal("location", new URL(address));
  vi.stubGlobal("history", {
    replaceState: vi.fn((state, title, url) => {
      vi.stubGlobal("location", new URL(url));
    }),
  });
  return {auth: await import("../auth.js"), values};
}

afterEach(() => vi.unstubAllGlobals());

describe("pilot invitation and return", () => {
  it("remembers the invited traveler before cleaning the address", async () => {
    const {auth, values} = await enter(
      "https://world.test/app?key=nw_invited&name=Ada%20Lovelace&node=Place-111#interactions",
    );
    expect(auth.betaKey()).toBe("nw_invited");
    expect(auth.urlName()).toBe("Ada Lovelace");
    expect(values.get("nw_player_name")).toBe("Ada Lovelace");
    expect(location.href).toBe("https://world.test/app?node=Place-111#interactions");
    expect(auth.withKey("/position")).toBe("/position?key=nw_invited");

    // A full page navigation reinitializes auth without the invitation URL.
    const returned = await enter("https://world.test/app", Object.fromEntries(values));
    expect(returned.auth.betaKey()).toBe("nw_invited");
    expect(returned.values.get("nw_player_name")).toBe("Ada Lovelace");
    expect(history.replaceState).not.toHaveBeenCalled();
  });

  it("uses the invitation's name when this browser remembers another name", async () => {
    const {values} = await enter("https://world.test/app?key=nw_new&name=Bea", {
      nw_beta_key: "nw_previous", nw_player_name: "Ada",
      nw_last_node: "Private bookmark-111", nw_view_depth: "11",
    });
    expect(values.get("nw_player_name")).toBe("Bea");
  });

  it("keeps the arrival fallback through credential rotation", async () => {
    const {auth, values} = await enter("https://world.test/app?key=nw_rotated&name=Ada", {
      nw_beta_key: "nw_previous", nw_player_name: "Ada",
      nw_last_node: "Home-111", nw_view_depth: "8",
    });
    expect(auth.betaKey()).toBe("nw_rotated");
    expect(values.get("nw_player_name")).toBe("Ada");
    expect(values.get("nw_last_node")).toBe("Home-111");
    expect(values.get("nw_view_depth")).toBe("8");
  });
});

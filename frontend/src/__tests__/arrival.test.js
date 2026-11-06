import { describe, expect, it } from "vitest";
import { arrivalScreen, openWorld } from "../arrival.js";

const shared = globalThis.EnfoldedClient;

// A fetch stand-in that answers like the real server: JSON bodies with a
// status, or a transport failure that rejects.
const answering = (status, body) => async () => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => {
    if (typeof body === "string") throw new SyntaxError(`Unexpected token '<', "${body}"`);
    return body;
  },
});
const unreachable = async () => { throw new TypeError("Failed to fetch"); };

// The screen a fresh browser shows once its /world read has settled.
async function settle(read, { hasKey = false, introSeen = false, named = false } = {}) {
  const opened = await openWorld(read, "/world?depth=6", hasKey);
  return {
    opened,
    screen: arrivalScreen({
      loading: false, hasNode: !!opened.data, unopened: opened.unopened ?? null,
      introSeen, named,
    }),
  };
}

describe("a world that does not open", () => {
  it("answers a keyless gate refusal with the invite line, not the loading shell", async () => {
    // A bookmark or new device: no stored key, no intro seen, no name.
    const { opened, screen } = await settle(answering(403, { error: "forbidden" }));
    expect(opened.unopened).toEqual({ kind: "invite", line: shared.WORLD_INVITE_LINE });
    expect(opened.unopened.line).toContain("open the invite link you were sent");
    expect(opened.unopened.line).not.toMatch(/forbidden|403/i);
    expect(screen).toBe("gate");
  });

  it("keeps a refused invitation neutral", async () => {
    // Unknown, revoked and sanctioned keys all meet the same bare 403.
    const { opened, screen } = await settle(answering(403, { error: "forbidden" }),
      { hasKey: true, introSeen: true, named: true });
    expect(opened.unopened).toEqual({ kind: "refused", line: shared.WORLD_REFUSED_LINE });
    expect(opened.unopened.line).not.toMatch(/forbidden|revok|suspend|ban|sanction/i);
    expect(screen).toBe("gate");
  });

  it("answers a network failure with the retry line once onboarding is done", async () => {
    const { opened, screen } = await settle(unreachable, { introSeen: true, named: true });
    expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
    expect(opened.unopened.line).not.toContain("Failed to fetch");
    expect(screen).toBe("retry");
  });

  it("lets onboarding finish before showing the retry line", async () => {
    const opened = await openWorld(unreachable, "/world", false);
    const base = { loading: false, hasNode: false, unopened: opened.unopened };
    expect(arrivalScreen({ ...base, introSeen: false, named: false })).toBe("intro");
    expect(arrivalScreen({ ...base, introSeen: true, named: false })).toBe("name");
  });

  it("answers a server failure or a non-JSON page with the retry line", async () => {
    for (const read of [
      answering(500, { error: "internal error" }),
      answering(502, "<html>Bad Gateway</html>"),
      answering(200, "<html>captive portal</html>"),
    ]) {
      const { opened } = await settle(read, { hasKey: true });
      expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
    }
  });

  it("keeps the server's own line for a paced or refused read", async () => {
    const pace = "the world asks for a quieter pace — a breath, then try again";
    const { opened } = await settle(answering(429, { error: pace }), { hasKey: true });
    expect(opened.unopened).toEqual({ kind: "retry", line: pace });
  });

  it("opens the world when the read succeeds", async () => {
    const world = { seed: 382, world: { name: "Root-1" } };
    const { opened } = await settle(answering(200, world), { hasKey: true });
    expect(opened).toEqual({ data: world });
  });
});

describe("arrival screens", () => {
  const ready = { introSeen: true, named: true };

  it("shows the loading shell only while a read is in flight", () => {
    expect(arrivalScreen({ ...ready, loading: true, hasNode: false, unopened: null })).toBe("loading");
    // A retry from the gate or the retry line is in flight again.
    const unopened = { kind: "invite", line: shared.WORLD_INVITE_LINE };
    expect(arrivalScreen({ ...ready, loading: true, hasNode: false, unopened })).toBe("loading");
    expect(arrivalScreen({ ...ready, loading: false, hasNode: true, unopened: null })).toBe("scene");
  });

  it("keeps the scene when a later read fails with a place in hand", () => {
    const unopened = { kind: "retry", line: shared.WORLD_UNREACHED_LINE };
    expect(arrivalScreen({ ...ready, loading: false, hasNode: true, unopened })).toBe("scene");
  });
});

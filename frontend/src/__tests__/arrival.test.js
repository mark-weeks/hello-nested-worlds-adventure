import { describe, expect, it } from "vitest";
import { arrivalScreen, openWorld } from "../arrival.js";

const shared = globalThis.EnfoldedClient;
const { hearSpeech } = shared;

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
      introSeen, named, hasKey,
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

  it("lets onboarding finish before showing the retry line to a browser with a key", async () => {
    // Review of bd8f904 (F2): this case used to loop over hasKey [false, true].
    // A keyless browser now gets the retry line before onboarding (next case),
    // so only the browser with a key still reads the introduction first.
    const opened = await openWorld(unreachable, "/world", true);
    const base = { loading: false, hasNode: false, unopened: opened.unopened, hasKey: true };
    expect(arrivalScreen({ ...base, introSeen: false, named: false })).toBe("intro");
    expect(arrivalScreen({ ...base, introSeen: true, named: false })).toBe("name");
  });

  it("shows a keyless browser the retry line before onboarding when no answer came", async () => {
    // A 502 during a deploy or a dropped connection: the gate has not
    // answered, and asking again may still meet it, so neither the
    // introduction nor the name entry comes first.
    for (const read of [answering(502, "<html>Bad Gateway</html>"), unreachable]) {
      const opened = await openWorld(read, "/world", false);
      expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
      const base = { loading: false, hasNode: false, unopened: opened.unopened, hasKey: false };
      expect(arrivalScreen({ ...base, introSeen: false, named: false })).toBe("retry");
      expect(arrivalScreen({ ...base, introSeen: true, named: false })).toBe("retry");
      // Asking again shows the loading shell, still before onboarding.
      expect(arrivalScreen({ ...base, loading: true, introSeen: false, named: false })).toBe("loading");
    }
  });

  it("answers a 403 that is not the server's own JSON with the retry line", async () => {
    // A proxy's HTML refusal or a cut-off body says nothing about the invitation.
    for (const hasKey of [false, true]) {
      for (const read of [answering(403, "<html>Forbidden</html>"), answering(403, '{"err')]) {
        const { opened, screen } = await settle(read, { hasKey, introSeen: true, named: true });
        expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
        expect(screen).toBe("retry");
      }
    }
  });

  it("answers a JSON 403 that is not the gate's own body with the retry line", async () => {
    // The gate always answers {"error": "forbidden"} (server/handlers.py,
    // _authorized). A WAF or proxy in front of it can answer 403 JSON
    // with any other body, which says nothing about the invitation.
    for (const body of [{ message: "Forbidden" }, {}, null, { error: "Access denied by WAF" }, []]) {
      for (const hasKey of [false, true]) {
        const { opened, screen } = await settle(answering(403, body),
          { hasKey, introSeen: true, named: true });
        expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
        expect(screen).toBe("retry");
      }
    }
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
    // The map's depth control: the server names the range it accepts.
    // guard.validate_world_params({"depth": 12}) (MIN_DEPTH 1, MAX_DEPTH 11).
    const depth = "depth must be between 1 and 11 (got 12)";
    const refused = await settle(answering(400, { error: depth }), { hasKey: true });
    expect(refused.opened.unopened).toEqual({ kind: "retry", line: depth });
  });

  it("does not show a proxy's own refusal to the player", async () => {
    // An edge or proxy in front of the server can answer with its own JSON.
    for (const [status, error] of [[404, "not found"], [401, "Unauthorized"], [418, "teapot"]]) {
      for (const hasKey of [false, true]) {
        const { opened } = await settle(answering(status, { error }), { hasKey });
        expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
      }
    }
  });

  it("does not open a 2xx answer without the seed and tree both clients draw from", async () => {
    // Every /world answer of the server carries a numeric seed and a tree.
    // Anything else would overwrite the drawn world before failing.
    for (const body of [{}, [], null, { seed: 382 }, { world: { name: "Root-1" } },
      { seed: "382", world: { name: "Root-1" } }, { seed: 382, world: null }]) {
      const { opened, screen } = await settle(answering(200, body),
        { hasKey: true, introSeen: true, named: true });
      expect(opened.unopened).toEqual({ kind: "retry", line: shared.WORLD_UNREACHED_LINE });
      expect(opened.data).toBeUndefined();
      expect(screen).toBe("retry");
    }
  });

  it("opens the world when the read succeeds", async () => {
    const world = { seed: 382, world: { name: "Root-1" } };
    const { opened } = await settle(answering(200, world), { hasKey: true });
    expect(opened).toEqual({ data: world });
  });
});

describe("arrival screens", () => {
  const ready = { introSeen: true, named: true, hasKey: true };
  const fresh = { introSeen: false, named: false };

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

  it("holds a keyless browser on the loading shell until the gate answers", () => {
    // The first render, before /world has answered: nothing to begin and no
    // name to choose, so nothing can be stored before the gate refuses.
    const inFlight = { ...fresh, hasKey: false, hasNode: false, unopened: null };
    expect(arrivalScreen({ ...inFlight, loading: true })).toBe("loading");
    // Between the position hydrate and the read, with nothing settled yet.
    expect(arrivalScreen({ ...inFlight, loading: false })).toBe("loading");
    // A browser that already saw the introduction waits the same way.
    expect(arrivalScreen({ ...inFlight, loading: true, introSeen: true })).toBe("loading");
    // The gate answers.
    const unopened = { kind: "invite", line: shared.WORLD_INVITE_LINE };
    expect(arrivalScreen({ ...inFlight, loading: false, unopened })).toBe("gate");
    // An open (ungated) world: onboarding follows the read.
    expect(arrivalScreen({ ...inFlight, loading: false, hasNode: true })).toBe("intro");
  });

  it("lets a browser with a key read the introduction while its world loads", () => {
    const inFlight = { ...fresh, hasKey: true, hasNode: false, unopened: null };
    expect(arrivalScreen({ ...inFlight, loading: true })).toBe("intro");
    expect(arrivalScreen({ ...inFlight, loading: true, introSeen: true })).toBe("name");
  });
});

describe("speech that is not answered", () => {
  // /speak and /agent/voice, through the same rule in both clients.
  const hear = (read, hasKey = true) => hearSpeech(read, "/speak", hasKey);
  const UNREACHED = { kind: "retry", line: shared.SPEAK_UNREACHED_LINE };

  it("keeps the server's reply for any 2xx", async () => {
    const quiet = "The place is quiet for now.";
    expect(await hear(answering(200, { response: quiet, ai: false }))).toEqual({ kind: "reply", line: quiet });
    // A hold or a decline is the world's own voice, answered 200.
    const held = { response: "Say it another way.", ai: false, held: true };
    expect(await hear(answering(200, held))).toEqual({ kind: "reply", line: held.response });
  });

  it("answers the gate's own 403 with the invitation lines, never its bare word", async () => {
    // A key revoked or sanctioned mid-session meets {"error": "forbidden"}.
    const refused = await hear(answering(403, { error: "forbidden" }), true);
    expect(refused).toEqual({ kind: "refused", line: shared.WORLD_REFUSED_LINE });
    const invite = await hear(answering(403, { error: "forbidden" }), false);
    expect(invite).toEqual({ kind: "invite", line: shared.WORLD_INVITE_LINE });
    for (const heard of [refused, invite]) expect(heard.line).not.toMatch(/forbidden/i);
  });

  it("answers a server error, a failed request or a foreign 403 with the authored line", async () => {
    for (const read of [
      answering(500, { error: "internal server error" }),
      answering(502, "<html>Bad Gateway</html>"),
      answering(503, { error: "unavailable" }),
      answering(403, { error: "Access denied by WAF" }),
      answering(403, "<html>Forbidden</html>"),
      answering(200, "<html>captive portal</html>"),
      answering(200, null),
      unreachable,
    ]) {
      for (const hasKey of [false, true]) {
        const heard = await hear(read, hasKey);
        expect(heard).toEqual(UNREACHED);
        expect(heard.line).not.toMatch(/internal server error|forbidden|WAF|Failed to fetch/i);
      }
    }
  });

  it("keeps the server's own line for the pace line and a client-shaped refusal", async () => {
    const pace = "the world asks for a quieter pace — a breath, then try again";
    expect(await hear(answering(429, { error: pace }))).toEqual({ kind: "server", line: pace });
    for (const [status, error] of [
      [400, "A message is required."],
      [404, "no such place in this world"],
      [413, "payload too large"],
    ]) {
      expect(await hear(answering(status, { error }))).toEqual({ kind: "server", line: error });
    }
    // A paced answer with no line of its own still says something authored.
    expect(await hear(answering(429, {}))).toEqual(UNREACHED);
  });
});

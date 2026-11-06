import { disclose } from "./disclosures.js";
// A chat line the moderation screen holds or declines reached nobody. Both
// real clients, served by the real server, give the player's own words back
// to the chat input — and never over text typed since the send. With AI
// disabled, a watch word escalates and is held (no classifier answers); a
// block-list word is declined locally.
import { expect, test } from "@playwright/test";
import { serveBrowser } from "./server.js";

const HOLD = "The worlds hold those words for now. They are not shared. "
  + "Say it another way, or try again later.";
const DECLINE = "The worlds decline to carry those words. Say it another way.";
const HELD_LINE = "the quietmoss grows by the gate";
const DECLINED_LINE = "the plumquake rises";

const serve = () => serveBrowser({ env: {
  NESTED_WORLDS_MODERATION_BLOCK_EXTRA: "plumquake",
  NESTED_WORLDS_MODERATION_WATCH_EXTRA: "quietmoss",
}});

// Relay the socket through the test. `holdDeclines` keeps each
// chat_declined until the test releases it, so the player can type first.
async function relay(page, { holdDeclines = false } = {}) {
  const state = { held: [], welcomed: null, toPage: null };
  let welcome;
  state.welcomed = new Promise(resolve => { welcome = resolve; });
  await page.routeWebSocket(/\/ws\?/, socket => {
    state.toPage = message => socket.send(JSON.stringify(message));
    const server = socket.connectToServer();
    server.onMessage(message => {
      const type = JSON.parse(message).type;
      if (holdDeclines && type === "chat_declined") {
        state.held.push(() => socket.send(message));
        return;
      }
      socket.send(message);
      if (type === "welcome") welcome();
    });
  });
  return state;
}

async function enter(page, url, route, socket) {
  await page.addInitScript(() => {
    if (location.protocol !== "http:") return;
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "Chatter");
    sessionStorage.setItem("nw_sound_invited", "1");
  });
  await page.goto(url + route);
  await socket.welcomed;
  await disclose(page, "History & journal");
  await disclose(page, "Travelers & chat");
  return page.getByRole("textbox", { name: "Message to travelers" });
}

const feed = (page, route) => page.locator(route === "/app" ? ".feed" : "#event-feed");

for (const route of ["/", "/app"]) {
  test(`${route} gives a held or declined chat line back to the empty input`, async ({ page }) => {
    const server = await serve();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    try {
      const socket = await relay(page);
      const input = await enter(page, server.url, route, socket);

      await input.fill(HELD_LINE);
      await input.press("Enter");
      await expect(feed(page, route)).toContainText(`✕ ${HOLD}`);
      await expect(input).toHaveValue(HELD_LINE);

      await input.fill(DECLINED_LINE);
      await input.press("Enter");
      await expect(feed(page, route)).toContainText(`✕ ${DECLINE}`);
      await expect(input).toHaveValue(DECLINED_LINE);

      // A line that is carried is not given back: the input stays clear.
      await input.fill("hello from the gate");
      await input.press("Enter");
      await expect(feed(page, route)).toContainText("hello from the gate");
      await expect(input).toHaveValue("");
      expect(errors).toEqual([]);
    } finally {
      await page.unrouteAll({ behavior: "wait" }).catch(() => {});
      await page.goto("about:blank").catch(() => {});
      await server.close();
    }
  });

  test(`${route} keeps what the player typed after a held line, and restores only the latest line`, async ({ page }) => {
    const server = await serve();
    try {
      const socket = await relay(page, { holdDeclines: true });
      const input = await enter(page, server.url, route, socket);
      const holds = feed(page, route).getByText(`✕ ${HOLD}`);

      await input.fill(HELD_LINE);
      await input.press("Enter");
      await expect.poll(() => socket.held.length).toBe(1);
      await expect(input).toHaveValue("");
      await input.pressSequentially("wait, the other gate");
      socket.held.shift()();
      await expect(holds).toHaveCount(1);
      await expect(input).toHaveValue("wait, the other gate");

      // Two lines in flight: the earlier one's hold restores nothing; the
      // later one's hold brings that later line back.
      await input.fill("first of two quietmoss lines");
      await input.press("Enter");
      await input.fill("second of two quietmoss lines");
      await input.press("Enter");
      await expect.poll(() => socket.held.length).toBe(2);
      socket.held.shift()();
      await expect(holds).toHaveCount(2);
      await expect(input).toHaveValue("");
      socket.held.shift()();
      await expect(holds).toHaveCount(3);
      await expect(input).toHaveValue("second of two quietmoss lines");
    } finally {
      await page.unrouteAll({ behavior: "wait" }).catch(() => {});
      await page.goto("about:blank").catch(() => {});
      await server.close();
    }
  });
}

// /app replaces its panel with the loading shell while a jump deepens the
// view toward a traveler below the fetched horizon. The socket stays open,
// so a verdict can arrive then; the line still comes back to the input.
test("/app gives a line back when its hold arrives during a deep traveler jump", async ({ page, request }) => {
  const server = await serve();
  let releaseWorld = () => {};
  try {
    const world = await (await request.get(server.url + "/world?depth=8")).json();
    let deep = world.world;
    while (deep.name.split("-").pop().length < 8) deep = deep.children[0];

    // Record each frame the page's socket delivers, so the test knows the
    // client handled the verdict before the world read is let through.
    await page.addInitScript(() => {
      const Native = window.WebSocket;
      window.__chatFrames = [];
      window.WebSocket = class extends Native {
        constructor(...args) {
          super(...args);
          this.addEventListener("message", event => {
            try { window.__chatFrames.push(JSON.parse(event.data).type); } catch { /* not JSON */ }
          });
        }
      };
    });
    const socket = await relay(page, { holdDeclines: true });
    const input = await enter(page, server.url, "/app", socket);

    await input.fill(HELD_LINE);
    await input.press("Enter");
    await expect.poll(() => socket.held.length).toBe(1);
    await expect(input).toHaveValue("");

    const gate = new Promise(resolve => { releaseWorld = resolve; });
    let asked;
    const worldAsked = new Promise(resolve => { asked = resolve; });
    await page.route(url => url.pathname === "/world", async route => {
      asked();
      await gate;
      await route.continue();
    });
    socket.toPage({ type: "player_move", name: "Farwalker", session_id: "far-1", node: deep.name });
    await page.getByRole("button", { name: /Farwalker/ }).click();
    await worldAsked;
    await expect(page.getByText("Opening the shared world…")).toBeVisible();

    socket.held.shift()();
    await page.waitForFunction(() => window.__chatFrames.includes("chat_declined"));
    releaseWorld();

    await expect(page.locator("#node-address")).toContainText(deep.name.split("-").pop());
    await disclose(page, "History & journal");
    await disclose(page, "Travelers & chat");
    await expect(feed(page, "/app")).toContainText(`✕ ${HOLD}`);
    await expect(page.getByRole("textbox", { name: "Message to travelers" })).toHaveValue(HELD_LINE);
  } finally {
    releaseWorld();
    await page.unrouteAll({ behavior: "wait" }).catch(() => {});
    await page.goto("about:blank").catch(() => {});
    await server.close();
  }
});

// A send in the moment the socket is closing (readyState 2, before onclose
// has marked the client disconnected) reaches nobody. Neither client may
// clear the line then. This drives the page's own socket, with no relay,
// because the relay replaces it and cannot show the closing state.
for (const route of ["/", "/app"]) {
  test(`${route} keeps a line sent while the socket is closing`, async ({ page }) => {
    const server = await serve();
    try {
      await page.addInitScript(() => {
        const Native = window.WebSocket;
        window.__sockets = [];
        window.WebSocket = class extends Native {
          constructor(...args) {
            super(...args);
            window.__sockets.push(this);
          }
        };
      });
      await page.addInitScript(() => {
        if (location.protocol !== "http:") return;
        localStorage.setItem("nw_seen_intro", "1");
        localStorage.setItem("nw_player_name", "Chatter");
        sessionStorage.setItem("nw_sound_invited", "1");
      });
      await page.goto(server.url + route);
      await page.waitForFunction(() => window.__sockets.some(socket => socket.readyState === 1));
      await disclose(page, "Travelers & chat");
      const input = page.getByRole("textbox", { name: "Message to travelers" });
      await input.fill("a line sent as the socket closes");

      // Close and press Enter in one task, so the client still believes it
      // is connected when it tries to send.
      const readyState = await page.evaluate(() => {
        const socket = window.__sockets.findLast(s => s.readyState === 1);
        socket.close();
        document.querySelector('input[aria-label="Message to travelers"]')
          .dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
        return socket.readyState;
      });
      expect(readyState).toBe(2);
      await expect(input).toHaveValue("a line sent as the socket closes");
    } finally {
      await page.goto("about:blank").catch(() => {});
      await server.close();
    }
  });
}

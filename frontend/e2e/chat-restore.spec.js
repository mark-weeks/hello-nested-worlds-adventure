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
  const state = { held: [], welcomed: null };
  let welcome;
  state.welcomed = new Promise(resolve => { welcome = resolve; });
  await page.routeWebSocket(/\/ws\?/, socket => {
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

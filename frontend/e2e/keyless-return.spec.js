// A returning player whose browser holds no invite key (a bookmark, a private
// window, another device, cleared site data) meets the latched invite gate.
// Both real clients, served by the real server, must say how to return
// instead of loading forever or printing the gate's bare refusal, and a
// failed /speak must answer with the authored line, never a raw error.
import { expect, test } from "@playwright/test";
import { serveBrowser } from "./server.js";

const KEY = "nw_" + "e".repeat(32);
const UNKNOWN_KEY = "nw_" + "f".repeat(32);
const NAME = "Returning traveler";
const INVITE = "The world opens only to an invitation, and this browser holds "
  + "none. To return, open the invite link you were sent, here on this device.";
const REFUSED = "The invitation this browser holds does not open the world. If "
  + "you were sent another invite link, open it here on this device.";
const UNREACHED = "The world could not be reached. Try opening the view again.";
const SPEAK_UNREACHED = "Your words did not reach this place. Try speaking again.";
const LOADING = "Opening the shared world…";
const inviteLink = route => `${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`;

// Minting a key latches the gate: every data read now needs a live key.
const serve = () => serveBrowser({ preseed: 382, invite: KEY, player: NAME });

function watchErrors(page) {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  return errors;
}

// A returning browser that kept its onboarding but not its key.
async function returning(page, key = null) {
  await page.addInitScript(({ key, name }) => {
    if (location.protocol !== "http:") return;
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", name);
    localStorage.setItem("nw_sound_preference", "off");
    if (key && !new URLSearchParams(location.search).has("key")) {
      localStorage.setItem("nw_beta_key", key);
    }
  }, { key, name: NAME });
}

test("/app on a new device says how to return, then opens from the invite link", async ({ page }) => {
  const server = await serve();
  const errors = watchErrors(page);
  try {
    // Nothing stored at all: no key, no name, no introduction seen.
    const refusal = page.waitForResponse(reply =>
      new URL(reply.url()).pathname === "/world" && reply.status() === 403);
    await page.goto(server.url + "/app");
    await refusal;
    await expect(page.getByRole("alert")).toHaveText(INVITE);
    await expect(page.getByText(LOADING)).toHaveCount(0);
    // The gate comes before onboarding: no name to choose, nothing to begin.
    await expect(page.getByPlaceholder("Your name", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Begin", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Open the view again" })).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText(/forbidden/i);

    // Doing what the line says opens the world on this device.
    await page.goto(server.url + inviteLink("/app"));
    await page.getByRole("button", { name: "Begin", exact: true }).click();
    await expect(page.locator("#node-name")).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem("nw_beta_key"))).toBe(KEY);
    expect(errors).toEqual([]);
  } finally {
    await server.close();
  }
});

test("/app keeps a refused invitation neutral", async ({ page }) => {
  const server = await serve();
  const errors = watchErrors(page);
  try {
    await returning(page, UNKNOWN_KEY);
    await page.goto(server.url + "/app");
    await expect(page.getByRole("alert")).toHaveText(REFUSED);
    await expect(page.getByText(LOADING)).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText(/forbidden/i);
    expect(errors).toEqual([]);
  } finally {
    await server.close();
  }
});

test("/app answers an unreachable world with a retry, and a failed speech with the authored line", async ({ page }) => {
  const server = await serve();
  const errors = watchErrors(page);
  try {
    await returning(page, KEY);
    const worldRead = url => url.pathname === "/world";
    await page.route(worldRead, route => route.abort("failed"));
    await page.goto(server.url + "/app");
    await expect(page.getByRole("alert")).toHaveText(UNREACHED);
    await expect(page.getByText(LOADING)).toHaveCount(0);

    await page.unroute(worldRead);
    await page.getByRole("button", { name: "Open the view again" }).click();
    await expect(page.locator("#node-name")).toBeVisible();

    await page.route(url => ["/speak", "/agent/voice"].includes(url.pathname),
      route => route.abort("failed"));
    await page.getByRole("textbox", { name: "Message to this place" }).fill("Who keeps this place?");
    await page.getByRole("button", { name: /^Speak to / }).click();
    await expect(page.getByText(SPEAK_UNREACHED, { exact: true })).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await page.unrouteAll({ behavior: "wait" }).catch(() => {});
    await server.close();
  }
});

test("the map says how to return without a key, opens from the invite link, and keeps a failed speech in fiction", async ({ page }) => {
  const server = await serve();
  const errors = watchErrors(page);
  try {
    await returning(page);
    await page.goto(server.url + "/");
    await expect(page.locator("#status")).toHaveText(INVITE);
    await expect(page.locator("#node-description")).toHaveText(INVITE);
    await expect(page.locator("body")).not.toContainText(/forbidden/i);

    await page.goto(server.url + inviteLink("/"));
    await expect(page.locator("#status")).toContainText("shared world");
    await expect(page.locator("#node-name")).not.toHaveText("Select a node");
    expect(await page.evaluate(() => localStorage.getItem("nw_beta_key"))).toBe(KEY);

    await page.route(url => ["/speak", "/agent/voice"].includes(url.pathname),
      route => route.abort("failed"));
    await page.locator("#btn-do-speak").click();
    await expect(page.locator("#speak-response")).toHaveText(SPEAK_UNREACHED);
    await expect(page.locator("#status")).toHaveText(SPEAK_UNREACHED);
    await expect(page.locator("#speak-response")).not.toContainText(/network error/i);
    expect(errors).toEqual([]);
  } finally {
    await page.unrouteAll({ behavior: "wait" }).catch(() => {});
    await server.close();
  }
});

test("the map keeps a refused invitation neutral", async ({ page }) => {
  const server = await serve();
  try {
    await returning(page, UNKNOWN_KEY);
    await page.goto(server.url + "/");
    await expect(page.locator("#status")).toHaveText(REFUSED);
    await expect(page.locator("body")).not.toContainText(/forbidden/i);
  } finally {
    await server.close();
  }
});

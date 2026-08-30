// Batch 4 in both shipped clients, against the real Python server: a selected
// node opens at its present event step, scrubs exactly back to birth, and
// redraws through the deterministic art surface without browser errors.
import { expect, test } from "@playwright/test";

function collectErrors(page) {
  const errors = [];
  page.on("pageerror", error => errors.push(`pageerror: ${error.message}`));
  page.on("console", message => {
    if (message.type() === "error") errors.push(`console.error: ${message.text()}`);
  });
  return errors;
}

async function setRangeToBirth(locator) {
  await locator.fill("0");
}

test("explorer scrubs a node from present to birth", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WaybackExplorer");
  });
  const errors = collectErrors(page);
  let waybackRequests = 0;
  page.on("request", request => {
    if (new URL(request.url()).pathname === "/wayback") waybackRequests += 1;
  });
  await page.goto("/");
  await expect(page.locator("#node-name")).not.toHaveText("Select a node");
  await expect(page.locator("#players-list")).not.toContainText("Not connected");

  await page.click("#btn-wayback");
  await expect(page.locator("#wayback-modal")).toBeVisible();
  await expect(page.locator("#wayback-x")).toBeFocused();
  await expect(page.locator("#wayback-meta")).toContainText("first witnessed");
  await expect(page.locator("#wayback-lens"))
    .toHaveText("the node as it was, seen with today's eyes");

  const range = page.locator("#wayback-range");
  await expect.poll(async () => Number(await range.getAttribute("max")))
    .toBeGreaterThan(0);
  await setRangeToBirth(range);
  await expect(page.locator("#wayback-moment"))
    .toHaveText("the node rests in its born state");
  await expect(page.locator("#wayback-meta")).toContainText("birth");

  const beforeScrubBurst = waybackRequests;
  await range.evaluate(element => {
    const max = Number(element.max);
    for (let i = 0; i < 12; i += 1) {
      element.value = String(i % 2 ? max : 0);
      element.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  await expect.poll(() => waybackRequests).toBe(beforeScrubBurst + 1);

  await page.route(/\/wayback\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ error: "archive unavailable" }),
  }));
  await page.click("#wayback-play");
  await expect(page.locator("#wayback-moment"))
    .toHaveText("The archive is unreadable right now.");
  await expect(page.locator("#wayback-play")).toHaveText("play evolution");
  await page.locator("#wayback-x").focus();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#wayback-close")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#wayback-x")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#wayback-modal")).toBeHidden();
  await expect(page.locator("#btn-wayback")).toBeFocused();
  expect(errors).toEqual([]);
});

test("/app scrubs a node from present to birth", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WaybackViewer");
  });
  const errors = collectErrors(page);
  let waybackRequests = 0;
  page.on("request", request => {
    if (new URL(request.url()).pathname === "/wayback") waybackRequests += 1;
  });
  await page.goto("/app");
  await expect(page.getByText("● connected")).toBeVisible({ timeout: 10_000 });

  const trigger = page.getByRole("button", { name: "wayback" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: /Wayback/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close wayback" })).toBeFocused();
  await expect(dialog).toContainText("first witnessed");
  await expect(dialog).toContainText("the node as it was, seen with today's eyes");

  const range = dialog.getByRole("slider", { name: "Wayback time" });
  await expect.poll(async () => Number(await range.getAttribute("max")))
    .toBeGreaterThan(0);
  await setRangeToBirth(range);
  await expect(dialog).toContainText("the node rests in its born state");
  await expect(dialog).toContainText("birth");

  const beforeScrubBurst = waybackRequests;
  await range.evaluate(element => {
    const max = Number(element.max);
    const setValue = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype, "value",
    ).set;
    for (let i = 0; i < 12; i += 1) {
      // Call the native prototype setter so React's controlled-input value
      // tracker observes each synthetic drag position.
      setValue.call(element, String(i % 2 ? max : 0));
      element.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  await expect(range).toBeEnabled();
  await expect.poll(() => waybackRequests).toBe(beforeScrubBurst + 1);

  const listen = dialog.getByRole("button", { name: "listen to this moment" });
  await listen.click();
  await expect(dialog.getByRole("button", { name: "return to present sound" }))
    .toBeEnabled();
  await page.route(/\/wayback\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ error: "archive unavailable" }),
  }));
  await range.fill("0");
  await expect(dialog).toContainText("The archive is unreadable right now.");
  await expect(dialog.getByRole("button", { name: "listen to this moment" }))
    .toBeDisabled();

  await dialog.getByRole("button", { name: "Close wayback" }).focus();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  expect(errors).toEqual([]);
});

test("explorer clears an old snapshot before a failed reopen", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WaybackFailureViewer");
  });
  const errors = collectErrors(page);
  await page.goto("/");
  await expect(page.locator("#node-name")).not.toHaveText("Select a node");

  await page.click("#btn-wayback");
  await expect(page.locator("#wayback-meta")).toContainText("first witnessed");
  await page.click("#wayback-close");

  await page.route(/\/wayback\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ error: "archive unavailable" }),
  }));
  await page.click("#btn-wayback");
  await expect(page.locator("#wayback-moment"))
    .toHaveText("The archive is unreadable right now.");
  await expect(page.locator("#wayback-range")).toBeDisabled();
  await expect(page.locator("#wayback-properties")).toBeEmpty();
  await expect(page.locator("#wayback-listen")).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.locator("#btn-wayback")).toBeFocused();
  expect(errors).toEqual([]);
});

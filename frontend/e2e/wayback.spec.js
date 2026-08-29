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
  await page.goto("/");
  await expect(page.locator("#node-name")).not.toHaveText("Select a node");
  await expect(page.locator("#players-list")).not.toContainText("Not connected");

  await page.click("#btn-wayback");
  await expect(page.locator("#wayback-modal")).toBeVisible();
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
  await page.click("#wayback-close");
  await expect(page.locator("#wayback-modal")).toBeHidden();
  expect(errors).toEqual([]);
});

test("/app scrubs a node from present to birth", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WaybackViewer");
  });
  const errors = collectErrors(page);
  await page.goto("/app");
  await expect(page.getByText("● connected")).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: "wayback" }).click();
  const dialog = page.getByRole("dialog", { name: /Wayback for/ });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("first witnessed");
  await expect(dialog).toContainText("the node as it was, seen with today's eyes");

  const range = dialog.getByRole("slider", { name: "Wayback time" });
  await expect.poll(async () => Number(await range.getAttribute("max")))
    .toBeGreaterThan(0);
  await setRangeToBirth(range);
  await expect(dialog).toContainText("the node rests in its born state");
  await expect(dialog).toContainText("birth");
  await dialog.getByRole("button", { name: "Close wayback" }).click();
  await expect(dialog).toBeHidden();
  expect(errors).toEqual([]);
});

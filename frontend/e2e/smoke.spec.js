// Both clients must actually render in a real browser, served by the real
// Python server under the production CSP. Any pageerror or console.error is
// a failure — the PixiJS-vs-CSP blank scene shipped precisely because
// nothing automated ever loaded the deployed bundle.
import { expect, test } from "@playwright/test";

function collectErrors(page) {
  const errors = [];
  page.on("pageerror", err => errors.push(`pageerror: ${err.message}`));
  page.on("console", msg => {
    if (msg.type() === "error") errors.push(`console.error: ${msg.text()}`);
  });
  return errors;
}

test("explorer (/) renders the world and the node sigil", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/");

  // Real first-run onboarding: intro → name → world.
  await page.click("#btn-begin");
  await page.fill("#player-name-input", "SmokeTester");
  await page.click("#btn-join");

  // The D3 world graph mounts and a node gets auto-selected.
  await expect(page.locator("#graph svg")).toBeVisible();
  await expect(page.locator("#node-name")).not.toHaveText("Select a node");

  // The generative-art sigil actually painted: opaque pixels on the canvas.
  await expect
    .poll(async () => page.evaluate(() => {
      const c = document.getElementById("node-sigil");
      if (!c) return -1;
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      let opaque = 0;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 200) opaque++;
      return opaque;
    }), { timeout: 10_000 })
    .toBeGreaterThan(1000);

  // The scale-native verb affordance is wired.
  await page.click("#btn-act");
  await expect(page.locator("#btn-do-act")).toContainText(
    /attune|calibrate|kindle|align|seed|ward|inscribe|mend|catalyze|excite|observe/i);

  // The chronicle opens and reports the world's record.
  await page.click("#btn-chronicle");
  await expect(page.locator("#chronicle-meta")).toContainText("recorded events");

  expect(errors).toEqual([]);
});

test("/app mounts the Pixi scene under the production CSP", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/app");

  // Real first-run onboarding: intro → name → world.
  await page.getByRole("button", { name: "Begin" }).click();
  await page.getByPlaceholder("Your name").fill("SmokeTester");
  await page.getByRole("button", { name: "Enter" }).click();

  // PixiJS must initialize despite script-src 'self' (pixi.js/unsafe-eval).
  const canvas = page.locator("canvas").first();
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  const size = await canvas.boundingBox();
  expect(size.width).toBeGreaterThan(100);
  expect(size.height).toBeGreaterThan(100);

  // The side panel carries a real node at some scale — non-linear entry
  // can drop the player anywhere in the eleven levels.
  await expect(page.locator(
    "text=/Multiverse|Universe|Galaxy|Planetary System|Planet|Region|Room|Object|Molecule|Atom|SubatomicParticle/",
  ).first()).toBeVisible({ timeout: 10_000 });

  expect(errors).toEqual([]);
});

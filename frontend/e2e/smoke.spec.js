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

  // The engine room stays tucked away: world-generation controls are hidden
  // until the ⚙ affordance opens them, and close again.
  await expect(page.locator("#seed")).toBeHidden();
  await page.click("#btn-advanced");
  await expect(page.locator("#seed")).toBeVisible();
  await expect(page.locator("#gen-btn")).toBeVisible();
  await page.click("#btn-advanced");
  await expect(page.locator("#seed")).toBeHidden();

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
  await page.click("#chronicle-close");

  // The sound invitation appears once per session, in fiction, a moment
  // after the world settles — and accepting it IS the WebAudio activation
  // gesture: the full graph (pad, sub, texture, music box, delay space)
  // builds in a real browser without throwing.
  await expect(page.locator("#sound-invite")).toBeVisible({ timeout: 10_000 });
  await expect(page.locator("#sound-invite .invite-line"))
    .toContainText("The world hums");
  await page.click("#sound-invite-yes");
  await expect(page.locator("#sound-invite")).toBeHidden();
  await expect(page.locator("#btn-sound")).toHaveText("♪ on");
  await page.waitForTimeout(600);   // let the scheduler tick
  await page.click("#btn-sound");
  await expect(page.locator("#btn-sound")).toHaveText("♪ off");

  expect(errors).toEqual([]);
});

test("/register runs its logic under the production CSP", async ({ page }) => {
  // The page's behavior IS its script: without JS, #no-invite stays hidden
  // and the form does nothing. This page shipped with an inline <script>
  // once — blocked wholesale by script-src 'self' — and the self-service
  // invite flow silently failed (2026-07-19 ensemble evaluation). Both
  // assertions below only pass if the external script actually executed.
  const errors = collectErrors(page);

  // No invite token → the script must swap the panels.
  await page.goto("/register");
  await expect(page.locator("#no-invite")).toBeVisible();
  await expect(page.locator("#register")).toBeHidden();

  // A (bogus) invite token → form visible; submitting must reach the
  // server and render its player-facing refusal — proving the submit
  // handler attached and the fetch wiring works end-to-end.
  await page.goto("/register?invite=nwr_not_a_real_token");
  await expect(page.locator("#register")).toBeVisible();
  await page.fill("#name", "SmokeRegistrant");
  await page.click("#go");
  await expect(page.locator("#error")).not.toHaveText("", { timeout: 10_000 });

  // The bogus token's 403 is the expected outcome above — Chromium logs
  // every non-2xx fetch as a console "Failed to load resource" error, so
  // that one line is allow-listed; anything else (a CSP violation, a
  // pageerror) still fails the run.
  expect(errors.filter(e => !/Failed to load resource/.test(e))).toEqual([]);
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

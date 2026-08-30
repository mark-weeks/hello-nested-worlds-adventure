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
  let historyLoads = 0;
  let socketOpens = 0;
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.pathname === "/history" && !url.searchParams.has("node_name")) {
      historyLoads += 1;
    }
  });
  page.on("websocket", () => { socketOpens += 1; });
  await page.goto("/");

  // Real first-run onboarding: intro → name → world.
  await page.click("#btn-begin");
  await page.fill("#player-name-input", "SmokeTester");
  await page.click("#btn-join");

  // The D3 world graph mounts and a node gets auto-selected.
  await expect(page.locator("#graph svg")).toBeVisible();
  await expect(page.locator("#node-name")).not.toHaveText("Select a node");

  // The world itself is server-owned. The advanced affordance can change only
  // view depth; neither seed nor breadth/world-generation controls exist.
  await expect(page.locator("#seed")).toHaveCount(0);
  await expect(page.locator("#min_b")).toHaveCount(0);
  await page.click("#btn-advanced");
  await expect(page.locator("#depth")).toBeVisible();
  await expect(page.locator("#gen-btn")).toBeVisible();
  await page.click("#btn-advanced");
  await expect(page.locator("#depth")).toBeHidden();

  // Depth six is only the initial payload window. Select a rendered horizon
  // node and cross it in fiction; the same node stays selected while its Room
  // children arrive in the next canonical prefix.
  const beforeDeepen = await page.locator("#graph .node").count();
  await page.evaluate(() => {
    const horizon = [...document.querySelectorAll("#graph .node")]
      .findLast((el) => el.__data__?.data?.level === "Region");
    horizon.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await expect(page.locator("#btn-deepen")).toBeVisible();
  const horizonName = await page.locator("#node-name").textContent();
  await expect.poll(() => historyLoads).toBe(1);
  await expect.poll(() => socketOpens).toBe(1);
  await page.click("#btn-deepen");
  await expect(page.locator("#status")).toContainText("depth 7");
  await expect(page.locator("#node-name")).toHaveText(horizonName);
  await expect(page.locator("#btn-deepen")).toBeHidden();
  await expect.poll(() => page.locator("#graph .node").count())
    .toBeGreaterThan(beforeDeepen);
  // A prefix-only view change must not replay history or flap shared presence.
  expect(historyLoads).toBe(1);
  expect(socketOpens).toBe(1);

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

test("/app puzzle tab loads immediately and preserves a solved result", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "PuzzleTester");
  });
  await page.route("**/puzzle?*", async route => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        found: true,
        name: "The Remembered Door",
        kind: "RIDDLE",
        prompt: "What remains after the answer?",
        max_attempts: 3,
        difficulty: 2,
        solved: true,
        attempt: 1,
        solver: "Ada",
        contributors: ["Ada"],
      }),
    });
  });

  await page.goto("/app");
  await page.getByRole("button", { name: "Puzzle" }).click();
  await expect(page.getByText("The Remembered Door")).toBeVisible();
  await expect(page.getByText("Already resolved — solved by Ada.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Find puzzle here" })).toHaveCount(0);
  await expect(page.getByPlaceholder("Your answer…")).toBeDisabled();
});

test("/app refreshes canonical properties after an immediate node action", async ({ page, request }) => {
  const response = await request.get("/world?depth=6");
  const data = await response.json();
  let region = data.world;
  while (region.children?.length) region = region.children[0];
  expect(region.level).toBe("Region");

  await page.addInitScript((nodeName) => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "ActionTester");
    localStorage.setItem("nw_last_node", nodeName);
  }, region.name);
  let worldLoads = 0;
  page.on("request", req => {
    if (new URL(req.url()).pathname === "/world") worldLoads += 1;
  });

  await page.goto("/app");
  await page.getByRole("button", { name: "Ward" }).click();
  await page.getByRole("button", { name: "Ward this Region" }).click();

  await expect(page.getByText("warded", { exact: true })).toBeVisible();
  await expect.poll(() => worldLoads).toBeGreaterThanOrEqual(2);
});

test("/app defaults sound on and remembers an explicit mute", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "SoundTester");
    if (!sessionStorage.getItem("sound-test-started")) {
      localStorage.removeItem("nw_sound_preference");
      sessionStorage.setItem("sound-test-started", "1");
    }
  });
  await page.goto("/app");

  const sound = page.locator("#btn-sound");
  await expect(sound).toHaveText("♪ on");
  await sound.click();
  await expect(sound).toHaveText("♪ off");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("nw_sound_preference")))
    .toBe("off");

  await page.reload();
  await expect(sound).toHaveText("♪ off");
  await sound.click();
  await expect(sound).toHaveText("♪ on");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("nw_sound_preference")))
    .toBe("on");
});

test("/app opens a depth horizon automatically without losing the current node", async ({ page, request }) => {
  const response = await request.get("/world?depth=6");
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  let horizon = data.world;
  while (horizon.children?.length) horizon = horizon.children[horizon.children.length - 1];
  expect(horizon.level).toBe("Region");

  await page.addInitScript((nodeName) => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "DepthTester");
    localStorage.setItem("nw_last_node", nodeName);
  }, horizon.name);

  const errors = collectErrors(page);
  await page.goto("/app");
  const horizonPhrase = horizon.name.replace(/-\d+$/, "");
  await expect(page.getByText(horizonPhrase, { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Passages \(/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Look within ↓" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "View full chronicle" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Player's Guide ↗" })).toBeVisible();

  // The list is an accessible fallback for the canvas hotspots, not passive
  // duplicate copy: either surface can move into the same child.
  await page.getByRole("button", { name: /\(Room\)/ }).first().click();
  await expect(page.getByText("Room", { exact: true }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

async function mockSavedPosition(page, position) {
  await page.route("**/position?*", async route => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ position }),
      });
    } else {
      await route.continue();
    }
  });
}

async function deepSavedPosition(request, depth = 8) {
  const response = await request.get(`/world?depth=${depth}`);
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  let node = data.world;
  while (node.children?.length) node = node.children[node.children.length - 1];
  return { node: node.name, seed: data.seed, depth };
}

test("/app restores a server-saved node below the initial horizon", async ({ page, request }) => {
  const position = await deepSavedPosition(request);
  await mockSavedPosition(page, position);
  await page.addInitScript(() => {
    localStorage.setItem("nw_beta_key", "cross-device-app");
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "DeepAppTraveler");
  });

  const errors = collectErrors(page);
  await page.goto("/app");
  await expect(page.getByText(position.node.replace(/-\d+$/, ""), { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Object", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("explorer restores server-saved depth across devices", async ({ page, request }) => {
  const position = await deepSavedPosition(request);
  await mockSavedPosition(page, position);
  await page.addInitScript(() => {
    localStorage.setItem("nw_beta_key", "cross-device-explorer");
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "DeepExplorerTraveler");
  });

  const errors = collectErrors(page);
  await page.goto("/");
  await expect(page.locator("#status")).toContainText("depth 8");
  await expect(page.locator("#node-name")).toHaveText(position.node.replace(/-\d+$/, ""));
  await expect(page.locator("#node-name")).toHaveAttribute("title", position.node);
  expect(errors).toEqual([]);
});

// The wrap passage (ADR-008) in both real clients, against the real
// Python server: standing on a particle offers the descent onto the
// whole; standing on the root offers the ascent to the one hinge — and
// the first crossing in each direction speaks its authored line.
import { expect, test } from "@playwright/test";

function collectErrors(page) {
  const errors = [];
  page.on("pageerror", err => errors.push(`pageerror: ${err.message}`));
  page.on("console", msg => {
    if (msg.type() === "error") errors.push(`console.error: ${msg.text()}`);
  });
  return errors;
}

async function wrapInfo(request) {
  const response = await request.get("/world?depth=4");
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.wrap?.hinge).toBeTruthy();
  expect(data.wrap?.root).toBeTruthy();
  return data.wrap;
}

test("/app crosses the wrap in both directions", async ({ page, request }) => {
  const wrap = await wrapInfo(request);

  // Resume standing on the hinge particle itself (suffix length pins the
  // view depth to 11, so the particle scale is rendered).
  await page.addInitScript((nodeName) => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WrapWalker");
    localStorage.setItem("nw_last_node", nodeName);
  }, wrap.hinge);

  // The display layer shows the phrase; the address gets its own field.
  const hingePhrase = wrap.hinge.replace(/-\d+$/, "");
  const hingeAddress = wrap.hinge.split("-").pop();
  const rootPhrase = wrap.root.replace(/-\d+$/, "");

  const errors = collectErrors(page);
  await page.goto("/app");
  await expect(page.getByText(hingePhrase, { exact: true }).first()).toBeVisible();
  await expect(page.getByText(`⌖ ${hingeAddress}`, { exact: true })).toBeVisible();

  // Descend below the particle: surface at the Multiverse root, with the
  // authored line spoken (first crossing in this browser).
  const descend = page.getByRole("button", { name: "Descend into the whole ↓" });
  await expect(descend).toBeVisible();
  await descend.click();
  await expect(page.getByText(rootPhrase, { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Multiverse", { exact: true })).toBeVisible();
  await expect(page.getByText(/the particle does not end/)).toBeVisible();

  // Ascend beyond the root: land back at the hinge — the same monument.
  const ascend = page.getByRole("button", { name: "Ascend beyond ↑" });
  await expect(ascend).toBeVisible();
  await ascend.click();
  await expect(page.getByText(hingePhrase, { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/beyond the last membrane/)).toBeVisible();

  expect(errors).toEqual([]);
});

test("explorer crosses the wrap in both directions", async ({ page, request }) => {
  const wrap = await wrapInfo(request);

  await page.addInitScript((nodeName) => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", "WrapExplorer");
    localStorage.setItem("nw_last_node", nodeName);
  }, wrap.hinge);

  const hingePhrase = wrap.hinge.replace(/-\d+$/, "");
  const rootPhrase = wrap.root.replace(/-\d+$/, "");

  const errors = collectErrors(page);
  await page.goto("/");
  await expect(page.locator("#status")).toContainText("depth 11");
  // Display name in the sidebar; the canonical name survives as hover
  // title and the address as its own property row.
  await expect(page.locator("#node-name")).toHaveText(hingePhrase);
  await expect(page.locator("#node-name")).toHaveAttribute("title", wrap.hinge);
  await expect(page.locator("#node-props")).toContainText("address");

  // The particle offers the descent — and only the descent.
  await expect(page.locator("#btn-wrap-down")).toBeVisible();
  await expect(page.locator("#btn-wrap-up")).toBeHidden();
  await page.click("#btn-wrap-down");
  await expect(page.locator("#node-name")).toHaveText(rootPhrase);
  await expect(page.locator("#event-feed")).toContainText("the particle does not end");

  // The root offers the ascent — and only the ascent.
  await expect(page.locator("#btn-wrap-up")).toBeVisible();
  await expect(page.locator("#btn-wrap-down")).toBeHidden();
  await page.click("#btn-wrap-up");
  await expect(page.locator("#node-name")).toHaveText(hingePhrase);
  await expect(page.locator("#event-feed")).toContainText("beyond the last membrane");

  expect(errors).toEqual([]);
});

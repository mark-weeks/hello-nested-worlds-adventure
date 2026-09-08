// Real browser actions, durable pending work, server process death/restart,
// missed notification and authoritative reload in both shipped clients.
import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

test.use({ viewport: { width: 1440, height: 1100 } });

const python = process.env.ENFOLDED_PYTHON || "python";
const repo = path.resolve(import.meta.dirname, "../..");

async function startServer(db, pump, port = 0, maturationScale = "0.02") {
  const source = `
import sys
from pathlib import Path
import persistence
persistence._DB_PATH = Path(sys.argv[1])
from server import _Handler, _ThreadedServer, heartbeat
server = _ThreadedServer(('127.0.0.1', int(sys.argv[2])), _Handler)
if sys.argv[3] == '1':
    heartbeat.start_pump()
print(server.server_address[1], flush=True)
server.serve_forever()
`;
  const child = spawn(python, ["-u", "-c", source, db, String(port), pump ? "1" : "0"], {
    cwd: repo,
    env: { ...process.env, NESTED_WORLDS_CANONICAL_SEED: "382",
      NESTED_WORLDS_DISABLE_AI: "1", NESTED_WORLDS_DISABLE_IMAGES: "1",
      NESTED_WORLDS_HOP_DELAY: "0", NESTED_WORLDS_MATURATION_SCALE: maturationScale },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.on("data", chunk => { stderr += chunk; });
  let boundPort;
  try {
    boundPort = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`server startup timeout: ${stderr}`)), 15_000);
    child.once("error", error => { clearTimeout(timer); reject(error); });
    child.once("exit", code => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${stderr}`)); });
    child.stdout.once("data", chunk => { clearTimeout(timer); resolve(Number(String(chunk).trim())); });
    });
  } catch (error) {
    await kill({ child });
    throw error;
  }
  return { child, port: boundPort, url: `http://127.0.0.1:${boundPort}` };
}

async function kill(server) {
  if (!server || server.child.exitCode !== null || server.child.signalCode !== null) return;
  const exited = once(server.child, "exit");
  server.child.kill("SIGKILL");
  await exited;
}

for (const [route, maturationScale] of [["/", "0.02"], ["/app", "0.02"], ["/", "0.001"], ["/app", "0.001"], ["/", "0"]]) {
  test(`${route} preserves act timing (scale ${maturationScale}) across server death and reload`, async ({ page, request }) => {
    const directory = await mkdtemp(path.join(tmpdir(), "enfolded-delivery-"));
    const db = path.join(directory, "worlds.db");
    let server;
    try {
      server = await startServer(db, false, 0, maturationScale);
      const data = await (await request.get(`${server.url}/world?depth=3`)).json();
      const galaxy = data.world.children[0].children[0];
      const bornDensity = galaxy.properties.star_density;
      await page.addInitScript(name => {
        localStorage.setItem("nw_seen_intro", "1");
        localStorage.setItem("nw_player_name", "RecoveryBrowser");
        localStorage.setItem("nw_last_node", name);
      }, galaxy.name);
      await page.goto(`${server.url}${route}`);
      if (route === "/") {
        await expect(page.locator("#players-list")).not.toContainText("Not connected");
        await page.locator("#sound-invite-no").click();
        await page.locator("#btn-act").click();
      }
      else await page.getByRole("button", { name: "Kindle", exact: true }).click();
      const [response] = await Promise.all([
        page.waitForResponse(r => new URL(r.url()).pathname === "/act"),
        page.getByRole("button", { name: "Kindle this Galaxy", exact: true }).click(),
      ]);
      const accepted = await response.json();
      const immediate = maturationScale === "0";
      const expectedDensity = immediate ? accepted.changed.star_density
        : Math.min(999, bornDensity + Math.max(1, Math.floor(bornDensity / 20)));
      if (!immediate) expect(accepted.changed).toBeNull();
      if (immediate) expect(accepted.matures_in).toBeNull();
      else if (maturationScale === "0.001") expect(accepted.matures_in).toBe(0);
      else expect(accepted.matures_in).toBeGreaterThan(0);
      if (immediate) {
        await expect(page.locator("#node-props")).toContainText(String(expectedDensity));
      } else if (route === "/") {
        await expect(page.locator("#act-response")).toContainText("still traveling");
        await expect(page.locator("#node-props")).toContainText(String(bornDensity));
      }
      const pending = await (await request.get(`${server.url}/world?depth=3`)).json();
      expect(pending.world.children[0].children[0].properties.star_density)
        .toBe(immediate ? accepted.changed.star_density : bornDensity);
      const port = server.port;
      await page.goto("about:blank"); // Deliberately miss the maturation broadcast.
      await kill(server);
      server = await startServer(db, true, port, maturationScale);
      await expect.poll(async () => {
        const current = await (await request.get(`${server.url}/world?depth=3`)).json();
        return current.world.children[0].children[0].properties.star_density;
      }, { timeout: 15_000 }).toBe(expectedDensity);
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(`${server.url}${route}`);
      const phrase = galaxy.name.replace(/-\d+$/, "");
      if (route === "/") {
        await expect(page.locator("#node-name")).toContainText(phrase);
        await expect(page.locator("#node-props")).toContainText(String(expectedDensity));
      } else {
        await expect(page.getByText(phrase, { exact: true }).first()).toBeVisible();
        await expect(page.getByText(String(expectedDensity), { exact: true }).first()).toBeVisible();
      }
      expect(errors).toEqual([]);
    } finally {
      await page.goto("about:blank").catch(() => {});
      await kill(server);
      await rm(directory, { recursive: true, force: true });
    }
  });
}

async function changeProperties(db, name, properties) {
  const child = spawn(python, ["-c", `
import json, sys
from pathlib import Path
import persistence
persistence._DB_PATH = Path(sys.argv[1])
persistence.record_substance_change(382, sys.argv[2], 'TEST_CHANGE', None, {}, json.loads(sys.argv[3]))
`, db, name, JSON.stringify(properties)], { cwd: repo });
  const [code] = await once(child, "exit");
  expect(code).toBe(0);
}

async function openKindle(page, url, route) {
  await page.goto(url + route);
  if (route === "/") {
    await page.locator("#btn-act").click();
  } else await page.getByRole("button", { name: "Kindle", exact: true }).click();
}

async function clickKindle(page) {
  const [response] = await Promise.all([
    page.waitForResponse(r => new URL(r.url()).pathname === "/act"),
    page.getByRole("button", { name: "Kindle this Galaxy", exact: true }).click(),
  ]);
  return response.json();
}

for (const route of ["/", "/app"]) {
  for (const mode of ["contributions", "shared-noop"]) {
    test(`${route} explains ${mode}, pending reload and missed terminal notification`, async ({ page, request }) => {
      const directory = await mkdtemp(path.join(tmpdir(), "enfolded-m2-browser-"));
      const db = path.join(directory, "worlds.db");
      let server;
      try {
        server = await startServer(db, false);
        const data = await (await request.get(`${server.url}/world?depth=3`)).json();
        const galaxy = data.world.children[0].children[0];
        const bornDensity = galaxy.properties.star_density;
        if (mode === "shared-noop") {
          await changeProperties(db, galaxy.name, { star_density: 999, kindled: false });
        }
        await page.addInitScript(name => {
          localStorage.setItem("nw_seen_intro", "1");
          localStorage.setItem("nw_player_name", "M2Browser");
          localStorage.setItem("nw_last_node", name);
          sessionStorage.setItem("nw_sound_invited", "1");
        }, galaxy.name);
        await openKindle(page, server.url, route);
        const first = await clickKindle(page);
        expect(first.action_status).toBe("accepted");
        expect(first.changed).toBeNull();
        await expect(page.getByText("1 kindle change is still traveling.", { exact: false }).first()).toBeVisible();
        const second = await clickKindle(page);
        expect(second.action_status).toBe(mode === "contributions" ? "accepted" : "shared");
        if (mode === "shared-noop") {
          expect(second.work.id).toBe(first.work.id);
          await expect(page.getByText(/You join its wait; no additional change is planted/).first()).toBeVisible();
        } else expect(second.work.id).not.toBe(first.work.id);
        // Pending state also survives a page load, without relying on acceptance messages.
        await openKindle(page, server.url, route);
        const count = mode === "contributions" ? 2 : 1;
        const pendingText = `${count} kindle ${count === 1 ? "change is" : "changes are"} still traveling.`;
        await expect(page.getByText(pendingText, { exact: false }).first()).toBeVisible();
        await page.goto("about:blank");
        const port = server.port;
        await kill(server);
        // The shared flag became satisfied during the wait: no second success is invented.
        if (mode === "shared-noop") await changeProperties(db, galaxy.name, { kindled: true });
        server = await startServer(db, true, port);
        await expect.poll(async () => {
          const current = await (await request.get(`${server.url}/world?depth=3`)).json();
          return current.world.children[0].children[0].pending_actions.length;
        }, { timeout: 15_000 }).toBe(0);
        const current = await (await request.get(`${server.url}/world?depth=3`)).json();
        const density = current.world.children[0].children[0].properties.star_density;
        const once = bornDensity + Math.max(1, Math.floor(bornDensity / 20));
        expect(density).toBe(mode === "shared-noop" ? 999 : once + Math.max(1, Math.floor(once / 20)));
        await openKindle(page, server.url, route);
        await expect(page.getByText(pendingText, { exact: false })).toHaveCount(0);
        if (route === "/") {
          await expect(page.locator("#node-props")).toContainText(String(density));
          await page.locator("#btn-chronicle").click();
          await expect(page.locator("#chronicle-entries")).toContainText(
            mode === "shared-noop" ? "Nothing more changes" : "the change arrives");
        } else {
          await expect(page.getByText(String(density), { exact: true }).first()).toBeVisible();
          await page.getByRole("button", { name: "View full chronicle" }).click();
          await expect(page.getByText(mode === "shared-noop" ? /Nothing more changes/ : /the change arrives/).first()).toBeVisible();
        }
      } finally {
        await page.goto("about:blank").catch(() => {});
        await kill(server);
        await rm(directory, { recursive: true, force: true });
      }
    });
  }
}

test("explorer keeps a delayed response attached to the place where it was requested", async ({ page, request }) => {
  const directory = await mkdtemp(path.join(tmpdir(), "enfolded-m2-navigation-"));
  const db = path.join(directory, "worlds.db");
  let server;
  let release;
  try {
    server = await startServer(db, false);
    const data = await (await request.get(`${server.url}/world?depth=3`)).json();
    const galaxy = data.world.children[0].children[0];
    await page.addInitScript(name => {
      localStorage.setItem("nw_seen_intro", "1");
      localStorage.setItem("nw_player_name", "M2Navigator");
      localStorage.setItem("nw_last_node", name);
      sessionStorage.setItem("nw_sound_invited", "1");
    }, galaxy.name);
    await openKindle(page, server.url, "/");
    const held = new Promise(resolve => { release = resolve; });
    let committed;
    const accepted = new Promise(resolve => { committed = resolve; });
    await page.route(/\/act$/, async route => {
      const response = await route.fetch();
      committed();
      await held;
      await route.fulfill({ response });
    });
    await page.getByRole("button", { name: "Kindle this Galaxy", exact: true }).click();
    await accepted;
    await page.evaluate(() => {
      const root = [...document.querySelectorAll("#graph .node")]
        .find(el => el.__data__?.data?.level === "Multiverse");
      root.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    const responseArrived = page.waitForResponse(r => new URL(r.url()).pathname === "/act");
    release();
    await responseArrived;
    await expect(page.locator("#node-name")).toContainText(data.world.name.replace(/-\d+$/, ""));
    await expect(page.locator("#act-response")).toHaveText("");
    await expect(page.locator("#act-tagline")).not.toContainText("kindle");
  } finally {
    release?.();
    await page.goto("about:blank").catch(() => {});
    await kill(server);
    await rm(directory, { recursive: true, force: true });
  }
});

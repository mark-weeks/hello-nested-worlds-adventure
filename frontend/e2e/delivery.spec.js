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

for (const [route, maturationScale] of [["/", "0.02"], ["/app", "0.02"], ["/", "0.001"], ["/", "0"]]) {
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
      if (immediate) expect(accepted.matures_in).toBeNull();
      else if (maturationScale === "0.001") expect(accepted.matures_in).toBe(0);
      else expect(accepted.matures_in).toBeGreaterThan(0);
      if (immediate) {
        await expect(page.locator("#node-props")).toContainText(String(accepted.changed.star_density));
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
      }, { timeout: 15_000 }).toBe(accepted.changed.star_density);
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(`${server.url}${route}`);
      const phrase = galaxy.name.replace(/-\d+$/, "");
      if (route === "/") {
        await expect(page.locator("#node-name")).toContainText(phrase);
        await expect(page.locator("#node-props")).toContainText(String(accepted.changed.star_density));
      } else {
        await expect(page.getByText(phrase, { exact: true }).first()).toBeVisible();
        await expect(page.getByText(String(accepted.changed.star_density), { exact: true }).first()).toBeVisible();
      }
      expect(errors).toEqual([]);
    } finally {
      await page.goto("about:blank").catch(() => {});
      await kill(server);
      await rm(directory, { recursive: true, force: true });
    }
  });
}

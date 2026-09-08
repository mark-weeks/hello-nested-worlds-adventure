// M3 through real browsers, HTTP, WebSockets, the committed bundle and reload.
import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const repo = path.resolve(import.meta.dirname, "../..");
const python = process.env.ENFOLDED_PYTHON || "python";
test.use({ viewport: { width: 1440, height: 1100 } });

async function serve(db) {
  const child = spawn(python, ["-u", "-c", `
import sys
from pathlib import Path
import persistence
persistence._DB_PATH = Path(sys.argv[1])
from server import _Handler, _ThreadedServer, heartbeat
server = _ThreadedServer(('127.0.0.1', 0), _Handler)
heartbeat.start_pump()
print(server.server_address[1], flush=True)
server.serve_forever()
`, db], { cwd: repo, env: { ...process.env,
    NESTED_WORLDS_CANONICAL_SEED: "382", NESTED_WORLDS_HOP_DELAY: "0",
    NESTED_WORLDS_MATURATION_SCALE: "0.03", NESTED_WORLDS_DISABLE_AI: "1",
    NESTED_WORLDS_DISABLE_IMAGES: "1" }, stdio: ["ignore", "pipe", "pipe"] });
  let errors = "";
  child.stderr.on("data", data => { errors += data; });
  const port = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", code => reject(new Error(`server ${code}: ${errors}`)));
    child.stdout.once("data", data => resolve(Number(String(data).trim())));
  });
  return { child, url: `http://127.0.0.1:${port}` };
}

for (const route of ["/", "/app"]) {
  for (const mode of ["immediate", "delayed"]) {
    test(`${route} traces ${mode} actions through live arrival, chronicle and missed-notice reload`, async ({ page, request }) => {
      const directory = await mkdtemp(path.join(tmpdir(), "enfolded-m3-browser-"));
      let server;
      try {
        server = await serve(path.join(directory, "world.db"));
        const world = await (await request.get(server.url + "/world?depth=6")).json();
        const galaxy = world.world.children[0].children[0];
        const origin = mode === "delayed" ? galaxy : galaxy.children[0].children[0];
        const receiver = mode === "delayed" ? world.world.children[0] : galaxy.children[0];
        const verb = mode === "delayed" ? "Kindle" : "Seed";
        await page.addInitScript(node => {
          if (location.protocol !== "http:") return;
          localStorage.setItem("nw_seen_intro", "1");
          localStorage.setItem("nw_player_name", "M3Visitor");
          localStorage.setItem("nw_last_node", node);
          sessionStorage.setItem("nw_sound_invited", "1");
        }, origin.name);
        const notices = [];
        page.on("websocket", socket => socket.on("framereceived", ({ payload }) => {
          try { notices.push(JSON.parse(payload)); } catch { /* other transport frames */ }
        }));
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(server.url + route);
        await page.waitForLoadState("networkidle");
        if (route === "/") await page.locator("#btn-act").click();
        else await page.getByRole("button", { name: verb, exact: true }).click();
        const reads = { world: 0, node: 0, history: 0 };
        page.on("request", req => {
          const endpoint = new URL(req.url()).pathname.slice(1);
          if (endpoint in reads) reads[endpoint]++;
        });
        const [response] = await Promise.all([
          page.waitForResponse(r => new URL(r.url()).pathname === "/act"),
          page.getByRole("button", { name: `${verb} this ${origin.level}`, exact: true }).click(),
        ]);
        const accepted = await response.json();
        expect(accepted.action_status).toBe("accepted");
        const originPage = await (await request.get(`${server.url}/chronicle?before=${accepted.event_id + 1}&limit=1`)).json();
        const action = originPage.entries[0];
        expect(action.narration.phase).toBe(mode === "delayed" ? "accepted" : "action");
        await expect(page.getByText(action.narration.text, { exact: false }).first()).toBeVisible();
        await expect.poll(() => notices.find(m => m.node === receiver.name && m.narration?.phase === "arrival"),
          { timeout: 15_000 }).toBeTruthy();
        const arrival = notices.find(m => m.node === receiver.name && m.narration?.phase === "arrival");
        expect(arrival.narration.source_event_id).toBe(accepted.event_id);
        expect(arrival.narration.actor_label).toBe("M3Visitor");
        expect(arrival.narration.origin).toBe(origin.name);
        expect(arrival.narration.text).not.toContain("chose");
        await expect(page.getByText(arrival.narration.text, { exact: false }).first()).toBeVisible();
        const local = await (await request.get(`${server.url}/history?node_name=${encodeURIComponent(receiver.name)}`)).json();
        expect(local.mutations.find(e => e.id === arrival.event_id).narration).toEqual(arrival.narration);
        expect(reads.world).toBe(0);
        expect(reads.history).toBe(0); // notices already carry bounded provenance

        // Leave before a later action and outcome: no socket hint reaches this
        // browser. The existing history/chronicle reads must recover the facts.
        await page.goto("about:blank");
        const other = await (await request.post(server.url + "/act", {
          data: { node_name: galaxy.name, player_name: "OtherVisitor" },
        })).json();
        expect(other.action_status).toBe("accepted");
        let outcome;
        await expect.poll(async () => {
          const history = await (await request.get(`${server.url}/history?node_name=${encodeURIComponent(galaxy.name)}`)).json();
          outcome = history.mutations.find(e => e.type === "SCALE_ACT_MATURED"
            && e.narration.source_event_id === other.event_id);
          return !!outcome;
        }, { timeout: 15_000 }).toBe(true);
        await page.goto(server.url + route);
        await expect(page.getByText(outcome.narration.text, { exact: false }).first()).toBeVisible();
        if (route === "/") await page.locator("#btn-chronicle").click();
        else await page.getByRole("button", { name: "View full chronicle" }).click();
        await expect(page.getByText(outcome.narration.text, { exact: false }).last()).toBeVisible();
        // The earlier ripple must be in the chronicle as the same arrival,
        // even if the bounded recent feed no longer includes it.
        await expect(page.getByText(arrival.narration.text, { exact: false }).last()).toBeVisible();
        await page.screenshot({ path: path.join(tmpdir(), `enfolded-m3-${route === "/" ? "explorer" : "scene"}-${mode}.png`) });
        expect(errors).toEqual([]);
      } finally {
        await page.goto("about:blank").catch(() => {});
        if (server && server.child.exitCode === null) {
          const exited = once(server.child, "exit");
          server.child.kill("SIGKILL");
          await exited;
        }
        await rm(directory, { recursive: true, force: true });
      }
    });
  }
}

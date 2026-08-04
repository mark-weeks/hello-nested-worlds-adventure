#!/usr/bin/env node
/** Reproduce the four beta-brief captures from the canonical launch world. */
import { createRequire } from "node:module";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoDir = resolve(scriptDir, "..");
const frontendRequire = createRequire(join(repoDir, "frontend", "package.json"));
const { chromium } = frontendRequire("@playwright/test");

const assetsDir = join(repoDir, "docs", "pitch", "assets");
const scratch = mkdtempSync(join(tmpdir(), "enfolded-pitch-"));
const framesDir = join(scratch, "cascade-frames");
const manifestPath = join(scratch, "manifest.json");
const heartbeatPath = join(scratch, "heartbeat.json");
const databasePath = join(scratch, "capture.db");
mkdirSync(framesDir, { recursive: true });
mkdirSync(assetsDir, { recursive: true });

const port = 8299;
const baseURL = `http://127.0.0.1:${port}`;
const python = process.env.ENFOLDED_PYTHON || join(repoDir, ".venv", "bin", "python");
const server = spawn(python, [
  join(scriptDir, "pitch_capture_server.py"),
  "--database", databasePath,
  "--manifest", manifestPath,
  "--heartbeat-summary", heartbeatPath,
  "--port", String(port),
], {
  cwd: repoDir,
  env: {
    ...process.env,
    NESTED_WORLDS_CANONICAL_SEED: "382",
    NESTED_WORLDS_HEARTBEAT: "0",
    NESTED_WORLDS_HOP_DELAY: "0.8",
    NESTED_WORLDS_CAUSAL_PUMP: "1",
    NESTED_WORLDS_DISABLE_AI: "1",
    NESTED_WORLDS_DISABLE_IMAGES: "1",
  },
  stdio: ["ignore", "inherit", "inherit"],
});

async function waitForServer() {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseURL}/health`);
      if (response.ok) return;
    } catch (_) { /* server is still birthing */ }
    await new Promise(resolvePromise => setTimeout(resolvePromise, 200));
  }
  throw new Error("pitch capture server did not become healthy");
}

async function waitForFile(path, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(path)) return;
    await new Promise(resolvePromise => setTimeout(resolvePromise, 200));
  }
  throw new Error(`timed out waiting for ${path}`);
}

function primeContext(context, playerName) {
  return context.addInitScript(name => {
    localStorage.setItem("nw_seen_intro", "1");
    localStorage.setItem("nw_player_name", name);
    localStorage.removeItem("nw_last_node");
    localStorage.setItem("nw_view_depth", "6");
    sessionStorage.setItem("nw_sound_invited", "1");
  }, playerName);
}

async function openExplorer(browser, viewport, playerName) {
  const context = await browser.newContext({ viewport });
  await primeContext(context, playerName);
  const page = await context.newPage();
  await page.goto(`${baseURL}/?name=${encodeURIComponent(playerName)}`,
                  { waitUntil: "networkidle" });
  await page.waitForFunction(() => {
    const text = document.querySelector("#node-name")?.textContent || "";
    return text && text !== "Select a node";
  });
  await page.waitForFunction(() => window.NodeArt?.drawNodeArt);
  return { context, page };
}

function encodeCascade() {
  const output = join(assetsDir, "cascade.gif");
  const result = spawnSync("ffmpeg", [
    "-hide_banner", "-loglevel", "error", "-y",
    "-framerate", "2", "-i", join(framesDir, "frame-%03d.png"),
    "-filter_complex",
    "fps=2,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer",
    output,
  ], { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`ffmpeg exited ${result.status}`);
}

let browser;
try {
  await waitForServer();
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  browser = await chromium.launch({ headless: true });

  // 1. A real name-derived middle-world arrival in the canonical world.
  const drop = await openExplorer(browser, { width: 1280, height: 800 }, "Archivist");
  await drop.page.waitForTimeout(700);
  const dropin = {
    player: "Archivist",
    node: await drop.page.locator("#node-name").textContent(),
    level: await drop.page.locator("#node-level").textContent(),
  };
  await drop.page.screenshot({ path: join(assetsDir, "dropin.png") });
  await drop.context.close();

  // 2. The first-child chain, painted directly by the shipped NodeArt module.
  const grid = await openExplorer(browser, { width: 1280, height: 792 }, "Cartographer");
  const artNodes = await grid.page.evaluate(async () => {
    const response = await fetch("/world?depth=11");
    const payload = await response.json();
    const chain = [];
    let node = payload.world;
    while (node) {
      chain.push(node);
      node = node.children?.[0] || null;
    }
    document.body.innerHTML = '<main id="capture-grid"><header><h1>ELEVEN ENFOLDED SCALES</h1><p>canonical world · seed 382 · one living chain</p></header><section id="cards"></section></main>';
    const style = document.createElement("style");
    style.textContent = `
      * { box-sizing: border-box; } html, body { margin:0; width:1280px; height:792px; overflow:hidden; }
      body { background:#07080f; color:#b0bcd0; font-family:'Courier New',monospace; }
      #capture-grid { width:1280px; height:792px; padding:16px; background:radial-gradient(circle at 50% 0%,#101832,#07080f 55%); }
      header { height:56px; display:flex; align-items:baseline; gap:18px; border-bottom:1px solid #1a2038; }
      h1 { margin:0; color:#5a9cff; letter-spacing:3px; font-size:16px; }
      header p { margin:0; color:#40557a; font-size:11px; letter-spacing:1px; }
      #cards { display:grid; grid-template-columns:repeat(4, 1fr); grid-template-rows:repeat(3, 1fr); gap:10px; height:704px; padding-top:10px; }
      article { min-width:0; border:1px solid #1a2038; background:#0b0d1acc; padding:8px; display:flex; flex-direction:column; }
      canvas { width:100%; flex:1; min-height:0; background:#07080f; border:1px solid #141b30; }
      .level { margin-top:6px; color:#668bd0; font-size:9px; text-transform:uppercase; letter-spacing:2px; }
      .name { color:#a8bad5; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    `;
    document.head.appendChild(style);
    const cards = document.querySelector("#cards");
    for (const item of chain) {
      const card = document.createElement("article");
      const canvas = document.createElement("canvas");
      canvas.width = 286; canvas.height = 155;
      const level = document.createElement("div");
      level.className = "level"; level.textContent = item.level;
      const name = document.createElement("div");
      name.className = "name"; name.textContent = item.name;
      card.append(canvas, level, name); cards.appendChild(card);
      window.NodeArt.drawNodeArt(canvas, payload.seed, item);
    }
    return chain.map(item => ({ level: item.level, name: item.name }));
  });
  await grid.page.locator("#capture-grid").screenshot({ path: join(assetsDir, "artgrid.png") });
  await grid.context.close();

  // 3. Solve a real world-reading puzzle and sample the staged ring arrivals.
  const cascade = await openExplorer(browser, { width: 900, height: 562 }, "Signalkeeper");
  const target = cascade.page.locator(".node").filter({ hasText: manifest.cascade_node }).first();
  // D3 lays the complete depth-six tree out before zooming it to fit, so the
  // SVG element's untransformed box may sit outside Playwright's viewport even
  // though the transformed mark is visible. Dispatching its real click event
  // drives the same D3 handler without fabricating application state.
  await target.dispatchEvent("click");
  await cascade.page.waitForFunction(
    expected => document.querySelector("#node-name")?.textContent === expected,
    manifest.cascade_node,
  );
  // The deliberately short GIF viewport clips the lower control panel. The
  // controls are still live in the page; dispatching their normal click events
  // avoids Playwright trying to scroll the fixed-height application shell.
  await cascade.page.locator("#btn-puzzle").dispatchEvent("click");
  await cascade.page.locator("#btn-do-puzzle").dispatchEvent("click");
  await cascade.page.locator("#puzzle-answer").waitFor();
  await cascade.page.locator("#puzzle-answer").evaluate((input, answer) => {
    input.value = answer;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, manifest.cascade_answer);
  await cascade.page.screenshot({ path: join(framesDir, "frame-000.png") });
  await cascade.page.locator("#puzzle-submit").dispatchEvent("click");
  for (let frame = 1; frame <= 24; frame += 1) {
    await cascade.page.waitForTimeout(500);
    await cascade.page.screenshot({
      path: join(framesDir, `frame-${String(frame).padStart(3, "0")}.png`),
    });
  }
  const cascadeFeed = await cascade.page.locator("#event-feed").innerText();
  await cascade.context.close();
  encodeCascade();

  // 4. Capture the same-process deterministic heartbeat while Tessera is live.
  const heartbeat = await openExplorer(browser, { width: 1280, height: 800 }, "Stillwater");
  await heartbeat.page.waitForFunction(() =>
    [...document.querySelectorAll(".player-row .player-name")]
      .some(element => element.textContent?.includes("Tessera")),
    { timeout: 30_000 },
  );
  await heartbeat.page.waitForTimeout(1000);
  const heartbeatPresence = await heartbeat.page.locator("#players-list").innerText();
  const heartbeatFeed = await heartbeat.page.locator("#event-feed").innerText();
  await heartbeat.page.locator(".sidebar").screenshot({ path: join(assetsDir, "heartbeat.png") });
  await heartbeat.context.close();

  await waitForFile(heartbeatPath);
  const heartbeatSummary = JSON.parse(readFileSync(heartbeatPath, "utf8"));
  const metadata = {
    captured_at: new Date().toISOString(),
    source: "scripts/capture_pitch_assets.mjs",
    seed: manifest.seed,
    generator_version: manifest.generator_version,
    dropin,
    cascade: {
      node: manifest.cascade_node,
      level: manifest.cascade_level,
      puzzle: manifest.cascade_puzzle,
      puzzle_kind: manifest.cascade_puzzle_kind,
      observed_feed: cascadeFeed.split("\n").filter(Boolean),
    },
    artgrid: artNodes,
    heartbeat: {
      ...heartbeatSummary,
      observed_presence: heartbeatPresence.split("\n").filter(Boolean),
      observed_feed: heartbeatFeed.split("\n").filter(Boolean),
    },
  };
  writeFileSync(join(assetsDir, "capture-metadata.json"),
                `${JSON.stringify(metadata, null, 2)}\n`);
  console.log(`Captured launch-world pitch assets in ${assetsDir}`);
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
  await new Promise(resolvePromise => {
    server.once("exit", resolvePromise);
    setTimeout(resolvePromise, 3000);
  });
  rmSync(scratch, { recursive: true, force: true });
}

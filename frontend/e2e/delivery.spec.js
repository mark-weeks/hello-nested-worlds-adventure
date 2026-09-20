// Real browser actions, durable pending work, server process death/restart,
// missed notification and authoritative reload in both shipped clients.
import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import { once } from "node:events";
import {createInterface} from "node:readline";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

test.use({ viewport: { width: 1440, height: 1100 },extraHTTPHeaders:{"X-Beta-Key":"nw_"+"a".repeat(32)} });

const python = process.env.ENFOLDED_PYTHON || "python";
const repo = path.resolve(import.meta.dirname, "../..");

async function startServer(db, pump, port = 0, maturationScale = "0.02") {
  const source = `
import sys
from pathlib import Path
import persistence
persistence._DB_PATH = Path(sys.argv[1])
if not persistence.lookup_invite_key('nw_'+'a'*32):
    persistence.mint_invite_key('nw_'+'a'*32,'Ada')
    persistence.mint_invite_key('nw_'+'b'*32,'Bea')
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
    const lines=createInterface({input:child.stdout});
    lines.once("line",line=>{clearTimeout(timer);lines.close();resolve(Number(line.trim()));});
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
        localStorage.setItem("nw_beta_key", "nw_"+"a".repeat(32));
        localStorage.setItem("nw_last_node", name);
      }, galaxy.name);
      await page.goto(`${server.url}${route}`);
      if (route === "/") {
        await expect(page.locator("#players-list")).not.toContainText("Not connected");
        await page.locator("#sound-invite-no").click();
        await page.locator("#btn-act").click();
      }
      else await page.getByRole("button", { name: "Act", exact: true }).click();
      // Retained actors/CLI may still create original /act work. Its old timing
      // and historic deltas must survive a renderer/UI upgrade.
      const response = await request.post(server.url+'/act',{data:{node_name:galaxy.name,player_name:'RecoveryBrowser'}});
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
        await expect(page.locator("enfolded-interventions")).toContainText("still traveling");
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
        await page.getByText("Conditions here",{exact:true}).click();
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

const credentials={Ada:'nw_'+'a'.repeat(32),Bea:'nw_'+'b'.repeat(32)};
async function enter(page,url,route,node,name='Ada') {
  await page.addInitScript(({node,name,key})=>{
    localStorage.setItem('nw_seen_intro','1');localStorage.setItem('nw_player_name',name);
    localStorage.setItem('nw_last_node',node);localStorage.setItem('nw_beta_key',key);
    sessionStorage.setItem('nw_sound_invited','1');
  },{node,name,key:credentials[name]});
  await page.goto(url+route);
  if(route==='/')await page.locator('#btn-act').click();
  else await page.getByRole('button',{name:'Act',exact:true}).click();
  return page.locator('enfolded-interventions');
}
async function kindle(page,act) {
  await act.getByRole('button',{name:'Kindle',exact:true}).click();
  const [reply]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/interventions/commit'),
    act.getByRole('button',{name:'Act: Kindle',exact:true}).click(),
  ]);
  return reply.json();
}

for(const route of ['/','/app']) {
  test(`${route} keeps new delayed contributions through restart and changed conditions`,async({page,request})=>{
    const directory=await mkdtemp(path.join(tmpdir(),'enfolded-v2-delivery-')),db=path.join(directory,'worlds.db');let server;
    try {
      server=await startServer(db,false);
      const world=await(await request.get(server.url+'/world?depth=3')).json(),galaxy=world.world.children[0].children[0];
      const before=galaxy.properties.star_density;
      const act=await enter(page,server.url,route,galaxy.name);
      const first=await kindle(page,act);
      const second=await kindle(page,act);
      expect(first.accepted).toBe(true);expect(first.changed).toEqual({});expect(second.id).not.toBe(first.id);
      await act.getByText('Actions still echoing',{exact:true}).click();
      await expect(act).toContainText('arrivals still travelling');
      await page.reload();if(route==='/')await page.locator('#btn-act').click();else await page.getByRole('button',{name:'Act',exact:true}).click();
      await act.getByText('Actions still echoing',{exact:true}).click();await expect(act).toContainText('arrivals still travelling');
      await page.goto('about:blank');const port=server.port;await kill(server);
      // Another action lands during the wait. Each contribution acts on that
      // current state, never overwriting it with its earlier absolute preview.
      await changeProperties(db,galaxy.name,{star_density:before+100});
      server=await startServer(db,true,port);
      const once=before+100+Math.max(1,Math.floor((before+100)/20));
      const expected=once+Math.max(1,Math.floor(once/20));
      await expect.poll(async()=>{
        const node=await(await request.get(server.url+'/node?node_name='+encodeURIComponent(galaxy.name))).json();
        return node.node.properties.star_density;
      },{timeout:15000}).toBe(expected);
      await page.goto(server.url+route);
      if(route==='/')await expect(page.locator('#node-props')).toContainText(String(expected));
      else {await page.getByText('Conditions here',{exact:true}).click();await expect(page.getByText(String(expected),{exact:true}).first()).toBeVisible();}
    }finally {await page.goto('about:blank').catch(()=>{});await kill(server);await rm(directory,{recursive:true,force:true});}
  });
}

for(const route of ['/','/app']) for(const endpoint of ['/interventions/commit','/node']) {
  test(`${route} keeps a late ${endpoint} reply attached to its original place`,async({page,request})=>{
    const directory=await mkdtemp(path.join(tmpdir(),'enfolded-v2-navigation-')),db=path.join(directory,'worlds.db');let server,release;
    try {
      server=await startServer(db,false);
      const world=await(await request.get(server.url+'/world?depth=3')).json(),galaxy=world.world.children[0].children[0];
      const act=await enter(page,server.url,route,galaxy.name);
      const held=new Promise(resolve=>{release=resolve;});let reached;
      const requested=new Promise(resolve=>{reached=resolve;});
      await page.routeWebSocket(/\/ws\?/,socket=>{const peer=socket.connectToServer();peer.onMessage(message=>{if(JSON.parse(message).type!=='intervention_changed')socket.send(message);});});
      await act.getByRole('button',{name:'Kindle',exact:true}).click();
      await page.route(url=>url.pathname===endpoint,async route=>{const response=await route.fetch();reached();await held;await route.fulfill({response});});
      await act.getByRole('button',{name:'Act: Kindle',exact:true}).click();await requested;
      if(route==='/app')await page.getByRole('button',{name:'↑ Enclosing world',exact:true}).click();
      else await page.evaluate(()=>{
        const root=[...document.querySelectorAll('#graph .node')].find(el=>el.__data__?.data?.level==='Multiverse');
        root.dispatchEvent(new MouseEvent('click',{bubbles:true}));
      });
      const arrived=page.waitForResponse(r=>new URL(r.url()).pathname===endpoint);release();await arrived;
      await expect(act.getByRole('button',{name:route==='/app'?'Calibrate':'Attune',exact:true})).toBeVisible();
      await expect(act.getByRole('button',{name:'Kindle',exact:true})).toHaveCount(0);
      await expect(act.getByRole('status')).not.toContainText('Kindle');
      // An unknown acknowledgement remains stored for the source place; it
      // cannot materialize as the new place's plan or be resubmitted there.
      await expect(act.getByRole('button',{name:'Act: Kindle',exact:true})).toHaveCount(0);
    }finally {release?.();await page.unrouteAll({behavior:'wait'}).catch(()=>{});await page.goto('about:blank').catch(()=>{});await kill(server);await rm(directory,{recursive:true,force:true});}
  });
}

for(const route of ['/','/app']) {
  test(`${route} co-viewers keep their own action replies while the shared state updates`,async({browser,request})=>{
    test.setTimeout(45000);
    const directory=await mkdtemp(path.join(tmpdir(),'enfolded-v2-viewers-')),db=path.join(directory,'worlds.db');let server;const contexts=[];
    try {
      server=await startServer(db,true,0,'0.05');
      const world=await(await request.get(server.url+'/world?depth=3')).json(),galaxy=world.world.children[0].children[0];
      await changeProperties(db,galaxy.name,{star_density:418,kindled:false});
      const pages=[],acts=[];
      for(const name of ['Ada','Bea']) {const ctx=await browser.newContext();contexts.push(ctx);const page=await ctx.newPage();pages.push(page);acts.push(await enter(page,server.url,route,galaxy.name,name));}
      const [ada,bea]=pages,[a,b]=acts;
      const reads=pages.map(()=>({world:0,node:0}));pages.forEach((page,i)=>page.on('request',req=>{const ep=new URL(req.url()).pathname.slice(1);if(ep in reads[i])reads[i][ep]++;}));
      const own=await kindle(ada,a);await expect(a.getByRole('status')).toHaveText(own.flavor);
      await expect(b.getByRole('status')).toHaveText('');
      // The other player's pending work is visible on demand, not a forced route.
      await b.getByText('Actions still echoing',{exact:true}).click();await expect(b).toContainText('Ada · Kindle');
      const other=await kindle(bea,b);expect(other.id).not.toBe(own.id);
      await expect(a.getByRole('status')).toHaveText(own.flavor);await expect(b.getByRole('status')).toHaveText(other.flavor);
      await expect.poll(async()=> (await(await request.get(server.url+'/node?node_name='+encodeURIComponent(galaxy.name))).json()).node.properties.star_density,{timeout:25000}).toBe(459);
      for(const page of pages) {
        if(route==='/')await expect(page.locator('#node-props')).toContainText('459');
        else {await page.getByText('Conditions here',{exact:true}).click();await expect(page.getByText('459',{exact:true}).first()).toBeVisible();}
      }
      await expect(a.getByRole('status')).toHaveText(own.flavor);await expect(b.getByRole('status')).toHaveText(other.flavor);
      expect(reads.every(r=>r.world===0 && r.node>=2 && r.node<9),JSON.stringify(reads)).toBe(true);
    }finally {for(const ctx of contexts)await ctx.close();await kill(server);await rm(directory,{recursive:true,force:true});}
  });
}

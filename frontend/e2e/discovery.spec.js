import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import {createInterface} from 'node:readline';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '../..');
const python = process.env.ENFOLDED_PYTHON || 'python';
const key = 'nw_' + 'a'.repeat(32);
const otherKey = 'nw_' + 'b'.repeat(32);
const names = {
  region: 'Emberlit Orchard Terraces-111111',
  instrument: 'Elder River Instrument-11111111',
  regulator: 'Amber Ember Mechanism-11111112',
  fold: 'Elder Lantern Fold-111111112',
  chain: 'Distant River Chain-111111111',
};
const capture = name => path.join(tmpdir(), name);

async function start() {
  const dir = await mkdtemp(path.join(tmpdir(), 'enfolded-discovery-'));
  const child = spawn(python, ['-u', '-c', `
import sys
from pathlib import Path
import persistence
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
from multiverse import situation
situation.WINDOW_SECONDS=4
situation.STEP_SECONDS=1
from persistence.situations import install
install(382)
persistence.mint_invite_key('nw_'+'a'*32,'Ada')
persistence.mint_invite_key('nw_'+'b'*32,'Bea')
from server import _Handler,_ThreadedServer,heartbeat
server=_ThreadedServer(('127.0.0.1',0),_Handler)
heartbeat._PUMP_INTERVAL=0.2  # Accelerate only this disposable browser fixture.
heartbeat.start_pump()
print(server.server_address[1],flush=True)
server.serve_forever()
`, dir], {cwd: repo, env: {...process.env, NESTED_WORLDS_CANONICAL_SEED: '382', NESTED_WORLDS_DISABLE_AI: '1', NESTED_WORLDS_DISABLE_IMAGES: '1'}, stdio: ['ignore','pipe','pipe']});
  let stderr = '';
  child.stderr.on('data', chunk => { stderr += chunk; });
  const port = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(stderr || 'Server did not start')), 15000);
    const lines=createInterface({input:child.stdout});
    lines.once('line',line=>{clearTimeout(timer);lines.close();resolve(Number(line.trim()));});
    child.once('exit', () => { clearTimeout(timer); reject(new Error(stderr)); });
  }).catch(async error => { child.kill('SIGKILL'); throw error; });
  return {url: `http://127.0.0.1:${port}`, async close() {
    const end = once(child, 'exit'); child.kill('SIGKILL'); await end;
    await rm(dir, {recursive: true, force: true});
  }};
}
async function enter(page, server, route = '/app', node = names.region) {
  await page.addInitScript(({key, node}) => {
    localStorage.setItem('nw_beta_key', key);
    localStorage.setItem('nw_player_name', 'Ada');
    localStorage.setItem('nw_seen_intro', '1');
    if (node) localStorage.setItem('nw_last_node', node);
  }, {key, node});
  await page.goto(server.url + route);
}
test('exploration has no quest controller; journals and profiles preserve private notes', async ({page,browser}) => {
  const server=await start();
  try {
    await enter(page,server,'/app',names.instrument);
    await expect(page.getByRole('region',{name:'Investigation'})).toHaveCount(0);
    await expect(page.getByText('Who will enact this?',{exact:true})).toHaveCount(0);
    await page.goto(server.url+'/journal?node='+names.instrument);
    await page.getByLabel('Question or observation').fill('Private: a different purpose for the instrument');
    await page.getByRole('button',{name:'Save private note'}).click();
    await expect(page.locator('#notes')).toContainText('Private:');
    await page.getByLabel('Bio',{exact:true}).fill('I follow echoes <script>bad()</script>');
    await page.getByLabel('Avatar',{exact:true}).selectOption('river');
    await page.getByLabel('Publish this profile to invited players').check();
    await page.getByRole('button',{name:'Save profile',exact:true}).click();
    const link=page.getByRole('link',{name:'View and share your profile'});
    await expect(link).toBeVisible();
    const other=await browser.newContext();
    try {
      const visitor=await other.newPage();
      await visitor.addInitScript(key=>localStorage.setItem('nw_beta_key',key),otherKey);
      await visitor.goto(server.url+await link.getAttribute('href'));
      await expect(visitor.getByText('I follow echoes <script>bad()</script>',{exact:true})).toBeVisible();
      await expect(visitor.getByLabel('river avatar')).toBeVisible();
      await expect(visitor.locator('body')).not.toContainText('Private:');
      await visitor.goto(server.url+'/journal');
      await expect(visitor.locator('#notes')).not.toContainText('Private:');
    } finally {await other.close();}
  } finally {await server.close();}
});

test('320px GPU-free scene offers keyboard navigation and one action surface', async ({page}) => {
  const server = await start();
  try {
    await page.setViewportSize({width: 320, height: 740});
    await page.addInitScript(() => {
      const getContext = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        if (type.includes('webgl') || type.includes('webgpu')) return null;
        return getContext.call(this, type, ...args);
      };
      Object.defineProperty(navigator, 'gpu', {value: undefined, configurable: true});
    });
    await enter(page, server);
    await expect(page.getByRole('button', {name: 'Act',exact:true})).toBeVisible();
    // Pixi can use its canvas renderer without a GPU; text passages remain
    // keyboard accessible regardless of which renderer is available.
    const passage = page.getByRole('button', {name: 'Room ↘ Broken Ember Gallery', exact: true});
    await passage.focus(); await page.keyboard.press('Enter');
    await expect(page.locator('[title="Broken Ember Gallery-1111111"]').first()).toBeVisible();
    await expect(page.getByRole('button', {name: 'Act',exact:true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: capture('enfolded-discovery-gpu-free.png')});
  } finally { await server.close(); }
});


test('renderer initialization failure leaves a navigable text scene', async ({page}) => {
  const server = await start();
  try {
    await page.addInitScript(() => { HTMLCanvasElement.prototype.getContext = () => null; });
    await enter(page, server);
    await expect(page.getByRole('region', {name: 'Text scene'})).toBeVisible();
    await page.getByRole('region', {name: 'Text scene'}).getByRole('button').first().click();
    await expect(page.locator('[title="Broken Ember Gallery-1111111"]').first()).toBeVisible();
  } finally { await server.close(); }
});

for (const saveFailure of [false,true]) {
  test(`acting waits for arrival${saveFailure?' and recovers from a failed save':''}`,async({page})=>{
    const server=await start();let release,blocked=false,attempts=0,canSave=!saveFailure;
    const held=new Promise(resolve=>{release=resolve;});const submissions=[];
    page.on('request',r=>{if(new URL(r.url()).pathname==='/interventions/commit')submissions.push(r.postDataJSON());});
    try {
      await page.route('**/position*',async route=>{
        const r=route.request();
        if(r.method()==='POST' && r.postDataJSON()?.node===names.instrument){
          if(++attempts===1){blocked=true;await held;}
          if(!canSave)return route.abort('failed');
        }await route.continue();
      });
      await enter(page,server,'/app?node='+encodeURIComponent(names.instrument));
      await page.getByRole('button',{name:'Act',exact:true}).click();
      const act=page.locator('enfolded-interventions');
      await act.getByRole('button',{name:'Engrave',exact:true}).click();
      const commit=act.getByRole('button',{name:'Act: Engrave',exact:true});
      await commit.click();await expect(commit).toBeDisabled();
      await expect.poll(()=>blocked).toBe(true);expect(submissions).toEqual([]);release();
      if(saveFailure){await expect(act.getByRole('status')).toContainText('arrival');expect(submissions).toEqual([]);canSave=true;await commit.click();}
      await expect.poll(()=>submissions.length).toBe(1);
      await expect(act.getByRole('status')).toContainText('Engrave');
      await page.reload();
      await expect(page.locator('.world-panel').getByTitle(names.instrument,{exact:true}).filter({hasText:/^Elder River Instrument$/})).toBeVisible();
    }finally {release();await page.unrouteAll({behavior:'wait'}).catch(()=>{});await server.close();}
  });
}

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
const headers = {'X-Beta-Key': key};
const names = {
  region: 'Emberlit Orchard Terraces-111111',
  instrument: 'Elder River Instrument-11111111',
  regulator: 'Amber Ember Mechanism-11111112',
  fold: 'Elder Lantern Fold-111111112',
  chain: 'Distant River Chain-111111111',
};
const phrase = name => name.replace(/-\d+$/, '');
const capture = name => path.join(tmpdir(), name);

async function start() {
  const dir = await mkdtemp(path.join(tmpdir(), 'enfolded-expressive-'));
  const child = spawn(python, ['-u', '-c', `
import sys
from pathlib import Path
import persistence
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
from multiverse import situation
situation.WINDOW_SECONDS=4
from persistence import interventions
interventions.HOP_SECONDS=1
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
async function enter(page, server, route = '/app', node = '') {
  await page.addInitScript(({key, node}) => {
    localStorage.setItem('nw_beta_key', key);
    localStorage.setItem('nw_player_name', 'Ada');
    localStorage.setItem('nw_seen_intro', '1');
    if (node) localStorage.setItem('nw_last_node', node);
  }, {key, node});
  await page.goto(server.url + route);
}

for(const route of ['/app','/']) {
  test(`${route}: compose, recover a lost acknowledgement, receive and return`,async({page})=>{
    const server=await start();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    try {
      await page.setViewportSize({width:1440,height:960});
      await enter(page,server,route,names.instrument);
      const composer=page.locator('enfolded-interventions');
      await expect(page.getByRole('region',{name:'Investigation'})).toHaveCount(0);
      await expect(page.getByText('Shape this place',{exact:true})).toHaveCount(0);
      if(route==='/') await page.locator('#btn-act').click();
      else await page.getByRole('button',{name:'Act',exact:true}).click();
      await expect(composer).toHaveCount(1);
      await expect(composer.getByRole('button',{name:'Charge',exact:true})).toHaveCount(0);
      await expect(composer.getByRole('button',{name:'Act: Engrave',exact:true})).toHaveCount(0);
      await composer.getByRole('button',{name:'Engrave',exact:true}).click();
      await expect(composer).toContainText('surface → engraved');
      let dropped=false;
      await page.route('**/interventions/commit',async intercept=>{
        if(!dropped){ dropped=true;await intercept.fetch();await intercept.abort('failed'); }
        else await intercept.continue();
      });
      await composer.getByRole('button',{name:'Act: Engrave',exact:true}).click();
      await expect(composer.getByRole('button',{name:'Confirm earlier action',exact:true})).toBeEnabled();
      await page.reload();
      if(route==='/') await page.locator('#btn-act').click();
      else await page.getByRole('button',{name:'Act',exact:true}).click();
      await expect(composer.getByRole('button',{name:'Confirm earlier action',exact:true})).toBeVisible();
      await composer.getByRole('button',{name:'Confirm earlier action',exact:true}).click();
      await composer.getByText('Actions still echoing',{exact:true}).click();
      await expect(composer).toContainText('All consequences settled',{timeout:15000});
      const result=await(await page.request.get(server.url+'/interventions?node='+names.instrument,{headers})).json();
      expect(result.recent.filter(r=>r.origin===names.instrument)).toHaveLength(1);
      expect(result.recent[0].summary).toBe('Engrave');
      expect(result.recent[0].arrivals).toHaveLength(3);
      await page.screenshot({path:capture(`enfolded-expressive-${route==='/app'?'scene':'map'}.png`)});
      await page.setViewportSize({width:390,height:844});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:capture(`enfolded-expressive-${route==='/app'?'scene':'map'}-mobile.png`),fullPage:true});
      expect(errors).toEqual([]);
    }finally{await server.close();}
  });
}

test('recorded score loads, stays on one transport and changes its harmony',async({page})=>{
  const server=await start();
  try {
    await enter(page,server,'/',names.instrument);
    await expect(page.locator('#node-name')).toHaveText(phrase(names.instrument));
    await page.click('#btn-sound');
    await expect.poll(()=>page.evaluate(()=>Object.keys(window._nwAmbience?.buffers || {}).length)).toBe(11);
    const evidence=await page.evaluate(()=>{
      const score=window._nwAmbience,ctx=score.ctx;
      const step=score.step;
      score.setNode(382,{name:'Changed',senses:{family:1,polarity:-1,revision:'test',woven:true,echo:-3}});
      return {sameContext:score.ctx===ctx,stepUnchanged:score.step===step,third:score.pending.third,durations:Object.values(score.buffers).map(b=>b.duration)};
    });
    expect(evidence.sameContext).toBe(true);expect(evidence.stepUnchanged).toBe(true);expect(evidence.third).toBe(3);
    expect(evidence.durations.every(d=>d>1)).toBe(true);
    await page.click('#btn-sound');
    expect(await page.evaluate(()=>window._nwAmbience.enabled)).toBe(false);
  }finally{await server.close();}
});


test('the complete sampled graph renders non-silent audio without clipping', async({page})=>{
  await page.goto('/');
  const metrics=await page.evaluate(async()=>{
    const {NodeAmbience}=await import('/score.js');
    const offline=new OfflineAudioContext(2,44100*18,44100);
    let time=0;
    const context=new Proxy(offline,{get(target,key){
      if(key==='currentTime')return time;
      if(key==='state')return 'running';
      if(key==='resume')return ()=>Promise.resolve();
      const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
    }});
    const score=new NodeAmbience();score.ctx=context;
    score.enable(382,{name:'Chain',level:'Molecule',senses:{family:2,tension:.8,energy:.8,woven:true,memory:'1234',atmosphere:'electric'}});
    clearInterval(score.timer);await score.loading;
    for(time=0;time<17;time+=.05)score.schedule();
    const result=await offline.startRendering();
    let peak=0,squares=0,finite=true;
    for(let c=0;c<2;c++)for(const x of result.getChannelData(c)){peak=Math.max(peak,Math.abs(x));squares+=x*x;finite=finite&&Number.isFinite(x);}
    return {peak,rms:Math.sqrt(squares/(result.length*2)),finite,samples:Object.keys(score.buffers).length};
  });
  expect(metrics.samples).toBe(11);expect(metrics.finite).toBe(true);
  expect(metrics.rms).toBeGreaterThan(.001);expect(metrics.peak).toBeLessThan(.99);
  console.log('Sampled score render:',JSON.stringify(metrics));
});


test('unavailable recovery storage prevents an ambiguous commitment',async({page})=>{
  const server=await start();let submissions=0;
  page.on('request',request=>{if(new URL(request.url()).pathname==='/interventions/commit')submissions++;});
  try{
    await page.addInitScript(()=>{
      const set=Storage.prototype.setItem;
      Storage.prototype.setItem=function(key,value){if(String(key).startsWith('nw_arrangement:'))throw new Error('fixture quota');return set.call(this,key,value);};
    });
    await enter(page,server,'/app',names.instrument);
    const composer=page.locator('enfolded-interventions');
    await page.getByRole('button',{name:'Act',exact:true}).click();
    await composer.getByRole('button',{name:'Engrave',exact:true}).click();
    await composer.getByRole('button',{name:'Act: Engrave',exact:true}).click();
    await expect(composer).toContainText('Nothing was submitted.');
    expect(submissions).toBe(0);
    await expect(composer.getByRole('button',{name:'Act: Engrave',exact:true})).toBeEnabled();
  }finally{await server.close();}
});

for(const route of ['/app','/']) {
  test(`${route}: one identity block follows another player's material change`,async({page})=>{
    const server=await start();
    try {
      await enter(page,server,route,names.instrument);
      const identity=page.locator('.node-identity');
      await expect(identity).toHaveCount(1);
      await expect(identity.getByRole('heading',{name:phrase(names.instrument),exact:true})).toBeVisible();
      await expect(identity.locator('#node-level')).toHaveText('Object');
      await expect(identity.locator('#node-address')).toContainText('11111111');
      await expect(identity.locator('#node-description')).toContainText('surface is');
      for(const id of ['node-name','node-level','node-address','node-description']) await expect(page.locator('#'+id)).toHaveCount(1);
      if(route==='/app') {
        const scene=page.getByRole('region',{name:'Living scene'});
        await expect(scene.getByRole('heading')).toHaveCount(0);
        await expect(page.getByText(phrase(names.instrument),{exact:true})).toHaveCount(1);
        await expect(scene.locator('canvas')).toHaveAttribute('aria-describedby','node-description');
        await page.getByText('Conditions here',{exact:true}).click();
        await expect(page.getByText('aspect',{exact:true})).toHaveCount(0);
      }
      const before=await identity.locator('#node-description').textContent();
      // A distinct player acts via the real endpoint. The first viewer receives
      // the shared update without navigation, a reload or their own action.
      const other={'X-Beta-Key':'nw_'+'b'.repeat(32)};
      expect((await page.request.post(server.url+'/position',{headers:other,data:{node:names.instrument,seed:382,depth:9}})).ok()).toBe(true);
      const plan=await(await page.request.post(server.url+'/interventions/preview',{headers:other,data:{node:names.instrument,steps:[{op:'engrave'}]}})).json();
      const result=await page.request.post(server.url+'/interventions/commit',{headers:other,data:{node:names.instrument,steps:plan.steps,expected:plan.expected,version:2,request_id:'peer-description'}});
      expect(result.ok()).toBe(true);
      await expect(identity.locator('#node-description')).toContainText('surface is engraved');
      expect(await identity.locator('#node-description').textContent()).not.toBe(before);
      await expect(identity.getByRole('heading')).toHaveText(phrase(names.instrument));
      await page.reload();
      await expect(identity.locator('#node-description')).toContainText('surface is engraved');
      await page.setViewportSize({width:390,height:844});
      await expect(identity).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:capture(`enfolded-identity-${route==='/app'?'scene':'map'}-mobile.png`),fullPage:true});
    } finally {await server.close();}
  });
}

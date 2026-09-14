import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '../..');
const python = process.env.ENFOLDED_PYTHON || 'python';
const key = 'nw_' + 'a'.repeat(32);
const headers = {'X-Beta-Key': key};
const evidence = path.join(tmpdir(), 'enfolded-ideas-evidence');
async function capture(page, name) {
  await mkdir(evidence, {recursive: true});
  await page.screenshot({path: path.join(evidence, name + '.png'), fullPage: true});
}
async function start() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-ideas-browser-'));
  const child = spawn(python, ['-u','-c', `
import sys
from pathlib import Path
import persistence as db
db._DB_PATH=Path(sys.argv[1])/'worlds.db'
db.mint_invite_key('nw_'+'a'*32,'Ada')
db.mint_invite_key('nw_'+'b'*32,'Bea')
from server import _Handler,_ThreadedServer
server=_ThreadedServer(('127.0.0.1',0),_Handler)
print(server.server_port,flush=True)
server.serve_forever()
`, directory], {cwd: repo, env: {...process.env, NESTED_WORLDS_CANONICAL_SEED:'382',
    NESTED_WORLDS_DISABLE_AI:'1', NESTED_WORLDS_DISABLE_IMAGES:'1'}, stdio:['ignore','pipe','pipe']});
  let stderr = ''; child.stderr.on('data', chunk => { stderr += chunk; });
  const port = await new Promise((resolve,reject) => {
    const timer = setTimeout(() => reject(new Error(stderr || 'Ideas fixture did not start')), 15000);
    child.stdout.once('data', chunk => { clearTimeout(timer); resolve(Number(String(chunk).trim())); });
    child.once('exit', () => { clearTimeout(timer); reject(new Error(stderr)); });
  }).catch(error => { child.kill('SIGKILL'); throw error; });
  return {url:`http://127.0.0.1:${port}`, async close() {
    const ended = once(child,'exit'); child.kill('SIGKILL'); await ended; await rm(directory,{recursive:true,force:true});
  }};
}
async function enter(page, server, route='/ideas') {
  await page.addInitScript(key => {
    localStorage.setItem('nw_beta_key',key);
    localStorage.setItem('nw_player_name','Ada');
    localStorage.setItem('nw_seen_intro','1');
    sessionStorage.setItem('nw_sound_invited','1');
  }, key);
  await page.goto(server.url + route);
}
async function keyboardTo(page, target) {
  for (let i=0;i<60;i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(node => node === document.activeElement)) return;
  }
  throw new Error('Could not reach control with keyboard');
}

for (const mobile of [false,true]) {
  for (const route of ['/','/app']) {
    test(`Ideas entry preserves ${route === '/' ? 'map' : 'scene'} game on ${mobile ? 'mobile' : 'desktop'}`, async ({page,context}) => {
      const server = await start();
      try {
        await page.setViewportSize(mobile ? {width:390,height:844} : {width:1440,height:1000});
        await enter(page,server,route);
        const link = page.getByRole('link',{name:'Ideas ↗',exact:true});
        await expect(link).toBeVisible();
        await expect(page.getByRole('link',{name:"Player's Guide ↗",exact:true})).toBeVisible();
        await expect(link).toHaveAttribute('href','/ideas');
        await expect(link).toHaveAttribute('target','_blank');
        await expect.poll(() => page.evaluate(() => localStorage.getItem('nw_last_node'))).not.toBeNull();
        const priorUrl = page.url();
        const priorNode = await page.evaluate(() => localStorage.getItem('nw_last_node'));
        await capture(page,`${route === '/' ? 'map' : 'scene'}-${mobile ? 'mobile' : 'desktop'}`);
        await keyboardTo(page,link);
        const popupPromise = context.waitForEvent('page');
        await page.keyboard.press('Enter');
        const board = await popupPromise;
        await expect(board.locator('#board')).toBeVisible();
        await expect(board.locator('#attribution')).toContainText('Ada');
        expect(board.url()).toBe(server.url+'/ideas');
        expect(page.url()).toBe(priorUrl);
        expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBe(priorNode);
        expect(await board.evaluate(() => window.opener)).toBeNull();
        await board.close();
      } finally { await server.close(); }
    });
  }
  test(`Ideas board ${mobile ? 'mobile' : 'desktop'}: empty, validation, text safety, voting, search and withdrawal`, async ({page}) => {
    const server = await start();
    try {
      await page.setViewportSize(mobile ? {width:390,height:844} : {width:1280,height:900});
      await enter(page,server);
      await expect(page.locator('#results')).toHaveAttribute('aria-busy','false');
      await expect(page.locator('#result-status')).toContainText('No ideas yet');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(page,`board-empty-${mobile ? 'mobile' : 'desktop'}`);
      await page.locator('#submit-button').click();
      await expect(page.locator('#title')).toBeFocused();
      const title = '<img src=x onerror="window.__ideasXss=1">';
      await page.getByLabel('Title',{exact:true}).fill(title);
      await page.getByLabel('Your experience and desired outcome').fill('I want a clearer signal when a crossing opens. <script>window.__ideasXss=1</script>');
      await page.locator('#submit-button').click();
      await expect(page.getByRole('link',{name:'Your stable idea link'})).toBeVisible();
      const submitted = await page.request.get(server.url+'/ideas/list',{headers});
      const data = await submitted.json(); expect(data.ideas).toHaveLength(1);
      await page.getByRole('link',{name:'Your stable idea link'}).click();
      await expect(page.locator('#detail-title')).toHaveText(title);
      expect(await page.evaluate(() => window.__ideasXss)).toBeUndefined();
      expect(await page.locator('#detail img,#results img,#detail script').count()).toBe(0);
      const support = page.getByRole('button',{name:'Support idea',exact:true});
      await support.focus(); await page.keyboard.press('Enter');
      await expect(page.getByRole('button',{name:'Undo support',exact:true})).toHaveAttribute('aria-pressed','true');
      await page.getByRole('button',{name:'Undo support',exact:true}).click();
      await expect(page.getByRole('button',{name:'Support idea',exact:true})).toHaveAttribute('aria-pressed','false');
      await page.getByRole('button',{name:'Most supported',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      await page.getByRole('button',{name:'Your submissions',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      await page.getByLabel('Search ideas',{exact:true}).fill('no match anywhere');
      await page.getByRole('button',{name:'Search',exact:true}).click();
      await expect(page.locator('#result-status')).toContainText('No matching ideas');
      await page.getByLabel('Search ideas',{exact:true}).fill('signal');
      await page.getByRole('button',{name:'Search',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(page,`board-detail-${mobile ? 'mobile' : 'desktop'}`);
      await page.getByRole('button',{name:'Withdraw my idea'}).click();
      await expect(page.getByRole('button',{name:'Keep idea'})).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('button',{name:'Withdraw my idea'})).toBeFocused();
      await page.getByRole('button',{name:'Withdraw my idea'}).click();
      await page.getByRole('button',{name:'Withdraw idea',exact:true}).click();
      await expect(page.locator('#message')).toContainText('was withdrawn');
      await expect(page.locator('#detail')).toBeHidden();
    } finally { await server.close(); }
  });
}

test('Draft survives rejected and interrupted submissions; retries recover one saved idea', async ({page}) => {
  const server = await start();
  try {
    await enter(page,server); await expect(page.locator('#board')).toBeVisible();
    await page.getByLabel('Title',{exact:true}).fill('A draft that must survive');
    await page.getByLabel('Your experience and desired outcome').fill('My experience stays here.');
    await page.route('**/ideas/submit', route => route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Please revise the idea.'})}));
    await page.locator('#submit-button').click();
    await expect(page.locator('#message')).toContainText('Please revise');
    await expect(page.locator('#title')).toHaveValue('A draft that must survive');
    await capture(page,'board-validation');
    await page.unroute('**/ideas/submit');
    await page.route('**/ideas/submit', async route => { await route.fetch(); await route.abort(); });
    await page.locator('#submit-button').click();
    await expect(page.locator('#draft-state')).toContainText('may have arrived');
    await expect(page.locator('#title')).toBeDisabled();
    await capture(page,'board-interrupted-submission');
    await page.reload();
    await expect(page.locator('#title')).toHaveValue('A draft that must survive');
    await expect(page.locator('#title')).toBeDisabled();
    await page.unroute('**/ideas/submit');
    await page.getByRole('button',{name:'Retry submission to confirm'}).click();
    await expect(page.locator('#message')).toContainText('Idea submitted');
    expect((await (await page.request.get(server.url+'/ideas/list',{headers})).json()).ideas).toHaveLength(1);
    await page.getByRole('link',{name:'Your stable idea link'}).click();
    await page.route('**/ideas/vote', async route => { await route.fetch(); await route.abort(); });
    await page.getByRole('button',{name:'Support idea',exact:true}).click();
    await expect(page.locator('#message')).toContainText('connection did not finish');
    await expect(page.getByRole('button',{name:'Support idea',exact:true})).toHaveAttribute('aria-pressed','false');
    await page.unroute('**/ideas/vote');
    await page.getByRole('button',{name:'Support idea',exact:true}).click();
    await expect(page.getByRole('button',{name:'Undo support',exact:true})).toBeVisible();
    expect((await (await page.request.get(server.url+'/ideas/list',{headers})).json()).ideas[0].votes).toBe(1);
  } finally { await server.close(); }
});

test('Public shell, loading, network failure and keyboard retry', async ({page}) => {
  const server = await start();
  try {
    await page.goto(server.url+'/ideas');
    await expect(page.locator('#notice')).toBeVisible(); await expect(page.locator('#board')).toBeHidden();
    await page.evaluate(key => localStorage.setItem('nw_beta_key',key),key);
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route('**/ideas/search',async route => { await gate; await route.abort(); });
    await page.reload();
    await expect(page.locator('#message')).toContainText('Loading ideas');
    await capture(page,'board-loading'); release();
    await expect(page.locator('#message')).toContainText('connection did not finish');
    await capture(page,'board-load-failure');
    await page.unroute('**/ideas/search');
    await page.locator('#retry').focus(); await page.keyboard.press('Enter');
    await expect(page.locator('#board')).toBeVisible();
  } finally { await server.close(); }
});

import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '../..');
const python = process.env.ENFOLDED_PYTHON || 'python';
const key = 'nw_' + 'a'.repeat(32);
const otherKey = 'nw_' + 'b'.repeat(32);
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
    child.stdout.once('data', chunk => { clearTimeout(timer); resolve(Number(String(chunk).trim())); });
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
async function clue(page, server, role) {
  const panel = page.getByRole('region', {name: 'Investigation'});
  const label = role === 'chain' ? 'Visit the chain' : phrase(names[role]);
  await panel.getByRole('button', {name: label, exact: true}).click();
  await expect.poll(async () => (await (await page.request.get(server.url + '/position', {headers})).json()).position?.node).toBe(names[role]);
  await panel.getByRole('button', {name: 'Read the clue here'}).click();
  await expect(panel.locator('blockquote')).toBeVisible();
}

for (const branch of ['preserve', 'release']) {
  test(`scene ${branch}: discover, decide, return, leave a lasting marker and keep notes private`, async ({page, browser}) => {
    const server = await start();
    try {
      await page.setViewportSize({width: 1280, height: 900});
      await enter(page, server);
      const panel = page.getByRole('region', {name: 'Investigation'});
      await expect(panel).toContainText('The signal in the gallery');
      await clue(page, server, 'instrument');
      await clue(page, server, 'regulator');
      await panel.getByRole('button', {name: 'Choose this route', exact: true}).nth(branch === 'preserve' ? 0 : 1).click();
      await expect.poll(async () => (await (await page.request.get(server.url + '/situation', {headers})).json()).situation.phase, {timeout: 12000}).toBe('aftermath');
      await page.reload();
      await expect(panel).toContainText('THE AFTERMATH');
      await clue(page, server, 'fold');
      await clue(page, server, 'chain');
      await panel.getByRole('button', {name: 'Set a reference marker'}).click();
      await expect(panel.getByRole('button', {name: 'Your reference marker remains'})).toBeDisabled();
      if (branch === 'release') await page.screenshot({path: capture('enfolded-discovery-desktop.png')});
      await page.goto(server.url + '/journal?node=' + names.chain);
      await page.getByLabel('Question or observation').fill('Private: why did the echo continue?');
      await page.getByRole('button', {name: 'Save private note'}).click();
      await expect(page.locator('#notes')).toContainText('Private:');
      await page.getByLabel('Bio', {exact: true}).fill('I follow echoes <script>bad()</script>');
      await page.getByLabel('Avatar', {exact: true}).selectOption('river');
      await page.getByLabel('Publish this profile to invited players').check();
      await page.getByRole('button', {name: 'Save profile', exact: true}).click();
      await expect(page.getByRole('link', {name: 'View and share your profile'})).toBeVisible();
      const profileLink = await page.getByRole('link', {name: 'View and share your profile'}).getAttribute('href');
      const other = await browser.newContext();
      try {
        const visitor = await other.newPage();
        await visitor.addInitScript(key => localStorage.setItem('nw_beta_key', key), otherKey);
        await visitor.goto(server.url + profileLink);
        await expect(visitor.getByText('I follow echoes <script>bad()</script>', {exact: true})).toBeVisible();
        await expect(visitor.getByLabel('river avatar')).toBeVisible();
        await expect(visitor.locator('body')).not.toContainText('Private:');
        await visitor.goto(server.url + '/journal');
        await expect(visitor.locator('#notes')).not.toContainText('Private:');
      } finally { await other.close(); }
      await page.setViewportSize({width: 390, height: 844});
      await page.screenshot({path: capture(`enfolded-journal-${branch}-mobile.png`), fullPage: true});
      await page.getByRole('link', {name: phrase(names.chain), exact: true}).last().click();
      await expect(page.locator(`[title="${names.chain}"]`).first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (branch === 'release') await page.screenshot({path: capture('enfolded-discovery-mobile.png')});
    } finally { await server.close(); }
  });
}

for (const route of ['/', '/app']) {
  test(`${route} recovers an accepted act after its response is lost and the page reloads`, async ({page}) => {
    const server = await start();
    try {
      await enter(page, server, route, names.instrument);
      if (route === '/') await page.locator('#btn-act').click();
      else await page.getByRole('button', {name: 'Mend', exact: true}).click();
      let first;
      await page.route('**/act?*', async intercept => {
        const response = await intercept.fetch(); first = await response.json(); await intercept.abort();
      }, {times: 1});
      await page.getByRole('button', {name: 'Mend this Object', exact: true}).click();
      await expect.poll(() => first?.event_id).toBeTruthy();
      await page.reload();
      if (route === '/') await page.locator('#btn-act').click();
      else await page.getByRole('button', {name: 'Mend', exact: true}).click();
      const [response] = await Promise.all([
        page.waitForResponse(r => new URL(r.url()).pathname === '/act'),
        page.getByRole('button', {name: 'Mend this Object', exact: true}).click(),
      ]);
      expect((await response.json()).event_id).toBe(first.event_id);
    } finally { await server.close(); }
  });
}

test('320px GPU-free scene offers keyboard navigation and investigation controls', async ({page}) => {
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
    await expect(page.getByRole('region', {name: 'Investigation'})).toBeVisible();
    // Pixi can use its canvas renderer without a GPU; text passages remain
    // keyboard accessible regardless of which renderer is available.
    const passage = page.getByRole('button', {name: '→ Broken Ember Gallery (Room)', exact: true});
    await passage.focus(); await page.keyboard.press('Enter');
    await expect(page.locator('[title="Broken Ember Gallery-1111111"]').first()).toBeVisible();
    await expect(page.getByRole('region', {name: 'Investigation'})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: capture('enfolded-discovery-gpu-free.png')});
  } finally { await server.close(); }
});


test('renderer initialization failure leaves a navigable text scene', async ({page}) => {
  const server = await start();
  try {
    await page.route('**/assets/init-*.js', route => route.abort());
    await enter(page, server);
    await expect(page.getByRole('region', {name: 'Text scene'})).toBeVisible();
    await page.getByRole('region', {name: 'Text scene'}).getByRole('button').first().click();
    await expect(page.locator('[title="Broken Ember Gallery-1111111"]').first()).toBeVisible();
  } finally { await server.close(); }
});

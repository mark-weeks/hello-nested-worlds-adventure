import { expect, test } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { serveBrowser } from './server.js';

const KEY = 'nw_' + '9'.repeat(32);
const NAME = 'Test traveler';
const TOKEN = 'nwr_' + '8'.repeat(32);
const AGREEMENT = 'I confirm I am at least 18 years old, have read this notice and agree to participate in this temporary test world.';
// These are disposable fixture values, not an adopted player policy.
const noticeEnv = {
  NESTED_WORLDS_TEST_WORLD: '1',
  NESTED_WORLDS_TEST_CONTACT: 'Fixture facilitator',
  NESTED_WORLDS_TEST_RETENTION: 'Fixture world and backups removed at fixture teardown.',
  NESTED_WORLDS_TEST_MIN_AGE: '18',
  NESTED_WORLDS_TEST_DATA_USE: 'No model provider receives fixture data.',
};

async function failMetadata(route, failure) {
  if (failure === 'network') return route.abort('connectionreset');
  return route.fulfill({ status: failure, contentType: 'text/html', body: 'metadata temporarily unavailable' });
}

async function returning(page) {
  await page.addInitScript(() => {
    localStorage.setItem('nw_seen_intro', '1');
    localStorage.setItem('nw_sound_preference', 'off');
  });
}

function countGameplay(page) {
  let worlds = 0, sockets = 0;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/world') worlds += 1;
  });
  page.on('websocket', () => { sockets += 1; });
  return () => ({ worlds, sockets });
}

async function accept(page) {
  const submit = page.getByRole('button', { name: 'Agree and continue', exact: true });
  await expect(submit).toBeDisabled();
  await expect(page.locator('.participation-gate').getByRole('checkbox')).toHaveCount(1);
  await page.getByRole('checkbox', { name: AGREEMENT, exact: true }).check();
  await submit.click();
}

for (const route of ['/', '/app']) {
  test(`${route}: an earlier intro never accepts staging consent; reload and a fresh device read server acceptance`, async ({ browser }) => {
    test.setTimeout(60_000);
    const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME, env: noticeEnv });
    const context = await browser.newContext();
    const fresh = await browser.newContext();
    try {
      const page = await context.newPage();
      await returning(page);
      const counts = countGameplay(page);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`);
      await expect(page.getByRole('heading', { name: 'Temporary test world' })).toBeVisible();
      await expect(page.getByText('Questions or concerns: Fixture facilitator', { exact: true })).toBeVisible();
      expect(counts()).toEqual({ worlds: 0, sockets: 0 });
      await accept(page);
      await expect(page.locator('#node-name')).toBeVisible();
      await expect.poll(() => counts().sockets).toBe(1);
      expect(counts().worlds).toBeGreaterThan(0);
      let accepts = 0;
      page.on('request', request => {
        if (new URL(request.url()).pathname === '/participation' && request.method() === 'POST') accepts += 1;
      });
      await page.reload();
      await expect(page.locator('#node-name')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Agree and continue' })).toHaveCount(0);
      expect(accepts).toBe(0);
      const freshPage = await fresh.newPage();
      await returning(freshPage);
      await freshPage.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`);
      await expect(freshPage.locator('#node-name')).toBeVisible();
      await expect(freshPage.getByRole('button', { name: 'Agree and continue' })).toHaveCount(0);
      expect(errors).toEqual([]);
    } finally {
      await context.close(); await fresh.close(); await server.close();
    }
  });
}

for (const route of ['/', '/app']) for (const failure of [429, 502, 'network']) {
  test(`${route}: an unknown ordinary-world metadata ${failure} does not block entry`, async ({ page }) => {
    const server = await serveBrowser({ preseed: 382 });
    try {
      await returning(page);
      await page.addInitScript(() => localStorage.setItem('nw_player_name', 'Ordinary traveler'));
      await page.route('**/participation', intercepted => failMetadata(intercepted, failure), { times: 1 });
      await page.goto(server.url + route);
      await expect(page.locator('#node-name')).toBeVisible();
      await expect(page.locator('.participation-gate')).toHaveCount(0);
      await expect(page.locator('body')).not.toContainText('test notice could not be reached');
    } finally { await server.close(); }
  });

  test(`${route}: an unknown test-world metadata ${failure} recovers through its real world refusal`, async ({ page }) => {
    const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME, env: noticeEnv });
    try {
      await returning(page);
      const counts = countGameplay(page);
      await page.route('**/participation', intercepted => failMetadata(intercepted, failure), { times: 1 });
      await page.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`);
      await expect(page.getByRole('heading', { name: 'Temporary test world' })).toBeVisible();
      expect(counts()).toEqual({ worlds: 1, sockets: 0 });
      await accept(page);
      await expect(page.locator('#node-name')).toBeVisible();
      await expect.poll(() => counts().sockets).toBe(1);
      expect(counts().worlds).toBe(2);
    } finally { await server.close(); }
  });
}

for (const route of ['/guide', `/register?invite=${TOKEN}`]) for (const failure of [429, 502, 'network']) {
  test(`${route}: metadata ${failure} preserves ordinary copy and can reveal temporary copy on retry`, async ({ page }) => {
    // Test each page against both operator modes: raw HTML always preserves
    // the standing promise, and only a successful explicit test notice swaps it.
    for (const temporary of [false, true]) {
      const server = await serveBrowser({ env: temporary ? noticeEnv : {} });
      try {
        await page.route('**/participation', intercepted => failMetadata(intercepted, failure), { times: 1 });
        await page.goto(server.url + route);
        await expect(page.getByRole('button', { name: 'Load the notice again', exact: true })).toBeVisible();
        if (route === '/guide') await expect(page.locator('body')).toContainText("world's permanent chronicle");
        else await expect(page.locator('#register')).toContainText('recorded under it, permanently,');
        await page.getByRole('button', { name: 'Load the notice again', exact: true }).click();
        if (temporary) {
          await expect(page.getByRole('heading', { name: 'Temporary test world', exact: true })).toBeVisible();
          await expect(page.locator('body')).not.toContainText("world's permanent chronicle");
          if (route !== '/guide') await expect(page.locator('#register')).not.toContainText('recorded under it, permanently,');
        } else {
          await expect(page.locator('[data-participation-notice]')).toBeHidden();
          if (route === '/guide') await expect(page.getByRole('heading', { name: 'Nothing is lost', exact: true })).toBeVisible();
          else await expect(page.locator('#register')).toContainText('recorded under it, permanently,');
        }
      } finally { await server.close(); }
    }
  });
}

test('a known test-world notice failure stays closed until an explicit retry', async ({ page }) => {
  const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME, env: noticeEnv });
  try {
    await returning(page);
    const counts = countGameplay(page);
    await page.route('**/participation', async route => {
      if (route.request().headers()['x-beta-key']) {
        await route.fulfill({ status: 502, contentType: 'text/html', body: 'temporarily unavailable' });
        await page.unroute('**/participation');
      } else await route.continue();
    });
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await expect(page.getByText('Participation information could not be reached. Try loading it again.', { exact: true })).toBeVisible();
    expect(counts()).toEqual({ worlds: 0, sockets: 0 });
    await page.getByRole('button', { name: 'Load the notice again', exact: true }).click();
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
  } finally { await server.close(); }
});

test('registration shows the same notice and a newly minted key still needs an affirmative choice', async ({ page }) => {
  test.setTimeout(60_000);
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-participation-register-'));
  const database = path.join(directory, 'worlds.db');
  const seeded = spawnSync(process.env.ENFOLDED_PYTHON || 'python', ['-c', `
from pathlib import Path
import sys
import persistence
persistence._DB_PATH=Path(sys.argv[1])
persistence.create_registration_token(sys.argv[2])
`, database, TOKEN], { cwd: path.resolve(import.meta.dirname, '../..'), encoding: 'utf8' });
  if (seeded.status !== 0) throw new Error(seeded.stderr);
  const server = await serveBrowser({ database, preseed: 382, env: noticeEnv });
  try {
    await returning(page);
    const counts = countGameplay(page);
    await page.goto(`${server.url}/register?invite=${TOKEN}`);
    await expect(page.getByRole('heading', { name: 'Temporary test world' })).toBeVisible();
    await expect(page.locator('#register')).not.toContainText('permanently');
    await page.getByLabel('Your name', { exact: true }).fill(NAME);
    await page.getByRole('button', { name: 'Enter the worlds', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toBeVisible();
    expect(counts()).toEqual({ worlds: 0, sockets: 0 });
    const key = await page.evaluate(() => localStorage.getItem('nw_beta_key'));
    const response = await page.request.get(`${server.url}/world`, { headers: { 'X-Beta-Key': key } });
    expect(response.status()).toBe(428);
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
  } finally {
    await server.close(); await rm(directory, { recursive: true, force: true });
  }
});

test('an incomplete notice prevents gameplay and offers no acknowledgement', async ({ page }) => {
  const server = await serveBrowser({ invite: KEY, player: NAME, env: { ...noticeEnv, NESTED_WORLDS_TEST_RETENTION: '' } });
  try {
    const counts = countGameplay(page);
    await returning(page);
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await expect(page.getByText('This test is not ready for visitors. Ask the person who invited you to finish its participation notice.', { exact: true })).toBeVisible();
    await expect(page.getByRole('checkbox')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Load the notice again', exact: true })).toBeVisible();
    expect(counts()).toEqual({ worlds: 0, sockets: 0 });
  } finally { await server.close(); }
});

test('public guide and registration render configured text without executing markup', async ({ page }) => {
  const injected = '<img src=x onerror="window.noticeExecuted=true">';
  const server = await serveBrowser({ env: { ...noticeEnv, NESTED_WORLDS_TEST_CONTACT: injected } });
  try {
    for (const route of ['/guide', `/register?invite=${TOKEN}`]) {
      await page.goto(server.url + route);
      await expect(page.getByText(`Questions or concerns: ${injected}`, { exact: true })).toBeVisible();
      await expect(page.locator('[data-participation-notice] img')).toHaveCount(0);
      expect(await page.evaluate(() => window.noticeExecuted)).toBeUndefined();
      await expect(page.locator('body')).not.toContainText("world's permanent chronicle");
    }
  } finally { await server.close(); }
});

test('a changed-notice response reloads the notice and clears its agreement', async ({ page }) => {
  const server = await serveBrowser({ invite: KEY, player: NAME, env: noticeEnv });
  try {
    const counts = countGameplay(page);
    let reads = 0, writes = 0;
    await returning(page);
    await page.route('**/participation', async route => {
      if (route.request().method() === 'GET') {
        // Count participant-state reads; each is preceded by public metadata.
        if (route.request().headers()['x-beta-key']) reads += 1;
        await route.continue();
      } else if (++writes === 1) {
        await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: 'The test-world notice changed. Please read it again.' }) });
      } else await route.continue();
    });
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await accept(page);
    await expect.poll(() => reads).toBe(2);
    await expect(page.getByRole('checkbox', { name: AGREEMENT, exact: true })).not.toBeChecked();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toBeDisabled();
    expect(counts()).toEqual({ worlds: 0, sockets: 0 });
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    expect(writes).toBe(2);
  } finally { await server.close(); }
});

test('a refused invite uses the existing return guidance rather than accepting consent', async ({ page }) => {
  const server = await serveBrowser({ invite: KEY, player: NAME, env: noticeEnv });
  try {
    await page.goto(`${server.url}/app?key=nw_${'0'.repeat(32)}&name=${encodeURIComponent(NAME)}`);
    await expect(page.getByRole('alert')).toContainText('The invitation this browser holds does not open the world.');
    await expect(page.getByRole('checkbox')).toHaveCount(0);
  } finally { await server.close(); }
});

test('ordinary guide and registration retain their standing permanence disclosure', async ({ page }) => {
  const server = await serveBrowser();
  try {
    for (const route of ['/guide', `/register?invite=${TOKEN}`]) {
      await page.goto(server.url + route);
      await expect(page.locator('[data-participation-notice]')).toBeHidden();
      if (route === '/guide') {
        await expect(page.locator('body')).toContainText("world's permanent chronicle");
        await expect(page.getByRole('heading', { name: 'Nothing is lost', exact: true })).toBeVisible();
      } else await expect(page.locator('#register')).toContainText('recorded under it, permanently,');
    }
  } finally { await server.close(); }
});

test('off-mode notice checks do not validate cached position-only credentials', async ({ page }) => {
  const server = await serveBrowser();
  try {
    await page.addInitScript(() => localStorage.setItem('nw_beta_key', 'cross-device-position-only'));
    const noticeRequests = [];
    const errors = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/participation') noticeRequests.push(request.headers());
    });
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(`${server.url}/guide`);
    await expect(page.locator('[data-participation-notice]')).toBeHidden();
    await page.evaluate(() => globalThis.EnfoldedParticipation.ensure());
    expect(await page.evaluate(() => globalThis.EnfoldedParticipation.recheck())).toBeUndefined();
    expect(noticeRequests).toHaveLength(3);
    expect(noticeRequests.every(headers => !headers['x-beta-key'])).toBe(true);
    expect(errors).toEqual([]);
  } finally { await server.close(); }
});

// The pipe is a fixture-only operator, so the browser sees the real notice
// revision, HTTP428 and socket1008 without a production control endpoint.
async function mutableNoticeServer() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-notice-revision-'));
  const child = spawn(process.env.ENFOLDED_PYTHON || 'python', ['-u', '-c', `
from pathlib import Path
import json, os, sys, threading
import persistence
from server import _Handler, _ThreadedServer, guard
from server.websocket import _SWEEP
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
persistence.mint_invite_key(sys.argv[2], sys.argv[3])
guard.WS_SWEEP_INTERVAL_SEC=3600
server=_ThreadedServer(('127.0.0.1',0),_Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
print(server.server_address[1],flush=True)
for command in sys.stdin:
    if command.strip()=='revise':
        os.environ['NESTED_WORLDS_TEST_RETENTION']='Revised fixture retention: remove this world and backups tomorrow.'
    elif command.strip()=='sweep':
        with _SWEEP._cond:
            sessions=list(_SWEEP._sessions)
        for session in sessions:
            _SWEEP._sweep(session)
    print(json.dumps({'ok':True}),flush=True)
`, directory, KEY, NAME], {
    cwd: path.resolve(import.meta.dirname, '../..'),
    env: { ...process.env, NESTED_WORLDS_CANONICAL_SEED: '382', NESTED_WORLDS_DISABLE_AI: '1', NESTED_WORLDS_DISABLE_IMAGES: '1', ...noticeEnv },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let errors = '';
  child.stderr.on('data', chunk => { errors = (errors + chunk).slice(-8000); });
  const reader = createInterface({ input: child.stdout });
  const lines = reader[Symbol.asyncIterator]();
  const read = async () => {
    const { value, done } = await lines.next();
    if (done) throw new Error(errors || 'Notice fixture ended');
    return value;
  };
  const port = Number(await read());
  return {
    url: `http://127.0.0.1:${port}`,
    command: async command => { child.stdin.write(command + '\n'); return JSON.parse(await read()); },
    close: async () => {
      if (child.exitCode === null) { const exited = once(child, 'exit'); child.kill('SIGKILL'); await exited; }
      reader.close(); await rm(directory, { recursive: true, force: true });
    },
  };
}

for (const route of ['/', '/app']) test(`${route}: a live notice revision resumes the current view without replaying refused speech`, async ({ page }) => {
  test.setTimeout(60_000);
  const server = await mutableNoticeServer();
  try {
    await returning(page);
    const counts = countGameplay(page);
    let speaks = 0;
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/speak' && request.method() === 'POST') speaks += 1;
    });
    await page.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect.poll(() => counts().sockets).toBe(1);
    await page.getByLabel('Message to this place', { exact: true }).fill('A line refused by the revised notice');
    await server.command('revise');
    const refused = page.waitForResponse(response => new URL(response.url()).pathname === '/speak');
    await page.getByRole('button', { name: /^Speak to [Nn]ode$/, exact: true }).click();
    expect((await refused).status()).toBe(428);
    await server.command('sweep');
    await expect(page.getByText('Retention and deletion, including backups: Revised fixture retention: remove this world and backups tomorrow.', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toBeDisabled();
    expect(speaks).toBe(1);
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toHaveCount(0);
    await expect.poll(() => counts().sockets).toBe(2);
    expect(speaks).toBe(1);
  } finally { await server.close(); }
});

for (const method of ['click', 'keyboard']) test(`an open native Chronicle survives the ${method} acknowledgement of a changed notice`, async ({ page }) => {
  const server = await mutableNoticeServer();
  try {
    await returning(page);
    const counts = countGameplay(page);
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect.poll(() => counts().sockets).toBe(1);
    await page.getByText('History & journal', { exact: true }).click();
    await page.getByRole('button', { name: 'View full chronicle', exact: true }).click();
    const chronicle = page.getByRole('dialog', { name: 'World Chronicle', exact: true });
    await expect(chronicle).toBeVisible();
    await expect(chronicle).toHaveJSProperty('open', true);
    let navigations = 0;
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) navigations += 1; });
    await server.command('revise');
    await server.command('sweep');
    const gate = page.getByRole('dialog', { name: 'Temporary test world', exact: true });
    await expect(gate).toBeVisible();
    expect(await gate.evaluate(node => node.matches(':modal'))).toBe(true);
    await page.keyboard.press('Escape');
    await expect(gate).toBeVisible();
    await expect(chronicle).toHaveJSProperty('open', true);
    if (method === 'click') await accept(page);
    else {
      await expect(page.getByRole('checkbox', { name: AGREEMENT, exact: true })).toBeFocused();
      await page.keyboard.press('Space');
      await page.keyboard.press('Tab');
      await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toBeFocused();
      await page.keyboard.press('Enter');
    }
    await expect(gate).toHaveCount(0);
    await expect(chronicle).toBeVisible();
    await expect(chronicle).toHaveJSProperty('open', true);
    await expect.poll(() => counts().sockets).toBe(2);
    expect(navigations).toBe(0);
    await chronicle.getByRole('button', { name: 'close', exact: true }).click();
    await expect(chronicle).toHaveCount(0);
  } finally { await server.close(); }
});

async function restartableNoticeServer() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-notice-restart-'));
  let current;
  const stop = async () => {
    if (!current) return;
    const { child, reader } = current;
    if (child.exitCode === null) { const exited = once(child, 'exit'); child.kill('SIGKILL'); await exited; }
    reader.close(); current = null;
  };
  const start = async (port = 0, retention = noticeEnv.NESTED_WORLDS_TEST_RETENTION) => {
    const child = spawn(process.env.ENFOLDED_PYTHON || 'python', ['-u', '-c', `
from pathlib import Path
import sys
import persistence
from server import _Handler, _ThreadedServer
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
if persistence.lookup_invite_key(sys.argv[2]) is None:
    persistence.mint_invite_key(sys.argv[2],sys.argv[3])
server=_ThreadedServer(('127.0.0.1',int(sys.argv[4])),_Handler)
print(server.server_address[1],flush=True)
server.serve_forever()
`, directory, KEY, NAME, String(port)], {
      cwd: path.resolve(import.meta.dirname, '../..'),
      env: { ...process.env, NESTED_WORLDS_CANONICAL_SEED: '382', NESTED_WORLDS_DISABLE_AI: '1', NESTED_WORLDS_DISABLE_IMAGES: '1', ...noticeEnv, NESTED_WORLDS_TEST_RETENTION: retention },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let errors = '';
    child.stderr.on('data', chunk => { errors = (errors + chunk).slice(-8000); });
    const reader = createInterface({ input: child.stdout });
    current = { child, reader };
    const lines = reader[Symbol.asyncIterator]();
    const { value, done } = await lines.next();
    if (done || !Number.isInteger(Number(value))) throw new Error(errors || 'Restart fixture ended');
    return Number(value);
  };
  const port = await start();
  return {
    url: `http://127.0.0.1:${port}`, stop,
    restart: retention => start(port, retention),
    close: async () => { await stop(); await rm(directory, { recursive: true, force: true }); },
  };
}

for (const route of ['/', '/app']) test(`${route}: a process restart with a new notice restores consent before reconnecting`, async ({ page }) => {
  test.setTimeout(60_000);
  const server = await restartableNoticeServer();
  try {
    await returning(page);
    await page.addInitScript(() => {
      window.__noticeSocketCloses = [];
      const NativeSocket = window.WebSocket;
      window.WebSocket = class extends NativeSocket {
        constructor(...args) {
          super(...args);
          this.addEventListener('close', event => window.__noticeSocketCloses.push(event.code));
        }
      };
    });
    const counts = countGameplay(page);
    await page.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}`);
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect.poll(() => counts().sockets).toBe(1);
    await server.stop();
    await expect.poll(() => page.evaluate(() => window.__noticeSocketCloses.length)).toBeGreaterThan(0);
    const closes = await page.evaluate(() => window.__noticeSocketCloses);
    expect(closes.some(code => code === 1006 || code === 1001)).toBe(true);
    // The current notice is temporarily unreachable. An ongoing network
    // interruption keeps normal reconnect backoff instead of opening a gate.
    await expect(page.getByRole('button', { name: 'Load the notice again', exact: true })).toHaveCount(0);
    await server.restart('Restarted fixture retention: remove the temporary world and backups next week.');
    const oldAcceptance = await page.request.get(`${server.url}/world`, { headers: { 'X-Beta-Key': KEY } });
    expect(oldAcceptance.status()).toBe(428);
    await expect(page.getByText('Retention and deletion, including backups: Restarted fixture retention: remove the temporary world and backups next week.', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toBeDisabled();
    await accept(page);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Agree and continue', exact: true })).toHaveCount(0);
    const currentAcceptance = await page.request.get(`${server.url}/world`, { headers: { 'X-Beta-Key': KEY } });
    expect(currentAcceptance.status()).toBe(200);
  } finally { await server.close(); }
});

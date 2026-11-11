import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const KEY = 'nw_' + '6'.repeat(32);
const AGREEMENT = 'I confirm I am at least 18 years old, have read this notice and agree to participate in this temporary test world.';
// Disposable fixture values, not an adopted participant policy.
const fixtureNotice = {
  NESTED_WORLDS_TEST_WORLD: '1', NESTED_WORLDS_TEST_CONTACT: 'Page fixture facilitator',
  NESTED_WORLDS_TEST_RETENTION: 'Fixture world and backups are removed at teardown.',
  NESTED_WORLDS_TEST_MIN_AGE: '18', NESTED_WORLDS_TEST_DATA_USE: 'No fixture data reaches a model provider.',
};

async function servePages(testWorld = true) {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-notice-pages-'));
  const child = spawn(process.env.ENFOLDED_PYTHON || 'python', ['-u', '-c', `
from pathlib import Path
import json, os, sys, threading
import persistence
from server import _Handler, _ThreadedServer
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
persistence.mint_invite_key(sys.argv[2], 'Page traveler')
server=_ThreadedServer(('127.0.0.1',0),_Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
print(server.server_address[1],flush=True)
for command in sys.stdin:
    if command.strip()=='revise':
        os.environ['NESTED_WORLDS_TEST_RETENTION']='Changed page-fixture retention: remove world and backups tomorrow.'
    print(json.dumps({'ok':True}),flush=True)
`, directory, KEY], {
    cwd: path.resolve(import.meta.dirname, '../..'),
    env: { ...process.env, NESTED_WORLDS_CANONICAL_SEED: '382', NESTED_WORLDS_DISABLE_AI: '1', NESTED_WORLDS_DISABLE_IMAGES: '1', ...fixtureNotice, NESTED_WORLDS_TEST_WORLD: testWorld ? '1' : '0' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let errors = '';
  child.stderr.on('data', chunk => { errors = (errors + chunk).slice(-8000); });
  const reader = createInterface({ input: child.stdout });
  const lines = reader[Symbol.asyncIterator]();
  const read = async () => {
    const { value, done } = await lines.next();
    if (done) throw new Error(errors || 'Page fixture ended');
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

async function holdKey(page) {
  await page.addInitScript(key => localStorage.setItem('nw_beta_key', key), KEY);
}

async function agree(page) {
  const button = page.getByRole('button', { name: 'Agree and continue', exact: true });
  await expect(button).toBeDisabled();
  await page.getByRole('checkbox', { name: AGREEMENT, exact: true }).check();
  await button.click();
}

for (const route of ['/journal', '/ideas']) test(`${route}: direct entry reads no page data until the current notice is acknowledged`, async ({ page }) => {
  const server = await servePages();
  try {
    await holdKey(page);
    let apiReads = 0;
    page.on('request', request => {
      if (new URL(request.url()).pathname === (route === '/journal' ? '/journal/data' : '/ideas/search')) apiReads += 1;
    });
    await page.goto(server.url + route);
    await expect(page.getByRole('heading', { name: 'Temporary test world', exact: true })).toBeVisible();
    expect(apiReads).toBe(0);
    await agree(page);
    await expect(page.locator(route === '/journal' ? '#journal' : '#board')).toBeVisible();
    expect(apiReads).toBeGreaterThan(0);
  } finally { await server.close(); }
});

test('journal: a changed notice leaves a refused note draft in place and never saves it automatically', async ({ page }) => {
  const server = await servePages();
  try {
    await holdKey(page);
    await page.goto(server.url + '/journal');
    await agree(page);
    await expect(page.locator('#journal')).toBeVisible();
    const world = await (await page.request.get(server.url + '/world?depth=1', { headers: { 'X-Beta-Key': KEY } })).json();
    await page.getByLabel('Place', { exact: true }).fill(world.world.name);
    await page.getByLabel('Question or observation', { exact: true }).fill('Keep this private question until I choose to save it.');
    let writes = 0;
    page.on('request', request => { if (new URL(request.url()).pathname === '/journal/note' && request.method() === 'POST') writes += 1; });
    await server.command('revise');
    await page.getByRole('button', { name: 'Save private note', exact: true }).click();
    await expect(page.getByText('Retention and deletion, including backups: Changed page-fixture retention: remove world and backups tomorrow.', { exact: true })).toBeVisible();
    await agree(page);
    await expect(page.locator('#status')).toContainText('Your previous change was not saved');
    await expect(page.getByLabel('Question or observation', { exact: true })).toHaveValue('Keep this private question until I choose to save it.');
    expect(writes).toBe(1);
    const beforeRetry = await (await page.request.get(server.url + '/journal/data', { headers: { 'X-Beta-Key': KEY } })).json();
    expect(beforeRetry.notes).toHaveLength(0);
    await page.getByRole('button', { name: 'Save private note', exact: true }).click();
    await expect(page.locator('#status')).toHaveText('Private note saved.');
    expect(writes).toBe(2);
  } finally { await server.close(); }
});

test('Ideas: a changed notice makes a refused submission editable and waits for another explicit submit', async ({ page }) => {
  const server = await servePages();
  try {
    await holdKey(page);
    await page.goto(server.url + '/ideas');
    await agree(page);
    await expect(page.locator('#board')).toBeVisible();
    await page.getByLabel('Title', { exact: true }).fill('Show passage names');
    await page.getByLabel('Your experience and desired outcome', { exact: true }).fill('Show the name of each passage before I choose it.');
    await expect(page.locator('#related')).toContainText('No related titles found.');
    let writes = 0;
    page.on('request', request => { if (new URL(request.url()).pathname === '/ideas/submit' && request.method() === 'POST') writes += 1; });
    await server.command('revise');
    await page.getByRole('button', { name: 'Submit idea', exact: true }).click();
    await expect(page.getByText('Retention and deletion, including backups: Changed page-fixture retention: remove world and backups tomorrow.', { exact: true })).toBeVisible();
    await agree(page);
    await expect(page.locator('#message')).toContainText('Your previous request was not sent');
    await expect(page.getByLabel('Title', { exact: true })).toBeEnabled();
    await expect(page.getByLabel('Title', { exact: true })).toHaveValue('Show passage names');
    expect(writes).toBe(1);
    const beforeRetry = await (await page.request.get(server.url + '/ideas/list', { headers: { 'X-Beta-Key': KEY } })).json();
    expect(beforeRetry.ideas).toHaveLength(0);
    await page.getByRole('button', { name: 'Submit idea', exact: true }).click();
    await expect(page.locator('#message')).toContainText('Idea submitted.');
    expect(writes).toBe(2);
  } finally { await server.close(); }
});

for (const route of ['/journal', '/ideas']) {
  for (const failure of ['429', '502', 'network']) test(`${route}: ordinary entry survives an unknown notice ${failure}`, async ({ page }) => {
    const server = await servePages(false);
    try {
      await holdKey(page);
      await page.route('**/participation', intercepted => failure === 'network' ? intercepted.abort() : intercepted.fulfill({ status: Number(failure), contentType: 'text/plain', body: 'Notice unavailable' }), { times: 1 });
      await page.goto(server.url + route);
      await expect(page.locator(route === '/journal' ? '#journal' : '#board')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Load the notice again', exact: true })).toHaveCount(0);
    } finally { await server.close(); }
  });
  test(`${route}: a protected first read recovers consent after unknown metadata fails`, async ({ page }) => {
    const server = await servePages();
    try {
      await holdKey(page);
      await page.route('**/participation', intercepted => intercepted.fulfill({ status: 502, contentType: 'text/plain', body: 'Notice unavailable' }), { times: 1 });
      await page.goto(server.url + route);
      await expect(page.getByRole('heading', { name: 'Temporary test world', exact: true })).toBeVisible();
      await agree(page);
      await page.getByRole('button', { name: route === '/journal' ? 'Load this page again' : 'Retry loading Ideas', exact: true }).click();
      await expect(page.locator(route === '/journal' ? '#journal' : '#board')).toBeVisible();
    } finally { await server.close(); }
  });
}

import {expect, test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {promisify} from 'node:util';
import {disclose} from './disclosures.js';
import {serveBrowser} from './server.js';

const execute = promisify(execFile);
const repo = path.resolve(import.meta.dirname, '../..');
const adaKey = 'nw_' + 'a'.repeat(32);
const beaKey = 'nw_' + 'b'.repeat(32);
const registration = 'nwr_' + 'c'.repeat(32);
const region = 'Emberlit Orchard Terraces-111111';
const gallery = 'Broken Ember Gallery-1111111';
const instrument = 'Elder River Instrument-11111111';

// Exercise the actual operator URL helper and registration endpoint on a born
// world, without installing a scripted situation or opening an operator DB.
async function pilot() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-pilot-journey-'));
  const database = path.join(directory, 'worlds.db');
  let server;
  try {
    const {stdout} = await execute(process.env.ENFOLDED_PYTHON || 'python', ['-c', `
import json, sys
from pathlib import Path
import persistence
persistence._DB_PATH = Path(sys.argv[1])
from multiverse import store
store.ensure_born(382)
persistence.mint_invite_key('nw_' + 'a' * 32, 'Ada')
persistence.mint_invite_key('nw_' + 'b' * 32, 'Bea')
persistence.create_registration_token('nwr_' + 'c' * 32)
from main import invite_share_url
print(json.dumps({
    'ada': invite_share_url('nw_' + 'a' * 32, 'Ada', base=''),
    'bea': invite_share_url('nw_' + 'b' * 32, 'Bea', base=''),
}))
`, database], {cwd: repo});
    const invites = JSON.parse(stdout);
    server = await serveBrowser({database, pump: true,
      env: {NESTED_WORLDS_MATURATION_SCALE: '0'}});
    return {...server, invites, async close() {
      await server.close();
      await rm(directory, {recursive: true, force: true});
    }};
  } catch (error) {
    await server?.close();
    await rm(directory, {recursive: true, force: true});
    throw error;
  }
}

async function identity(page, name, key) {
  expect(await page.evaluate(() => localStorage.getItem('nw_player_name'))).toBe(name);
  expect(await page.evaluate(() => localStorage.getItem('nw_beta_key'))).toBe(key);
  const url = new URL(page.url());
  expect(url.pathname).toBe('/app');
  expect(url.searchParams.has('key')).toBe(false);
  expect(url.searchParams.has('name')).toBe(false);
  await expect(page.getByPlaceholder('Your name', {exact: true})).toHaveCount(0);
  const me = await (await page.request.get(new URL('/me', page.url()).href,
    {headers: {'X-Beta-Key': key}})).json();
  expect(me.participant.name).toBe(name);
  return me;
}

async function attempt(page, label) {
  await page.getByRole('button', {name: 'Act', exact: true}).click();
  const composer = page.locator('enfolded-interventions');
  const [response] = await Promise.all([
    page.waitForResponse(reply => new URL(reply.url()).pathname === '/interventions/commit'),
    composer.getByRole('button', {name: label, exact: true}).click(),
  ]);
  const result = await response.json();
  expect(result.accepted).toBe(true);
  await expect(composer.getByRole('status')).toContainText(label);
  return result;
}

function watchSockets(page) {
  const open = new Set();
  const welcomes = [];
  page.on('websocket', socket => {
    open.add(socket);
    socket.on('close', () => open.delete(socket));
    socket.on('framereceived', ({payload}) => {
      const message = JSON.parse(String(payload));
      if (message.type === 'welcome') welcomes.push(message);
    });
  });
  return {open, welcomes};
}

async function arrived(page, sockets, previous = 0) {
  await expect(page.locator('#node-name')).toBeVisible();
  // A mounted scene is not proof that its server-side presence has arrived.
  await expect.poll(() => sockets.welcomes.length).toBeGreaterThan(previous);
  await expect.poll(() => sockets.open.size).toBe(1);
  const scenes = page.context().pages().filter(candidate =>
    new URL(candidate.url()).pathname === '/app');
  expect(scenes).toHaveLength(1);
  expect(scenes[0]).toBe(page);
  expect(page.context().pages()).toHaveLength(1);
  return sockets.welcomes.at(-1);
}

async function openJournal(page) {
  await disclose(page, 'History & journal');
  await page.getByRole('link', {name: 'Journal', exact: true}).click();
  await expect(page).toHaveURL(url => url.pathname === '/journal');
  await expect(page.getByRole('status')).toHaveText('Your journal is private.');
}

test('self-service entry and auxiliary-page returns keep the registered pilot identity', async ({page}) => {
  const server = await pilot();
  const errors = [];
  const sockets = watchSockets(page);
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(server.url + '/register?invite=' + registration);
    await page.getByLabel('Your name', {exact: true}).fill('Clara');
    await page.getByRole('button', {name: 'Enter the worlds', exact: true}).click();
    await page.waitForURL(url => url.pathname === '/app');
    await page.getByRole('button', {name: 'Begin', exact: true}).click();
    await arrived(page, sockets);
    const key = await page.evaluate(() => localStorage.getItem('nw_beta_key'));
    expect(key).toMatch(/^nw_[0-9a-f]{32}$/);
    const first = await identity(page, 'Clara', key);
    const place = await page.locator('#node-name').getAttribute('title');

    await disclose(page, 'Sound & help');
    await page.getByRole('link', {name: "Player's Guide ↗", exact: true}).click();
    await page.getByRole('link', {name: /back to (the )?world/i}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', place);
    await arrived(page, sockets);
    expect((await identity(page, 'Clara', key)).participant).toEqual(first.participant);

    await openJournal(page);
    await page.getByRole('link', {name: 'Back to world', exact: true}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', place);
    await arrived(page, sockets);
    await disclose(page, 'Sound & help');
    await page.getByRole('link', {name: 'Ideas', exact: true}).click();
    await expect(page).toHaveURL(url => url.pathname === '/ideas');
    await page.getByRole('link', {name: 'Enfolded — back to world', exact: true}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', place);
    await arrived(page, sockets);
    await page.reload();
    await expect(page.locator('#node-name')).toHaveAttribute('title', place);
    expect((await identity(page, 'Clara', key)).participant).toEqual(first.participant);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: path.join(tmpdir(), 'enfolded-pilot-registration-mobile.png'), fullPage: true});
    expect(errors).toEqual([]);
  } finally {
    await server.close();
  }
});

test('an invited traveler explores, acts and returns through a private journal to another traveler’s change', async ({page, browser}) => {
  // This exercises repeated real page loads and two independently connected
  // travelers, including a fresh server roster after every return.
  test.setTimeout(60_000);
  const server = await pilot();
  const errors = [];
  const sockets = watchSockets(page);
  page.on('pageerror', error => errors.push(error.message));
  let otherContext;
  try {
    await page.setViewportSize({width: 390, height: 844});
    // A graphics failure must leave this entire journey operable. The fixture
    // also disables generated images, so this cannot depend on model artwork.
    await page.context().addInitScript(() => {HTMLCanvasElement.prototype.getContext = () => null;});
    await page.goto(server.url + server.invites.ada + '&node=' + encodeURIComponent(region));
    await page.getByRole('button', {name: 'Begin', exact: true}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', region);
    await arrived(page, sockets);
    await expect(page.getByText('The view is quiet. The passages remain open to exploration.')).toBeVisible();
    const first = await identity(page, 'Ada', adaKey);
    for (const destination of [gallery, instrument]) {
      await page.locator('enfolded-navigation').locator(`button[data-target="${destination}"]`).focus();
      await page.keyboard.press('Enter');
      await expect(page.locator('#node-name')).toHaveAttribute('title', destination);
    }
    await attempt(page, 'Engrave');
    await disclose(page, 'Conditions here');
    await expect(page.getByText('engraved', {exact: true})).toBeVisible();

    await openJournal(page);
    await page.getByLabel('Question or observation').fill('A private question about the instrument.');
    await page.getByRole('button', {name: 'Save private note', exact: true}).click();
    await expect(page.locator('#notes')).toContainText('A private question about the instrument.');
    await page.getByRole('button', {name: 'Make this my home bookmark', exact: true}).click();
    const home = page.locator('#home-label').getByRole('link');
    await expect(home).toHaveText('Elder River Instrument');
    await expect(home).toHaveAttribute('href', '/app?node=' + encodeURIComponent(instrument));
    await home.click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', instrument);
    await arrived(page, sockets);
    expect((await identity(page, 'Ada', adaKey)).participant).toEqual(first.participant);

    otherContext = await browser.newContext();
    const other = await otherContext.newPage();
    const otherSockets = watchSockets(other);
    await other.goto(server.url + server.invites.bea + '&node=' + encodeURIComponent(instrument));
    await other.getByRole('button', {name: 'Begin', exact: true}).click();
    await expect(other.locator('#node-name')).toHaveAttribute('title', instrument);
    let welcome = await arrived(other, otherSockets);
    expect(welcome.players.filter(player => player.name === 'Ada')).toHaveLength(1);
    await identity(other, 'Bea', beaKey);

    // Use the actual outgoing links repeatedly. A popup would leave the old
    // scene live, and returning from it would create another Ada presence.
    for (const destination of ['Journal', 'Ideas', 'Journal', 'Ideas']) {
      const previous = sockets.welcomes.length;
      if (destination === 'Journal') {
        await openJournal(page);
        await page.getByRole('link', {name: 'Back to world', exact: true}).click();
      } else {
        await disclose(page, 'Sound & help');
        await page.getByRole('link', {name: 'Ideas', exact: true}).click();
        await expect(page).toHaveURL(url => url.pathname === '/ideas');
        await page.getByRole('link', {name: 'Enfolded — back to world', exact: true}).click();
      }
      await arrived(page, sockets, previous);
      await expect(page.locator('#node-name')).toHaveAttribute('title', instrument);
      const otherPrevious = otherSockets.welcomes.length;
      await other.reload();
      welcome = await arrived(other, otherSockets, otherPrevious);
      expect(welcome.players.filter(player => player.name === 'Ada')).toHaveLength(1);
    }

    // Leaving the scene through its own journal link is enough to leave the
    // world. Do not hide an extra live tab with an about:blank navigation.
    await openJournal(page);
    await expect.poll(() => sockets.open.size).toBe(0);
    const polished = await attempt(other, 'Polish');
    await disclose(other, 'Conditions here');
    await expect(other.getByText('mirror smooth', {exact: true})).toBeVisible();
    await openJournal(other);
    await expect(other.locator('#notes')).not.toContainText('A private question about the instrument.');
    await expect(other.locator('#home-label').getByRole('link')).toHaveCount(0);

    await page.reload();
    await expect(page.locator('#notes')).toContainText('A private question about the instrument.');
    // The recap cites the recorded source action; it need not repeat the
    // performer's name in the authored outcome line.
    const change = page.locator('#recap p').filter({hasText: `Source action #${polished.event_id}.`}).filter({hasText: 'Polish'}).first();
    await expect(change).toBeVisible();
    await page.screenshot({path: path.join(tmpdir(), 'enfolded-pilot-return-journal.png'), fullPage: true});
    await change.getByRole('link', {name: /^Recorded event #/}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', instrument);
    await arrived(page, sockets);
    await disclose(page, 'Conditions here');
    await expect(page.getByText('mirror smooth', {exact: true})).toBeVisible();
    expect((await identity(page, 'Ada', adaKey)).participant).toEqual(first.participant);
    await page.reload();
    await expect(page.locator('#node-name')).toHaveAttribute('title', instrument);
    await expect(page.getByPlaceholder('Your name', {exact: true})).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: path.join(tmpdir(), 'enfolded-pilot-mobile-fallback.png'), fullPage: true});
    expect(errors).toEqual([]);
  } finally {
    await otherContext?.close();
    await server.close();
  }
});

test('a legacy map invitation returns through the journal to the scene without another name prompt', async ({page}) => {
  const server = await pilot();
  const sockets = watchSockets(page);
  try {
    await page.goto(server.url + server.invites.ada.replace(/^\/app/, '/'));
    await page.locator('#btn-begin').click();
    await expect(page.locator('#graph svg')).toBeVisible();
    await expect(page.locator('#node-name')).toHaveAttribute('title', /.+-\d+$/);
    await expect.poll(() => sockets.welcomes.length).toBeGreaterThan(0);
    const place = await page.locator('#node-name').getAttribute('title');
    const previous = sockets.welcomes.length;
    await openJournal(page);
    await page.getByRole('link', {name: 'Back to world', exact: true}).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', place);
    await arrived(page, sockets, previous);
    await identity(page, 'Ada', adaKey);
  } finally {
    await server.close();
  }
});

test('the home bookmark renders a stored place name as text and encodes its scene link', async ({page}) => {
  const server = await pilot();
  const unsafeNode = '<img src=x onerror="window.__homeInjected=true">-11111111';
  try {
    await page.goto(server.url + server.invites.ada);
    await page.getByRole('button', {name: 'Begin', exact: true}).click();
    await expect(page.locator('#node-name')).toBeVisible();
    // Preserve the authenticated production response and replace only the
    // display name to exercise characters unavailable in the current births.
    await page.route('**/journal/data?*', async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.profile.home = {seed: 382, node: unsafeNode};
      await route.fulfill({response, json: data});
    });
    await openJournal(page);
    const home = page.locator('#home-label').getByRole('link');
    await expect(home).toHaveText('<img src=x onerror="window.__homeInjected=true">');
    await expect(home).toHaveAttribute('href', '/app?node=' + encodeURIComponent(unsafeNode));
    await expect(page.locator('#home-label img')).toHaveCount(0);
    expect(await page.evaluate(() => window.__homeInjected)).toBeUndefined();
  } finally {
    await server.close();
  }
});

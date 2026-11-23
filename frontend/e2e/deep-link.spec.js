// A place named without its address is found by one read of /node. When
// that read fails for a while, the place stays the destination: the link
// stays in the address bar, no other place is saved in its stead, and the
// player arrives there once the read answers.
import { expect, test } from '@playwright/test';
import { serveBrowser } from './server.js';
import { failFirstNotice } from './notice-fixture.js';
import { acknowledgeCurrentStudy } from './study-fixture.js';

const KEY = 'nw_' + '7'.repeat(32);
const NAME = 'Deep traveler';
const DEEP = 'Cedar Anchor Quark';        // eleven scales down, at 11111111111
const DEEP_ADDRESS = '11111111111';
const AGREEMENT = 'I have read this notice and agree to participate in this temporary test world.';
const AGE = 'I confirm I am 18 years old or older.';
const noticeEnv = {
  NESTED_WORLDS_TEST_WORLD: '1',
  NESTED_WORLDS_TEST_CONTACT: 'Fixture facilitator',
  NESTED_WORLDS_TEST_RETENTION: 'Fixture world and backups removed at fixture teardown.',
  NESTED_WORLDS_TEST_MIN_AGE: '18',
  NESTED_WORLDS_TEST_DATA_USE: 'No model provider receives fixture data.',
};

async function returning(page) {
  await page.addInitScript(() => {
    localStorage.setItem('nw_seen_intro', '1');
    localStorage.setItem('nw_sound_preference', 'off');
  });
}

// Every position this page asks the server to keep.
function savedPositions(page) {
  const saved = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/position' && request.method() === 'POST') {
      saved.push(request.postDataJSON()?.node);
    }
  });
  return saved;
}

// Refuse reads of /node until told otherwise; count the refusals.
async function holdAddress(page, status) {
  const held = { refused: 0, open: false };
  await page.route('**/node?*', async route => {
    if (held.open) return route.continue();
    held.refused += 1;
    if (status === 'network') return route.abort('connectionreset');
    return route.fulfill({ status, contentType: 'application/json',
      body: JSON.stringify({ error: 'the world is restarting' }) });
  });
  return held;
}

async function serverPosition(page, server) {
  const response = await page.request.get(server.url + '/position', { headers: { 'X-Beta-Key': KEY } });
  return (await response.json()).position;
}

for (const failure of [503, 'network']) {
  test(`/app: a name-only deep link stays pending through a ${failure} and arrives when the address answers`, async ({ page }) => {
    const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME });
    try {
      await acknowledgeCurrentStudy(server.url, KEY);
      await returning(page);
      const saved = savedPositions(page);
      const held = await holdAddress(page, failure);
      await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}&node=${encodeURIComponent(DEEP)}`);
      const retry = page.getByRole('button', { name: 'Open the view again', exact: true });
      await expect(retry).toBeVisible();
      expect(held.refused).toBeGreaterThan(0);
      // No place was shown in its stead, the link is whole, nothing was saved.
      await expect(page.locator('#node-name')).toHaveCount(0);
      expect(new URL(page.url()).searchParams.get('node')).toBe(DEEP);
      expect(saved).toEqual([]);
      expect(await serverPosition(page, server)).toBeNull();
      expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBeNull();

      held.open = true;
      await retry.click();
      await expect(page.locator('#node-name')).toHaveAttribute('title', DEEP);
      await expect(page.locator('#node-address')).toContainText(DEEP_ADDRESS);
      await expect.poll(() => new URL(page.url()).searchParams.has('node')).toBe(false);
      await expect.poll(async () => (await serverPosition(page, server))?.node).toBe(DEEP);
      expect(saved.every(node => node === DEEP)).toBe(true);
    } finally { await page.unrouteAll({ behavior: 'wait' }).catch(() => {}); await server.close(); }
  });
}

test('/app: a name-only deep link survives one failed read without a click', async ({ page }) => {
  const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME });
  try {
    await acknowledgeCurrentStudy(server.url, KEY);
    await returning(page);
    const saved = savedPositions(page);
    let refused = 0;
    await page.route('**/node?*', async route => {
      if (refused++) return route.continue();
      return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"restarting"}' });
    });
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}&node=${encodeURIComponent(DEEP)}`);
    await expect(page.locator('#node-name')).toHaveAttribute('title', DEEP);
    expect(refused).toBeGreaterThan(1);
    expect(saved.every(node => node === DEEP)).toBe(true);
  } finally { await page.unrouteAll({ behavior: 'wait' }).catch(() => {}); await server.close(); }
});

test('/app: a link to a place this world does not hold still opens the world', async ({ page }) => {
  const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME });
  try {
    await acknowledgeCurrentStudy(server.url, KEY);
    await returning(page);
    await page.goto(`${server.url}/app?key=${KEY}&name=${encodeURIComponent(NAME)}&node=${encodeURIComponent('No Such Place')}`);
    await expect(page.locator('#node-name')).toBeVisible();
    await expect.poll(() => new URL(page.url()).searchParams.has('node')).toBe(false);
  } finally { await server.close(); }
});

// The map keeps no link of its own; its name-only destination is a position
// this browser saved before it kept addresses.
async function savedByNameAlone(page) {
  await page.addInitScript(([name, deep]) => {
    localStorage.setItem('nw_player_name', name);
    if (!sessionStorage.getItem('seeded')) {
      sessionStorage.setItem('seeded', '1');
      localStorage.setItem('nw_last_node', deep);
      localStorage.removeItem('nw_last_address');
    }
  }, [NAME, DEEP]);
}

for (const route of ['/app', '/map']) test(`${route}: a name-only destination held by the participation notice is reached after acknowledgement`, async ({ page }) => {
  const server = await serveBrowser({ preseed: 382, invite: KEY, player: NAME, env: noticeEnv });
  try {
    await returning(page);
    const saved = savedPositions(page);
    // The notice cannot be read at first, so the first gameplay reads meet
    // the server's own 428.
    await failFirstNotice(page, route => route.fulfill({ status: 502, contentType: 'text/html', body: 'unavailable' }));
    const refusals = [];
    page.on('response', response => {
      if (response.status() === 428) refusals.push(new URL(response.url()).pathname);
    });
    const link = route === '/app' ? `&node=${encodeURIComponent(DEEP)}` : '';
    if (route === '/map') await savedByNameAlone(page);
    await page.goto(`${server.url}${route}?key=${KEY}&name=${encodeURIComponent(NAME)}${link}`);
    await expect(page.getByRole('heading', { name: 'Temporary test world' })).toBeVisible();
    expect(refusals).toContain('/node');
    if (route === '/app') expect(new URL(page.url()).searchParams.get('node')).toBe(DEEP);
    else expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBe(DEEP);
    expect(saved).toEqual([]);
    await page.getByRole('checkbox', { name: AGE, exact: true }).check();
    await page.getByRole('checkbox', { name: AGREEMENT, exact: true }).check();
    await page.getByRole('button', { name: 'Agree and continue', exact: true }).click();
    await expect(page.locator('#node-name')).toHaveAttribute('title', DEEP);
    await expect.poll(async () => (await serverPosition(page, server))?.node).toBe(DEEP);
    expect(saved.every(node => node === DEEP)).toBe(true);
  } finally { await page.unrouteAll({ behavior: 'wait' }).catch(() => {}); await server.close(); }
});

for (const route of ['/map', '/app']) {
  test(`${route}: a position saved by name alone is not replaced while its address cannot be read`, async ({ page }) => {
    const server = await serveBrowser({ preseed: 382 });
    try {
      await returning(page);
      await savedByNameAlone(page);
      const held = await holdAddress(page, 503);
      await page.goto(server.url + route);
      await expect(page.getByText('The world could not be reached.', { exact: false }).first()).toBeVisible();
      expect(held.refused).toBeGreaterThan(0);
      expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBe(DEEP);
      expect(await page.evaluate(() => document.getElementById('node-name')?.getAttribute('title') || '')).toBe('');

      held.open = true;
      if (route === '/map') {
        // The map's own way to open the view again.
        await page.locator('summary', { hasText: 'Sound & help' }).click();
        await page.click('#btn-advanced');
        await page.locator('#gen-btn').click();
      } else {
        await page.getByRole('button', { name: 'Open the view again', exact: true }).click();
      }
      await expect(page.locator('#node-name')).toHaveAttribute('title', DEEP);
      expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBe(DEEP);
      expect(await page.evaluate(() => localStorage.getItem('nw_last_address'))).toBe(`${DEEP_ADDRESS} ${DEEP}`);
    } finally { await page.unrouteAll({ behavior: 'wait' }).catch(() => {}); await server.close(); }
  });
}

test('/map: a jump to a place whose address cannot be read selects no other place', async ({ page }) => {
  const server = await serveBrowser({ preseed: 382 });
  try {
    await returning(page);
    await page.addInitScript(name => localStorage.setItem('nw_player_name', name), NAME);
    await page.goto(server.url + '/map');
    await expect(page.locator('#node-name')).toHaveAttribute('title', /.+/);
    const before = await page.locator('#node-name').getAttribute('title');
    const held = await holdAddress(page, 503);
    await page.evaluate(deep => jumpTo(deep), DEEP);
    await expect(page.locator('#event-feed')).toContainText('could not be found just now');
    expect(held.refused).toBeGreaterThan(0);
    await expect(page.locator('#node-name')).toHaveAttribute('title', before);
    held.open = true;
    await page.evaluate(deep => jumpTo(deep), DEEP);
    await expect(page.locator('#node-name')).toHaveAttribute('title', DEEP);
    expect(before).not.toBe(DEEP);
  } finally { await page.unrouteAll({ behavior: 'wait' }).catch(() => {}); await server.close(); }
});

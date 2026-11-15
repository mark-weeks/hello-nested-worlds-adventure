// Both real clients, real authenticated sockets and private report endpoints.
// Synthetic frames/refusals below exercise UI recovery, not evidence validation.
import {expect, test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {promisify} from 'node:util';
import {serveBrowser} from './server.js';
import {disclose} from './disclosures.js';

const execute = promisify(execFile);
const repo = path.resolve(import.meta.dirname, '../..');
const adaKey = 'nw_' + 'a'.repeat(32), beaKey = 'nw_' + 'b'.repeat(32);

async function fixture(env = {}) {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-reporting-'));
  const database = path.join(directory, 'worlds.db');
  let server;
  try {
    await execute(process.env.ENFOLDED_PYTHON || 'python', ['-c', `
from pathlib import Path
import sys, persistence
persistence._DB_PATH=Path(sys.argv[1])
persistence.mint_invite_key(sys.argv[2], 'Ada')
persistence.mint_invite_key(sys.argv[3], 'Bea')
from multiverse import store
store.ensure_born(382)
`, database, adaKey, beaKey], {cwd: repo});
    server = await serveBrowser({database, env});
    return {...server, async restart() {
      const port = Number(new URL(server.url).port);
      await server.close();
      server = await serveBrowser({database, env, port});
    }, async close() { await server.close(); await rm(directory, {recursive: true, force: true}); }};
  } catch (error) {
    await server?.close(); await rm(directory, {recursive: true, force: true}); throw error;
  }
}

async function enter(page, server, route, key = adaKey, name = 'Ada') {
  // Participation has its own browser journeys. Reporting fixtures explicitly
  // acknowledge the current notice and age requirement before opening a client.
  const headers = {'X-Beta-Key': key};
  const notice = await (await page.request.get(server.url + '/participation', {headers})).json();
  if (notice.required && !notice.accepted) {
    const accepted = await page.request.post(server.url + '/participation', {headers,
      data: {accepted: true, age_confirmed: true, revision: notice.revision}});
    expect(accepted.ok()).toBe(true);
  }
  let welcome;
  const ready = new Promise(resolve => { welcome = resolve; });
  const relay = {send: null, welcomes: [], frames: []};
  await page.routeWebSocket(/\/ws\?/, socket => {
    relay.send = message => socket.send(JSON.stringify(message));
    const upstream = socket.connectToServer();
    upstream.onMessage(message => {
      socket.send(message);
      const parsed = JSON.parse(message);
      relay.frames.push(parsed);
      if (parsed.type === 'welcome') { relay.welcomes.push(parsed); welcome(); }
    });
  });
  await page.addInitScript(({key, name}) => {
    localStorage.setItem('nw_beta_key', key); localStorage.setItem('nw_player_name', name);
    localStorage.setItem('nw_seen_intro', '1'); localStorage.setItem('nw_sound_preference', 'off');
  }, {key, name});
  await page.goto(server.url + route);
  await ready;
  await disclose(page, 'Travelers & chat');
  return relay;
}

async function twoTravelers(browser, server, route) {
  const context = await browser.newContext();
  const other = await browser.newContext();
  const page = await context.newPage(), bea = await other.newPage();
  const relay = await enter(page, server, route);
  await enter(bea, server, '/', beaKey, 'Bea');
  await expect(page.getByRole('button', {name: 'Report Bea', exact: true})).toBeVisible();
  return {page, bea, relay, async close() { await context.close(); await other.close(); }};
}

const reportDialog = page => page.getByRole('dialog', {name: 'Report a concern', exact: true});
async function fill(dialog, detail = 'Private fixture concern.') {
  await dialog.getByLabel('Reason', {exact: true}).selectOption('harassment');
  await dialog.getByLabel('Details (optional)', {exact: true}).fill(detail);
}

async function expectChatDescription(page, paused = false) {
  const input = page.getByLabel('Message to travelers');
  const notice = await page.locator('#chat-recording-notice').textContent();
  const availability = page.locator('#chat-availability');
  await expect(input).toHaveAttribute('aria-describedby',
    (paused ? 'chat-availability ' : '') + 'chat-recording-notice');
  await expect(input).toHaveAccessibleDescription(
    (paused ? 'Traveler chat is currently unavailable. ' : '') + notice);
  if (paused) await expect(availability).toBeVisible();
  else await expect(availability).toBeHidden();
}

for (const route of ['/', '/app']) {
  test(`${route}: roster and chat reports use private server receipts and opaque evidence`, async ({browser}) => {
    const server = await fixture();
    let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, bea} = people, bodies = [], replies = [];
      await expect(page.getByLabel('Message to travelers')).toBeEnabled();
      await expectChatDescription(page);
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        const response = await intercepted.fetch(); replies.push(await response.json());
        await intercepted.fulfill({response});
      });
      const place = await page.locator('#node-name').getAttribute('title');
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page));
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies[0]).toEqual({request_id: expect.any(String), participant: expect.stringMatching(/^[a-f0-9]{32}$/),
        evidence_ref: null, reason: 'harassment', detail: 'Private fixture concern.'});
      expect(replies[0]).toEqual({report_id: expect.any(String), status: 'received'});
      await reportDialog(page).getByRole('button', {name: 'Close', exact: true}).click();
      await expect(page.locator('#node-name')).toHaveAttribute('title', place);

      await expect(bea.getByLabel('Message to travelers')).toBeEnabled();
      await bea.getByLabel('Message to travelers').fill('A fixture line to cite.');
      await bea.getByRole('button', {name: 'Send', exact: true}).click();
      await disclose(page, 'History & journal');
      const feed = page.getByLabel('Recent events');
      await expect(feed).toContainText('A fixture line to cite.');
      await feed.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'Private cited fixture concern.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(2);
      expect(bodies[1].evidence_ref).toEqual(expect.any(String));
      expect(bodies[1].evidence_ref.length).toBeGreaterThan(0);
      expect(bodies[1].participant).toBe(bodies[0].participant);
      expect(bodies[1].request_id).not.toBe(bodies[0].request_id);
      const history = await (await page.request.get(server.url + '/chronicle?seed=382',
        {headers: {'X-Beta-Key': adaKey}})).text();
      expect(history).not.toContain('Private cited fixture concern.');
      await expect(bea.getByLabel('Recent events')).not.toContainText('Private cited fixture concern.');
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: a lost receipt freezes the payload until explicit retry`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people, bodies = [], receipts = [];
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        const response = await intercepted.fetch(); receipts.push(await response.json());
        if (bodies.length === 1) await intercepted.abort('failed');
        else await intercepted.fulfill({response});
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'Keep this private draft.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Retry to confirm');
      await expect(reportDialog(page).getByRole('button', {name: 'Retry report', exact: true})).toBeFocused();
      await expect(reportDialog(page).getByLabel('Details (optional)')).toBeDisabled();
      expect(bodies).toHaveLength(1);
      await reportDialog(page).getByRole('button', {name: 'Close', exact: true}).click();
      relay.send({type: 'agent_enter', name: 'Tessera', persona: 'tender', participant_id: 'e'.repeat(32)});
      await page.getByRole('button', {name: 'Report Tessera', exact: true}).click();
      await expect(reportDialog(page)).toContainText('About Bea');
      await expect(reportDialog(page)).toContainText('awaiting confirmation');
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(2);
      expect(bodies[1]).toEqual(bodies[0]);
      expect(receipts[1]).toEqual(receipts[0]);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: anonymous evidence and agent rows can be reported with keyboard focus recovery`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people, bodies = [];
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        await intercepted.fulfill({json: {report_id: 'synthetic-ui-receipt', status: 'received'}});
      });
      relay.send({type: 'chat', name: 'Unnamed traveler', text: 'Synthetic anonymous evidence.', evidence_ref: 'synthetic-evidence'});
      await disclose(page, 'History & journal');
      const opener = page.getByLabel('Recent events').getByRole('button', {name: 'Report Unnamed traveler', exact: true});
      await opener.focus(); await opener.press('Enter');
      await expect(reportDialog(page)).toBeVisible();
      await fill(reportDialog(page));
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      await expect(reportDialog(page).getByRole('button', {name: 'Close', exact: true})).toBeFocused();
      expect(bodies[0].participant).toBeNull();
      expect(bodies[0].evidence_ref).toBe('synthetic-evidence');
      await page.keyboard.press('Escape');
      await expect(opener).toBeFocused();

      relay.send({type: 'agent_enter', name: 'Tessera', persona: 'tender', participant_id: 'e'.repeat(32)});
      const agent = page.getByRole('button', {name: 'Report Tessera', exact: true});
      await agent.focus(); await agent.press('Space');
      await expect(reportDialog(page)).toContainText('About Tessera');
      await page.keyboard.press('Escape');
      await expect(agent).toBeFocused();
      expect(bodies).toHaveLength(1);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: same-credential retry survives a real process restart and stale target handles`, async ({browser}) => {
    test.setTimeout(60_000);
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people, bodies = [], receipts = [];
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        const response = await intercepted.fetch(); receipts.push(await response.json());
        if (bodies.length === 1) await intercepted.abort('failed');
        else await intercepted.fulfill({response});
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'Keep this report through the server restart.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Retry to confirm');
      const oldViewer = relay.welcomes.at(-1).participant_id;
      await server.restart();
      await expect.poll(() => relay.welcomes.at(-1).participant_id).not.toBe(oldViewer);
      const stale = await page.request.post(server.url + '/blocks', {
        headers: {'X-Beta-Key': adaKey}, data: {participant: bodies[0].participant, blocked: true},
      });
      expect(stale.status()).toBe(400);
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('Keep this report through the server restart.');
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(2);
      expect(bodies[1]).toEqual(bodies[0]);
      expect(receipts[1]).toEqual(receipts[0]);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: a changed credential cannot submit another participant's retained pending report`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page} = people, bodies = [], receipts = [];
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        const response = await intercepted.fetch(); receipts.push(await response.json());
        if (bodies.length === 1) await intercepted.abort('failed');
        else await intercepted.fulfill({response});
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'This pending report belongs to the original invitation.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Retry to confirm');
      await page.evaluate(key => localStorage.setItem('nw_beta_key', key), beaKey);
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Your invitation changed.');
      expect(bodies).toHaveLength(1);
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('This pending report belongs to the original invitation.');
      // Restoring the original credential permits only its exact receipt retry.
      await page.evaluate(key => localStorage.setItem('nw_beta_key', key), adaKey);
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(2);
      expect(bodies[1]).toEqual(bodies[0]);
      expect(receipts[1]).toEqual(receipts[0]);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: report details permit 2000 supplementary code points and reject 2001 points locally`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page} = people, bodies = [];
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        await intercepted.continue();
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'a'.repeat(2001));
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Shorten the details before sending.');
      expect(bodies).toHaveLength(0);
      const detail = '🪶'.repeat(2000);
      await reportDialog(page).getByLabel('Details (optional)').fill(detail);
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue(detail);
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(1);
      expect(bodies[0].detail).toBe(detail);
      expect(Array.from(bodies[0].detail)).toHaveLength(2000);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: a stalled response times out to an explicit idempotent retry`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page} = people, bodies = [], receipts = [];
      let committed;
      const stored = new Promise(resolve => { committed = resolve; });
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        const response = await intercepted.fetch(); receipts.push(await response.json());
        if (bodies.length === 1) { committed(); return; } // browser waits until its own abort
        await intercepted.fulfill({response});
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'Keep the same receipt after a stalled connection.');
      await page.clock.install();
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await stored;
      await page.clock.fastForward(15000);
      await expect(reportDialog(page)).toContainText('Retry to confirm');
      expect(bodies).toHaveLength(1);
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies).toHaveLength(2);
      expect(bodies[1]).toEqual(bodies[0]);
      expect(receipts[1]).toEqual(receipts[0]);
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: a receipt arriving after Close permits a fresh report`, async ({browser}) => {
    const server = await fixture(); let people, release = () => {};
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people;
      let committed;
      const stored = new Promise(resolve => { committed = resolve; });
      const held = new Promise(resolve => { release = resolve; });
      let requests = 0;
      await page.route(url => url.pathname === '/reports', async intercepted => {
        requests += 1;
        const response = await intercepted.fetch();
        committed(); await held; await intercepted.fulfill({response});
      });
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'A confirmed report must not freeze the next one.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await stored;
      await reportDialog(page).getByRole('button', {name: 'Close', exact: true}).click();
      const received = page.waitForResponse(response => new URL(response.url()).pathname === '/reports');
      release(); await (await received).finished();
      relay.send({type: 'agent_enter', name: 'Tessera', persona: 'tender', participant_id: 'e'.repeat(32)});
      await page.getByRole('button', {name: 'Report Tessera', exact: true}).click();
      await expect(reportDialog(page)).toContainText('About Tessera');
      await expect(reportDialog(page)).not.toContainText('awaiting confirmation');
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('');
      expect(requests).toBe(1);
    } finally { release(); await people?.close(); await server.close(); }
  });

  test(`${route}: stale evidence retains details and consent recovery never replays a report`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people, bodies = [];
      const beaHandle = relay.frames.find(frame => frame.type === 'player_join' && frame.name === 'Bea').participant_id;
      relay.send({type: 'chat', name: 'Bea', text: 'Synthetic stale evidence.', participant_id: beaHandle, evidence_ref: 'expired-evidence'});
      await disclose(page, 'History & journal');
      await page.route(url => url.pathname === '/reports', async intercepted => {
        bodies.push(intercepted.request().postDataJSON());
        await intercepted.fulfill({status: 422, json: {error: 'That evidence is unavailable. Select the traveler again.'}});
      });
      await page.getByLabel('Recent events').getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'Details survive a stale reference.');
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('That evidence is unavailable.');
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('Details survive a stale reference.');
      await expect(reportDialog(page).getByLabel('Details (optional)')).toBeEnabled();
      await expect(reportDialog(page).getByLabel('Details (optional)')).toBeFocused();
      await reportDialog(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      await page.locator('details').filter({has: page.locator('summary').filter({hasText: /^Travelers & chat$/})})
        .getByRole('button', {name: 'Report Bea', exact: true}).click();
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('Details survive a stale reference.');

      let accepted = false, attempts = 0;
      const notice = () => ({required: true, ready: true, accepted, revision: 'synthetic-notice',
        title: 'Temporary fixture notice', paragraphs: ['Synthetic notice for this UI case.'],
        temporary: true, minimum_age: 18, age_confirmation: 'I confirm that I am 18 or older.',
        agreement: 'I agree to the synthetic fixture notice.'});
      await page.route(url => url.pathname === '/participation', async intercepted => {
        if (intercepted.request().method() === 'POST') accepted = true;
        await intercepted.fulfill({json: notice()});
      });
      await page.route(url => url.pathname === '/reports', async intercepted => {
        attempts += 1; bodies.push(intercepted.request().postDataJSON());
        await intercepted.fulfill(attempts === 1
          ? {status: 428, json: {error: 'Review the notice.', participation_required: true}}
          : {json: {report_id: 'synthetic-consent-receipt', status: 'received'}});
      });
      await reportDialog(page).getByRole('button', {name: 'Send report', exact: true}).click();
      const gate = page.locator('dialog.participation-gate');
      await expect(gate).toBeVisible();
      await gate.locator('#participation-age').check();
      await gate.locator('#participation-agree').check();
      await gate.getByRole('button', {name: /Continue|Enter/i}).click();
      await expect(gate).toHaveCount(0);
      await expect(reportDialog(page)).toContainText('Your details are kept.');
      expect(attempts).toBe(1);
      await reportDialog(page).getByRole('button', {name: 'Retry report', exact: true}).click();
      await expect(reportDialog(page)).toContainText('Report received. Reference:');
      expect(bodies.at(-1)).toEqual(bodies.at(-2));
      expect(bodies.at(-1).evidence_ref).toBeNull();
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: unavailable collection disables chat without creating another composer`, async ({browser}) => {
    const server = await fixture({NESTED_WORLDS_DISABLE_CHAT: '1'}); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page} = people;
      await expect(page.getByLabel('Message to travelers')).toHaveCount(1);
      await expect(page.getByLabel('Message to travelers')).toBeDisabled();
      await expect(page.getByRole('button', {name: 'Send', exact: true})).toBeDisabled();
      await expect(page.locator('#chat-availability')).toHaveText('Traveler chat is currently unavailable.');
      await expect(page.locator('#chat-recording-notice')).toContainText('private log');
      await expectChatDescription(page, true);
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await expect(reportDialog(page)).toBeVisible();
      await page.keyboard.press('Escape');
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: no collection policy announces its own unavailable notice once`, async ({browser}) => {
    const server = await fixture(); const context = await browser.newContext();
    const page = await context.newPage();
    try {
      // Isolate the policy presentation from the server's collection dispatch.
      // Its configured participation notice is still acknowledged normally.
      await page.route(url => url.pathname === '/community', intercepted => intercepted.fulfill({json: {
        chat: {enabled: false, retention_mode: null, retention_days: null,
          notice: 'Live traveler chat collection is unavailable in this world.'},
        reports: {enabled: false, retention_days: null, notice: 'Private reporting is unavailable.',
          reasons: [], max_detail_length: null},
        contact: '', backup_notice: '', revision: 'synthetic-collection-disabled',
      }}));
      await enter(page, server, route);
      await expect(page.getByLabel('Message to travelers')).toBeDisabled();
      await expect(page.locator('#chat-recording-notice')).toHaveText(
        'Live traveler chat collection is unavailable in this world.');
      await expectChatDescription(page);
    } finally { await context.close(); await server.close(); }
  });

  test(`${route}: cancelled report details stay with their person`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page, relay} = people;
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await fill(reportDialog(page), 'A private draft about Bea.');
      await reportDialog(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('A private draft about Bea.');
      await reportDialog(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      relay.send({type: 'agent_enter', name: 'Tessera', persona: 'tender', participant_id: 'e'.repeat(32)});
      await page.getByRole('button', {name: 'Report Tessera', exact: true}).click();
      await expect(reportDialog(page)).toContainText('About Tessera');
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('');
      await expect(reportDialog(page).getByLabel('Reason', {exact: true})).toHaveValue('');
      await fill(reportDialog(page), 'A different private draft.');
      await reportDialog(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await expect(reportDialog(page).getByLabel('Details (optional)')).toHaveValue('');
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: a failed policy refresh keeps valid chat availability`, async ({browser}) => {
    const server = await fixture(); let people;
    try {
      people = await twoTravelers(browser, server, route);
      const {page} = people;
      await expect(page.getByLabel('Message to travelers')).toBeEnabled();
      await expectChatDescription(page);
      await page.route(url => url.pathname === '/community', intercepted =>
        intercepted.fulfill({status: 429, json: {error: 'Try again later.'}}));
      await page.getByRole('button', {name: 'Report Bea', exact: true}).click();
      await expect(reportDialog(page)).toBeVisible();
      await reportDialog(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      await expect(page.getByLabel('Message to travelers')).toBeEnabled();
      await expect(page.locator('#chat-recording-notice')).not.toContainText('could not be reached');
    } finally { await people?.close(); await server.close(); }
  });

  test(`${route}: initial metadata loading does not announce a failure`, async ({browser}) => {
    const server = await fixture(); const context = await browser.newContext();
    const page = await context.newPage(); let release = () => {};
    const held = new Promise(resolve => { release = resolve; });
    try {
      await page.route(url => url.pathname === '/community', async intercepted => {
        await held;
        await intercepted.continue();
      });
      await enter(page, server, route);
      await expect(page.locator('#chat-availability')).toBeHidden();
      await expect(page.locator('#chat-recording-notice')).toHaveText('Loading chat recording information…');
      await expect(page.getByLabel('Message to travelers')).toBeDisabled();
      await expectChatDescription(page);
      release();
      await expect(page.getByLabel('Message to travelers')).toBeEnabled();
      await expect(page.locator('#chat-recording-notice')).not.toContainText('Chat is currently unavailable.');
    } finally { release(); await context.close(); await server.close(); }
  });
}

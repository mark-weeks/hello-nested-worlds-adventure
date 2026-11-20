import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { displayName } from '../src/names.js';
import { serveBrowser } from './server.js';
import { studyEnvironment } from './study-fixture.js';
import { enterUX, serveUX } from './ux-fixture.js';

const key = 'nw_' + 'a'.repeat(32);
const player = 'Iris';
const samples = JSON.parse(await readFile(new URL('./fixtures/visual-language.json', import.meta.url), 'utf8'));
const region = samples[0].before.name;
const gallery = samples[1].before.name;

// Tab through the actual page and its open shadow roots. Locator.focus()
// would also reach controls missing from the keyboard's tab order.
async function tabTo(page, target, reverse = false) {
  await expect(target).toBeVisible();
  for (let step = 0; step < 40; step++) {
    if (await target.evaluate(element => element.matches(':focus'))) return;
    await page.keyboard.press(reverse ? 'Shift+Tab' : 'Tab');
  }
  await expect(target).toBeFocused();
}

async function activate(page, target, activationKey = 'Enter') {
  await tabTo(page, target);
  await page.keyboard.press(activationKey);
}

function replyTo(page, path) {
  return page.waitForResponse(reply => new URL(reply.url()).pathname === path);
}

test('a traveler uses the map, Speak, Puzzle and Act by keyboard and returns to the same place', async ({page}) => {
  test.setTimeout(60_000);
  const server = await serveBrowser({
    preseed: 382, invite: key, player,
    env: {...studyEnvironment, NESTED_WORLDS_TEST_WORLD: '1'},
  });
  const welcomes = [];
  let interruptConnection;
  try {
    await page.routeWebSocket(/\/ws\?/, socket => {
      const peer = socket.connectToServer();
      peer.onMessage(payload => {
        const message = JSON.parse(String(payload));
        if (message.type === 'welcome') welcomes.push(message);
        socket.send(payload);
      });
      interruptConnection = () => Promise.all([socket.close(), peer.close()]);
    });
    await page.emulateMedia({reducedMotion: 'reduce'});
    const invite = new URL('/app', server.url);
    invite.search = new URLSearchParams({key, name: player, node: region});
    await page.goto(invite.href);
    await expect(page.getByRole('heading', {name: 'Temporary test world'})).toBeVisible();
    await expect(page.getByRole('button', {name: 'World map'})).toHaveCount(0);
    await activate(page, page.locator('#participation-age'), 'Space');
    await activate(page, page.locator('#participation-agree'), 'Space');
    await activate(page, page.getByRole('button', {name: 'Agree and continue'}));
    await expect(page.getByText(/Some travelers you meet are AI/)).toBeVisible();
    await activate(page, page.getByRole('button', {name: 'Begin', exact: true}));

    const place = page.locator('#node-name');
    await expect(place).toHaveText(displayName(region));
    await expect.poll(() => welcomes.length).toBe(1);
    await activate(page, page.getByRole('button', {name: 'World map', exact: true}));
    const map = page.getByRole('group', {name: 'World map'});
    const regionMarker = map.getByRole('button', {name: new RegExp(displayName(region))});
    const galleryMarker = map.getByRole('button', {name: new RegExp(displayName(gallery))});
    await expect(galleryMarker).toBeVisible();
    await tabTo(page, regionMarker);
    await page.keyboard.press('ArrowRight');
    await expect(galleryMarker).toBeFocused();
    await expect(place).toHaveText(displayName(region));
    await page.keyboard.press('Enter');
    await expect(place).toHaveText(displayName(gallery));
    expect(await map.evaluate(el => el.getAnimations({subtree: true}).length)).toBe(0);

    const modes = page.getByRole('group', {name: 'Interaction mode'});
    await expect(modes.getByRole('button')).toHaveCount(3);
    await expect(page.getByText('Travelers & chat', {exact: true})).toHaveCount(1);
    await activate(page, modes.getByRole('button', {name: 'Speak', exact: true}));
    await tabTo(page, page.getByRole('textbox', {name: 'Message to this place'}));
    await page.keyboard.press('ControlOrMeta+a');
    await page.keyboard.type('Are you human?');
    const [speech] = await Promise.all([replyTo(page, '/speak'), page.keyboard.press('Control+Enter')]);
    expect(speech.request().postDataJSON().node_name).toBe(gallery);
    const said = await speech.json();
    expect(said.ai).toBe(false);
    await expect(page.getByText(said.response, {exact: true})).toBeVisible();

    const puzzle = modes.getByRole('button', {name: 'Puzzle', exact: true});
    await tabTo(page, puzzle, true);
    await page.keyboard.press('Enter');
    await tabTo(page, page.getByRole('textbox', {name: 'Puzzle answer'}));
    await page.keyboard.type('An untried possibility');
    const [answer] = await Promise.all([replyTo(page, '/puzzle/attempt'), page.keyboard.press('Enter')]);
    expect(answer.request().postDataJSON().node_name).toBe(gallery);
    expect(await answer.json()).toMatchObject({correct: false, attempt: 1});
    await expect(page.getByText(/Wrong\. .* left\.|The question keeps its answer\./)).toBeVisible();

    const act = modes.getByRole('button', {name: 'Act', exact: true});
    await tabTo(page, act, true);
    await page.keyboard.press('Enter');
    const composer = page.locator('enfolded-interventions');
    await tabTo(page, composer.getByRole('button', {name: 'Shade', exact: true}));
    const [action] = await Promise.all([replyTo(page, '/interventions/commit'), page.keyboard.press('Enter')]);
    expect(await action.json()).toMatchObject({accepted: true});
    await expect(composer.getByRole('status')).toContainText('Shade');
    expect(welcomes).toHaveLength(1);
    await expect(page).toHaveURL(server.url + '/app');

    // Break the live connection while the map is open, then separately
    // exercise a full page reload. Each must join the same traveler and place.
    await interruptConnection();
    await expect.poll(() => welcomes.length).toBe(2);
    await expect(place).toHaveText(displayName(gallery));
    await expect(map).toBeVisible();
    await page.reload();
    await expect.poll(() => welcomes.length).toBe(3);
    expect(new Set(welcomes.map(message => message.session_id)).size).toBe(3);
    expect(welcomes[0].participant_id).toBeTruthy();
    for (const welcome of welcomes.slice(1)) expect(welcome.participant_id).toBe(welcomes[0].participant_id);
    await expect(place).toHaveText(displayName(gallery));
    await expect(map).toBeVisible();
    await activate(page, act);
    await activate(page, composer.getByText('Actions still echoing', {exact: true}));
    await expect(composer.getByText(player + ' · Shade', {exact: true})).toBeVisible();
  } finally {
    await server.close();
  }
});

test('a failed first map download leaves passages and interactions available', async ({page}) => {
  const server = await serveUX();
  try {
    let downloads = 0;
    await page.route('**/assets/MapView-*.js', route => {
      downloads++;
      return route.abort('failed');
    });
    await enterUX(page, server, '/app', region);
    const place = page.locator('#node-name');
    await expect(place).toHaveText(displayName(region));
    const navigation = page.getByRole('navigation', {name: 'Explore places'});
    const openMap = navigation.getByRole('button', {name: 'World map', exact: true});
    await tabTo(page, openMap);
    expect(downloads).toBe(0);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('status').filter({hasText: 'The map could not open'})).toBeVisible();
    expect(downloads).toBe(1);
    await expect(place).toHaveText(displayName(region));

    await activate(page, navigation.getByRole('button', {name: new RegExp(displayName(gallery))}));
    await expect(place).toHaveText(displayName(gallery));
    await activate(page, page.getByRole('button', {name: 'Puzzle', exact: true}));
    await expect(page.getByRole('textbox', {name: 'Puzzle answer'})).toBeVisible();
    await activate(page, navigation.getByRole('button', {name: 'Living scene', exact: true}));
    await expect(page.getByRole('region', {name: 'Living scene'}).getByRole('img')).toBeVisible();
    await expect(place).toHaveText(displayName(gallery));
  } finally {
    await server.close();
  }
});

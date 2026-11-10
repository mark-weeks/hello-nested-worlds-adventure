// The owner's guardrail (b) (2026-11-06): both clients say at entry that some
// travelers are AI. A place asked "are you human?" answers truthfully; that
// place half is proposed in PR #158 and awaits the owner's decision.
// The browser server runs with NESTED_WORLDS_DISABLE_AI=1, so this is the
// AI-off path: the authored answer, not the quiet line.
import {expect, test} from '@playwright/test';
import {serveBrowser} from './server.js';

const NOTICE = "Some travelers you meet are AI. You won't always be able to tell, but if you ask one, it will tell you the truth.";
const PLACE_ANSWER = 'I am not a person. I am a place in this world, and the voice you hear from me comes from an AI.';
const QUIET = 'The worlds are quiet today. Try again tomorrow.';

function speakReply(page) {
  return page.waitForResponse(reply => new URL(reply.url()).pathname === '/speak');
}

test('the scene view says some travelers are AI and a place says it is not a person', async ({page}) => {
  const server = await serveBrowser({preseed: 382});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(server.url + '/app');
    await expect(page.getByText(NOTICE, {exact: true})).toBeVisible();
    await page.getByRole('button', {name: 'Begin', exact: true}).click();
    await page.getByPlaceholder('Your name', {exact: true}).fill('Iris');
    await page.getByRole('button', {name: 'Enter', exact: true}).click();
    await expect(page.locator('#node-name')).toBeVisible();

    const message = page.getByLabel('Message to this place', {exact: true});
    await message.fill('Are you human?');
    let [reply] = await Promise.all([speakReply(page),
      page.getByRole('button', {name: 'Speak to node', exact: true}).click()]);
    expect(await reply.json()).toEqual({response: PLACE_ANSWER, ai: false});
    await expect(page.getByText(PLACE_ANSWER, {exact: true})).toBeVisible();

    // An ordinary line still meets the switched-off voice.
    await message.fill('Are you afraid of humans?');
    [reply] = await Promise.all([speakReply(page),
      page.getByRole('button', {name: 'Speak to node', exact: true}).click()]);
    expect(await reply.json()).toEqual({response: QUIET, ai: false});
    expect(errors).toEqual([]);
  } finally {
    await server.close();
  }
});

test('the map view and the guide carry the same notice, and the map gets the same answer', async ({page}) => {
  const server = await serveBrowser({preseed: 382});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(server.url + '/');
    await expect(page.locator('#intro-modal')).toBeVisible();
    await expect(page.locator('#intro-modal').getByText(NOTICE, {exact: true})).toBeVisible();
    await page.click('#btn-begin');
    await page.fill('#player-name-input', 'Iris');
    await page.click('#btn-join');
    await expect(page.locator('#node-name')).not.toHaveText('Select a node');

    await page.fill('#message', 'r u a bot?');
    const [reply] = await Promise.all([speakReply(page), page.click('#btn-do-speak')]);
    expect(await reply.json()).toEqual({response: PLACE_ANSWER, ai: false});
    await expect(page.locator('#speak-response')).toHaveText(PLACE_ANSWER);

    await page.goto(server.url + '/guide');
    await expect(page.getByText('Some travelers you meet are AI.', {exact: true})).toBeVisible();
    await expect(page.locator('p', {hasText: 'Some travelers you meet are AI.'}))
      .toContainText("You won't always be able to tell, but if you ask one, it will tell you the truth.");
    expect(errors).toEqual([]);
  } finally {
    await server.close();
  }
});

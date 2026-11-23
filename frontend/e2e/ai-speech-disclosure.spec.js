import {expect, test} from '@playwright/test';
import {disclose} from './disclosures.js';
import {enterUX, serveUX} from './ux-fixture.js';

const orchard = 'Emberlit Orchard Terraces';
const placeLine = 'The last frost left a silver seam in my bark.';
const agentLine = 'I mend the orchard paths after the rain.';
const delayedQuestion = 'How did the path look yesterday?';
const agentEndpoint = url => url.pathname === '/agent/voice';

for (const entry of ['/', '/map']) {
  test(`${entry} identifies generated place and agent replies until the next exchange`, async ({page}) => {
    const server = await serveUX();
    let releaseEarlierReply;
    const earlierReply = new Promise(resolve => { releaseEarlierReply = resolve; });
    try {
      await page.route(url => url.pathname === '/history' && url.searchParams.get('node_name') === orchard,
        route => route.fulfill({json: {mutations: [
          {type: 'AGENT_VISIT', data: {agent: 'Tessera', persona: 'tender'}},
        ]}}));
      await page.route(url => url.pathname === '/speak', route =>
        route.fulfill({json: {response: placeLine, ai: true}}));
      await page.route(agentEndpoint, async route => {
        const {message} = route.request().postDataJSON();
        if (message === 'Are you human?') return route.continue();
        if (message === delayedQuestion) await earlierReply;
        return route.fulfill({json: {agent: 'Tessera', persona: 'tender', node: orchard, response: agentLine, ai: true}});
      });

      await enterUX(page, server, entry, orchard);
      await expect(page.locator('#node-name')).toHaveText('Emberlit Orchard Terraces');
      const panel = page.getByRole('region', {name: 'Interact here'});
      const response = panel.getByRole('status');
      const disclosure = response.getByText('AI-generated reply', {exact: true});
      const message = panel.getByLabel('Message to this place');

      await message.fill('What do you remember?');
      await panel.getByRole('button', {name: /^Speak to node$/i}).click();
      await expect(response.getByText(placeLine, {exact: true})).toBeVisible();
      await expect(disclosure).toBeVisible();

      const targetAgent = panel.getByRole('button', {name: 'Tessera · tender'});
      await targetAgent.click();
      await expect(response).toBeEmpty();
      const speakToAgent = panel.getByRole('button', {name: 'Speak to Tessera'});
      await message.fill('What brought you here?');
      await speakToAgent.click();
      await expect(response.getByText(agentLine, {exact: true})).toBeVisible();
      await expect(disclosure).toBeVisible();

      // The earlier agent reply is still in transit when the player changes
      // addressees and starts a new exchange with the same agent.
      await message.fill(delayedQuestion);
      const [pending] = await Promise.all([
        page.waitForRequest(request => agentEndpoint(new URL(request.url()))),
        speakToAgent.click(),
      ]);
      await expect(response).toHaveText('…');
      await expect(disclosure).toBeHidden();
      await panel.getByRole('button', {name: 'the place', exact: true}).click();
      await expect(response).toBeEmpty();
      await targetAgent.click();
      await expect(response).toBeEmpty();
      await message.fill('Are you human?');
      const [identityReply] = await Promise.all([
        page.waitForResponse(reply => agentEndpoint(new URL(reply.url()))),
        speakToAgent.click(),
      ]);
      const identity = await identityReply.json();
      expect(identity).toMatchObject({agent: 'Tessera', response: expect.stringContaining('an AI'), ai: false});
      await expect(response).toHaveText(identity.response);
      await expect(disclosure).toBeHidden();

      releaseEarlierReply();
      const obsolete = await pending.response();
      if (obsolete) await obsolete.finished();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(response).toHaveText(identity.response);
      await expect(disclosure).toBeHidden();

      await panel.getByRole('button', {name: 'Act', exact: true}).click();
      await disclose(page, 'Describe an intention');
      await expect(panel.getByText(/AI can interpret other wording when enabled\./)).toBeVisible();
    } finally {
      releaseEarlierReply();
      await page.unrouteAll({behavior: 'wait'});
      await server.close();
    }
  });
}

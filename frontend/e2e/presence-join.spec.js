import {expect, test} from '@playwright/test';
import {serveUX, enterUX} from './ux-fixture.js';
import {disclose} from './disclosures.js';

const place = 'Emberlit Orchard Terraces-111111';

for (const route of ['/', '/app']) {
  test(`${route}: joins show their place and restarted handles retire only live buffers`, async ({page}) => {
    const server = await serveUX();
    let send, welcome;
    await page.routeWebSocket(/\/ws\?/, socket => {
      send = message => socket.send(JSON.stringify(message));
      const peer = socket.connectToServer();
      peer.onMessage(message => {
        const frame = JSON.parse(message);
        if (frame.type === 'welcome') welcome = frame;
        socket.send(message);
      });
    });
    try {
      await enterUX(page, server, route, place);
      await expect(page.locator('#node-name')).toHaveText('Emberlit Orchard Terraces');
      await expect.poll(() => typeof send).toBe('function');
      await expect.poll(() => welcome?.participant_id).toBeTruthy();
      await disclose(page, 'Travelers & chat');
      send({type:'player_join', session_id:'new-traveler', participant_id:'old-target', name:'New traveler', node:place});
      const traveler = page.locator('.traveler,.traveler-row').filter({hasText:'New traveler'});
      await expect(traveler).toBeEnabled();
      await expect(traveler).toContainText(route === '/app' ? 'Here' : 'Emberlit Orchard Terraces');
      await disclose(page, 'History & journal');
      const feed = page.getByLabel('Recent events');
      send({type:'chat', participant_id:'old-target', name:'New traveler', text:'An earlier live sentence'});
      send({type:'agent_encounter', agent1:'Earlier traveler', agent2:'Another traveler',
        node:place, participant_ids:['old-target', 'old-other']});
      send({type:'intervention_changed', node:place, flavor:'A shared consequence remains'});
      await expect(feed).toContainText('An earlier live sentence');
      await expect(feed).toContainText('Earlier traveler meets Another traveler');
      await expect(feed).toContainText('A shared consequence remains');
      // An ordinary reconnect keeps live buffers. A restart's new viewer
      // handle retires speech and meetings that no future block could match.
      send(welcome);
      await expect(feed).toContainText('An earlier live sentence');
      send({...welcome, participant_id:'fresh-runtime-viewer'});
      await expect(feed).not.toContainText('An earlier live sentence');
      await expect(feed).not.toContainText('Earlier traveler meets Another traveler');
      await expect(feed).not.toContainText('New traveler joined');
      await expect(feed).toContainText('A shared consequence remains');
    } finally {
      await page.goto('about:blank').catch(() => {});
      await server.close();
    }
  });
}

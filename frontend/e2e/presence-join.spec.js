import {expect, test} from '@playwright/test';
import {serveUX, enterUX} from './ux-fixture.js';
import {disclose} from './disclosures.js';

const place = 'Emberlit Orchard Terraces-111111';

for (const route of ['/', '/app']) {
  test(`${route}: a join announces a reachable place before any move`, async ({page}) => {
    const server = await serveUX();
    let send;
    await page.routeWebSocket(/\/ws\?/, socket => {
      send = message => socket.send(JSON.stringify(message));
      const peer = socket.connectToServer();
      peer.onMessage(message => socket.send(message));
    });
    try {
      await enterUX(page, server, route, place);
      await expect(page.locator('#node-name')).toHaveText('Emberlit Orchard Terraces');
      await expect.poll(() => typeof send).toBe('function');
      await disclose(page, 'Travelers & chat');
      send({type:'player_join', session_id:'new-traveler', name:'New traveler', node:place});
      const traveler = page.getByRole('button', {name:/New traveler/});
      await expect(traveler).toBeEnabled();
      await expect(traveler).toContainText(route === '/app' ? 'Here' : 'Emberlit Orchard Terraces');
    } finally {
      await page.goto('about:blank').catch(() => {});
      await server.close();
    }
  });
}

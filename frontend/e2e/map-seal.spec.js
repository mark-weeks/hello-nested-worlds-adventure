import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { displayName } from '../src/names.js';
import { disclose } from './disclosures.js';
import { enterUX, key, serveUX } from './ux-fixture.js';

test('a map jump under a seal opens the room’s puzzle and a late refusal leaves later travel alone', async ({page}) => {
  const samples = JSON.parse(await readFile(new URL('./fixtures/visual-language.json', import.meta.url), 'utf8'));
  const keeper = samples[0].before.name;
  const server = await serveUX();
  try {
    // The fixture server generates the move_denied frames. For the second
    // trip, pause one real frame in the browser until the player has left.
    await page.addInitScript(() => {
      window.WebSocket = class extends WebSocket {
        constructor(...args) {
          super(...args);
          this.addEventListener('message', event => {
            const frame = JSON.parse(event.data);
            if (frame.type !== 'move_denied' || frame.reason !== 'sealed') return;
            window.sealFrame = frame;
            window.sealFrameCount = (window.sealFrameCount || 0) + 1;
            if (window.holdNextSeal) {
              window.holdNextSeal = false;
              event.stopImmediatePropagation();
              window.deliverSeal = () => this.dispatchEvent(new MessageEvent('message', {data: event.data}));
            }
          });
        }
      };
    });
    await page.setViewportSize({width: 320, height: 740});
    await enterUX(page, server, '/app', keeper);
    await page.evaluate(() => { document.documentElement.style.fontSize = '32px'; });
    await expect(page.getByText('● Connected to the shared world')).toBeVisible();
    await page.getByRole('button', {name: 'World map', exact: true}).click();
    const map = page.getByRole('group', {name: 'World map'});
    const keeperMarker = map.getByRole('button', {name: /Emberlit Orchard Terraces/});
    const roomMarker = map.getByRole('button', {name: /Mossbound Orchard Alcove/});
    const childMarker = map.getByRole('button', {name: /Lucent Thorn Loom/});
    const siblingMarker = map.getByRole('button', {name: /Fallow Orchard Chest/});
    async function travelUnderSeal() {
      await keeperMarker.focus();
      await page.keyboard.press('ArrowRight');
      await page.keyboard.press('ArrowDown');
      await expect(roomMarker).toBeFocused();
      await page.keyboard.press('ArrowRight');
      await expect(childMarker).toBeFocused();
      // With large text, the two wrapped marker labels still need separate hit targets.
      await expect.poll(async () => {
        const [loom, chest] = await Promise.all([childMarker.boundingBox(), siblingMarker.boundingBox()]);
        return chest.y - (loom.y + loom.height);
      }).toBeGreaterThanOrEqual(0);
      await page.keyboard.press('Enter');
    }

    await travelUnderSeal();
    await page.waitForFunction(() => window.sealFrame);
    const denial = await page.evaluate(() => window.sealFrame);
    expect(displayName(denial.node)).toBe('Lucent Thorn Loom');
    expect(displayName(denial.sealed_by)).toBe('Mossbound Orchard Alcove');
    const place = page.locator('#node-name');
    await expect(place).toHaveAttribute('title', denial.sealed_by);
    await expect(roomMarker).toHaveAttribute('aria-current', 'location');
    await expect(roomMarker).toHaveAccessibleName(/Seal threshold/);
    await expect(childMarker).toHaveAccessibleName(/Beyond a seal/);
    await disclose(page, 'History & journal');
    const feed = page.getByLabel('Recent events');
    const sealNotice = feed.getByText(/Mossbound Orchard Alcove is sealed/);
    const sealPrompt = feed.getByText(denial.prompt, {exact: true});
    await expect(sealNotice).toHaveCount(1);
    await expect(sealPrompt).toHaveCount(1);
    await expect(feed).not.toContainText('Lucent Thorn Loom is sealed');

    const [puzzle] = await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === '/puzzle'),
      page.getByRole('button', {name: 'Puzzle', exact: true}).click(),
    ]);
    expect(new URL(puzzle.url()).searchParams.get('node_name')).toBe(denial.sealed_by);
    await expect(page.getByRole('region', {name: 'Interact here'}).getByText(denial.prompt, {exact: true})).toBeVisible();
    const saved = await page.request.get(server.url + '/position', {headers: {'X-Beta-Key': key}});
    expect((await saved.json()).position.node).toBe(keeper);
    expect(await page.evaluate(() => window.sealFrameCount)).toBe(1);

    await keeperMarker.click();
    await page.evaluate(() => { window.holdNextSeal = true; });
    await travelUnderSeal();
    await page.waitForFunction(() => typeof window.deliverSeal === 'function');
    await keeperMarker.click();
    await expect(place).toHaveAttribute('title', keeper);
    await page.evaluate(async () => {
      window.deliverSeal();
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    await expect(place).toHaveAttribute('title', keeper);
    await expect(keeperMarker).toHaveAttribute('aria-current', 'location');
    await expect(sealNotice).toHaveCount(1);
    await expect(sealPrompt).toHaveCount(1);
  } finally {
    await server.close();
  }
});

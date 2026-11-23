import {test, expect} from '@playwright/test';
import {disclose} from './disclosures.js';
import {enterUX, serveUX} from './ux-fixture.js';

const gallery = 'Broken Ember Gallery-1111111';
const bundled = 'AI-generated background, included with the game.';
const generated = 'AI-generated background for this place.';
const drawn = 'Scene drawn from this place’s conditions.';
const imageApi = url => url.pathname === '/image';

test('the living scene credits only a background it can draw', async ({page}) => {
  const server = await serveUX();
  let releaseAsset;
  const held = new Promise(resolve => { releaseAsset = resolve; });
  try {
    await page.emulateMedia({reducedMotion: 'reduce'});
    const generatedUrl = '/media/places/gallery-v1.png?generated-fixture';
    const missingUrl = '/media/places/missing-fixture.png';
    let imageUrl = generatedUrl;
    const requests = [];
    await page.route(imageApi, route => {
      requests.push(route.request().postDataJSON().node_name);
      return route.fulfill({json: {url: imageUrl}});
    });
    const isGeneratedAsset = url => url.searchParams.has('generated-fixture');
    await page.route(isGeneratedAsset, async route => {
      await held;
      await route.continue();
    });

    await enterUX(page, server, '/app', gallery);
    const scene = page.getByRole('region', {name: 'Living scene'});
    const caption = scene.locator('figcaption');
    const nav = page.getByRole('navigation', {name: 'Explore places'});
    const mechanism = nav.getByRole('button', {name: /Object ↘ Amber Ember Mechanism/});
    const returnToGallery = nav.getByRole('button', {name: '↑ Broken Ember Gallery'});
    await expect(caption).toHaveText(bundled);
    await expect(caption).toBeVisible();
    const canvas = scene.getByRole('img');
    await expect(canvas).toHaveAccessibleDescription(/AI-generated background, included with the game\./);
    expect(requests).toEqual([]);

    const requested = page.waitForRequest(request => isGeneratedAsset(new URL(request.url())));
    await mechanism.click();
    await requested;
    await expect(caption).toHaveText(drawn);
    releaseAsset();
    await expect(caption).toHaveText(generated);
    await expect(canvas).toHaveAccessibleDescription(/AI-generated background for this place\./);
    expect(requests).toEqual(['Amber Ember Mechanism-11111112']);

    await disclose(page, 'History & journal');
    await page.getByRole('button', {name: 'Replay History'}).click();
    const replay = page.getByRole('dialog', {name: /Replay History/});
    await expect(replay.getByText(drawn, {exact: true})).toBeVisible();
    await expect(replay.getByRole('img')).toHaveAccessibleDescription(drawn);
    await expect(replay.getByText(generated, {exact: true})).toHaveCount(0);
    await replay.getByRole('button', {name: 'Close history replay'}).click();
    await expect(caption).toHaveText(generated);

    await returnToGallery.click();
    await expect(caption).toHaveText(bundled);
    imageUrl = missingUrl;
    const missing = page.waitForResponse(response => new URL(response.url()).pathname === missingUrl);
    await mechanism.click();
    expect((await missing).status()).toBe(404);
    await expect(caption).toHaveText(drawn);
    await expect(canvas).toHaveAccessibleDescription(/Scene drawn from this place’s conditions\./);

    await returnToGallery.click();
    await expect(caption).toHaveText(bundled);
    await page.unroute(imageApi);
    const disabled = page.waitForResponse(response => imageApi(new URL(response.url())));
    await mechanism.click();
    const response = await disabled;
    expect(await response.json()).toMatchObject({url: null});
    await expect(caption).toHaveText(drawn);
  } finally {
    releaseAsset();
    await server.close();
  }
});

test('the explorer credits art in Conditions and Replay History', async ({page}) => {
  const server = await serveUX();
  try {
    await page.emulateMedia({reducedMotion: 'reduce'});
    const requests = [];
    page.on('request', request => {
      if (imageApi(new URL(request.url()))) requests.push(request.url());
    });
    // Select the place before the deferred art module is available. Loading
    // the real module below exercises the explorer's first NodeArt-only paint.
    await page.route('**/nodeart-global.js', route => route.fulfill({
      contentType: 'text/javascript', body: '',
    }));
    await enterUX(page, server, '/map', gallery);
    await expect(page.locator('#node-name')).toHaveText('Broken Ember Gallery');
    await disclose(page, 'Conditions here');
    const caption = page.locator('#node-art-source');
    await expect(caption).toBeEmpty();
    const firstCaption = await page.evaluate(async () => {
      let captionAtReady;
      window.addEventListener('nodeart-ready', () => {
        captionAtReady = document.getElementById('node-art-source').textContent;
      }, {once: true});
      await import('/nodeart-global.js?late');
      return captionAtReady;
    });
    expect(firstCaption).toBe(drawn);
    await expect(caption).toBeVisible();
    await expect(caption).toHaveText(bundled);
    await expect(page.locator('#node-sigil')).toHaveAccessibleDescription(/AI-generated background, included with the game\./);
    await disclose(page, 'History & journal');
    await page.getByRole('button', {name: 'Replay History'}).click();
    const replay = page.getByRole('dialog', {name: /Wayback/});
    await expect(replay.getByText(bundled, {exact: true})).toBeVisible();
    await expect(replay.getByRole('img')).toHaveAccessibleDescription(bundled);
    await page.keyboard.press('Escape');

    const nav = page.getByRole('navigation', {name: 'Explore places'});
    await nav.getByRole('button', {name: /Object ↘ Amber Ember Mechanism/}).click();
    await expect(caption).toHaveText(drawn);
    expect(requests).toEqual([]);
  } finally {
    await server.close();
  }
});

import { expect, test } from '@playwright/test';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

// The production bundle does not replay effects. Exercise the actual component
// in React development StrictMode rather than approximating it with DOM calls.
let dev, cache, url;
test.beforeAll(async () => {
  const frontend = path.resolve(import.meta.dirname, '..');
  cache = await mkdtemp(path.join(tmpdir(), 'enfolded-chronicle-vite-'));
  dev = await createServer({
    configFile: false, plugins: [react()], root: frontend,
    cacheDir: cache,
    server: { host: '127.0.0.1', port: 0, fs: { allow: [path.dirname(frontend)] } },
  });
  await dev.listen();
  url = `http://127.0.0.1:${dev.httpServer.address().port}/e2e/fixtures/chronicle-strict-mode.html`;
});
test.afterAll(async () => {
  await dev?.close();
  if (cache) await rm(cache, { recursive: true, force: true });
});

for (const closeWith of ['button', 'Escape']) {
  test(`Chronicle restores its opener after ${closeWith} in development StrictMode`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/chronicle?*', r => r.fulfill({ json: {
      entries: [], total: 0, era_now: 'Quiet', next_before: null,
    } }));
    await page.goto(url);
    const opener = page.getByRole('button', { name: 'View full chronicle' });
    const dialog = page.getByRole('dialog', { name: 'World Chronicle' });
    for (let visit = 0; visit < 2; visit++) {
      await opener.focus(); await page.keyboard.press('Enter');
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId('effect-setups')).toHaveText('2');
      expect(await dialog.evaluate(el => el.matches(':modal'))).toBe(true);
      if (closeWith === 'Escape') await page.keyboard.press('Escape');
      else await dialog.getByRole('button', { name: 'close', exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(opener).toBeFocused();
    }
    expect(errors).toEqual([]);
  });
}

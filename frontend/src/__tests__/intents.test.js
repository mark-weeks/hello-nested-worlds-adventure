import { beforeEach, expect, test, vi } from 'vitest';

const credentialA = 'nw_' + 'a'.repeat(32);
const credentialB = 'nw_' + 'b'.repeat(32);
const rotated = 'nw_' + 'c'.repeat(32);
const owner = '1'.repeat(32);
const other = '2'.repeat(32);

async function reload() {
  vi.resetModules();
  await import('../../../static/intents.js');
  return globalThis.EnfoldedIntents;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  const saved = new Map();
  vi.stubGlobal('localStorage', {
    getItem: key => saved.get(key) ?? null,
    setItem: (key, value) => saved.set(key, value),
    removeItem: key => saved.delete(key),
  });
  vi.stubGlobal('fetch', vi.fn(async (_, options) => ({
    ok: true,
    json: async () => ({participant: {id: options.headers['X-Beta-Key'] === credentialB ? other : owner}}),
  })));
});

test('pending receipt survives reload and an unavailable identity endpoint', async () => {
  let intents = await reload();
  const first = await intents.begin('/act', 382, {verb: 'mend'}, credentialA);
  intents = await reload();
  fetch.mockRejectedValue(new Error('offline'));
  expect(await intents.begin('/act', 382, {verb: 'mend'}, credentialA)).toEqual(first);
  expect(fetch).toHaveBeenCalledTimes(1);
  intents.finish(first);
  expect((await intents.begin('/act', 382, {verb: 'mend'}, credentialA)).request_id).not.toBe(first.request_id);
});

test('rotation preserves the owner namespace while another account stays separate', async () => {
  const intents = await reload();
  const first = await intents.begin('/act', 382, {}, credentialA);
  expect(await intents.begin('/act', 382, {}, rotated)).toEqual(first);
  expect((await intents.begin('/act', 382, {}, credentialB)).request_id).not.toBe(first.request_id);
  expect(fetch).toHaveBeenCalledTimes(3);
});

test('a previously unknown credential still requires a successful identity lookup', async () => {
  const intents = await reload();
  fetch.mockRejectedValue(new Error('offline'));
  await expect(intents.begin('/act', 382, {}, credentialA)).rejects.toThrow('offline');
  expect(await intents.begin('/act', 382, {}, '')).toBeNull();
});

import {expect, test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {promisify} from 'node:util';
import {serveBrowser} from './server.js';

const execute = promisify(execFile);
const repo = path.resolve(import.meta.dirname, '../..');
const key = 'nw_' + '5'.repeat(32);
const player = 'Puzzle traveler';
const failureLine = 'The question keeps its answer.';
// A synthetic definition in a caller-owned scratch world. These values are
// disclosure sentinels, not answers drawn from any real world's puzzles.
const fixtureAnswer = 'fixture-unreleased-solution';
const legacyAnswer = 'legacy-answer-must-stay-unseen';

async function fixture() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-answer-withdrawal-'));
  const database = path.join(directory, 'worlds.db');
  let server;
  try {
    const {stdout} = await execute(process.env.ENFOLDED_PYTHON || 'python', ['-c', `
from pathlib import Path
import json, sys
import persistence
from persistence import puzzle_content
from multiverse import store
persistence._DB_PATH=Path(sys.argv[1])
store.ensure_born(382)
persistence.mint_invite_key(sys.argv[2], sys.argv[3])
root=store.world_tree(382)
puzzle_content.pin(382, root.name, 0, 1, {
    'name':'The Fixture Question', 'kind':'RIDDLE',
    'prompt':'A question for the disclosure rehearsal.',
    'answer':sys.argv[4], 'hints':[], 'max_attempts':2, 'difficulty':2,
}, [])
print(json.dumps({'node':root.name}))
`, database, key, player, fixtureAnswer], {cwd: repo});
    const {node} = JSON.parse(stdout);
    server = await serveBrowser({database});
    return {...server, node, async close() {
      await server.close();
      await rm(directory, {recursive: true, force: true});
    }};
  } catch (error) {
    await server?.close();
    await rm(directory, {recursive: true, force: true});
    throw error;
  }
}

for (const client of ['/', '/app']) for (const legacy of [false, true]) {
  test(`${client}: an exhausted real pool keeps its answer hidden${legacy ? ', including an old response field' : ''}`, async ({page}) => {
    const server = await fixture();
    const upstreamResults = [];
    try {
      await page.addInitScript(({node, key, player}) => {
        localStorage.setItem('nw_seen_intro', '1');
        localStorage.setItem('nw_sound_preference', 'off');
        localStorage.setItem('nw_player_name', player);
        localStorage.setItem('nw_beta_key', key);
        localStorage.setItem('nw_last_node', node);
      }, {node: server.node, key, player});
      if (legacy) await page.route('**/puzzle/attempt', async route => {
        const response = await route.fetch();
        const data = await response.json();
        upstreamResults.push(data);
        await route.fulfill({response, json: data.result === 'FAILED'
          ? {...data, correct_answer: legacyAnswer} : data});
      });
      await page.goto(server.url + client);
      await expect(page.locator('#node-name')).toHaveAttribute('title', server.node);
      await page.getByRole('button', {name: 'Puzzle', exact: true}).click();
      await expect(page.getByText('The Fixture Question', {exact: true})).toBeVisible();
      const input = client === '/' ? page.locator('#puzzle-answer') : page.getByLabel('Puzzle answer', {exact: true});
      for (const [index, guess] of ['first guess', 'second guess'].entries()) {
        await input.fill(guess);
        const [response] = await Promise.all([
          page.waitForResponse(reply => new URL(reply.url()).pathname === '/puzzle/attempt'),
          page.getByRole('button', {name: 'Submit', exact: true}).click(),
        ]);
        expect(response.status()).toBe(200);
        const result = await response.json();
        if (!legacy) upstreamResults.push(result);
        expect(result.correct).toBe(false);
        expect(result.attempt).toBe(index + 1);
        expect(result.result).toBe(index ? 'FAILED' : 'UNSOLVED');
      }
      for (const result of upstreamResults) expect(result).not.toHaveProperty('correct_answer');
      await expect(page.getByText(failureLine, {exact: true})).toBeVisible();
      await expect(input).toBeDisabled();
      await expect(page.locator('body')).not.toContainText(fixtureAnswer);
      await expect(page.locator('body')).not.toContainText(legacyAnswer);
      await expect(page.locator('body')).not.toContainText('The answer was:');

      // Reopening preserves the existing pool and each client's existing
      // exhausted-state controls. Batch 1a changes only answer disclosure.
      await page.reload();
      await page.getByRole('button', {name: 'Puzzle', exact: true}).click();
      await expect(page.getByText('The Fixture Question', {exact: true})).toBeVisible();
      const reopened = await (await page.request.get(server.url + '/puzzle?node_name=' + encodeURIComponent(server.node),
        {headers: {'X-Beta-Key': key}})).json();
      expect(reopened.attempt).toBe(2);
      expect(reopened.max_attempts).toBe(2);
      expect(reopened.solved).toBe(false);
      expect(reopened).not.toHaveProperty('correct_answer');
      await expect(page.locator('body')).not.toContainText(fixtureAnswer);
      await expect(page.locator('body')).not.toContainText(legacyAnswer);
    } finally {
      await server.close();
    }
  });
}

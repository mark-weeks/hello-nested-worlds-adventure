// M4: a real heartbeat in a saturated world, real clients and persisted restart.
import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '../..');
const python = process.env.ENFOLDED_PYTHON || 'python';
test.use({ viewport: { width: 1440, height: 1100 } });

async function serve(db) {
  const child = spawn(python, ['-u', '-c', `
import sys, threading, json, random
from pathlib import Path
from unittest.mock import patch
import persistence
persistence._DB_PATH = Path(sys.argv[1])
from server import _Handler, _ThreadedServer, heartbeat
from multiverse import store
from causality.staging import drain_due_hops
# Keep this real-server fixture runnable with CI's runtime-only installation.
class Steady(random.Random):
    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.5

def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)

root = store.world_tree(382)
nodes = list(walk(root))
target = root.children[0].children[0]
if persistence.load_agent_memory('Tessera', 382) is None:
    persistence.save_agent_memory('Tessera', 382, [n.name for n in nodes], [])
    with persistence.transaction() as conn:
        conn.executemany('INSERT INTO agent_attention VALUES (382,?, ?,0,0)',
                         [('Tessera', n.name) for n in nodes if n.name != target.name])
server = _ThreadedServer(('127.0.0.1', 0), _Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(server.server_address[1], flush=True)
for command in sys.stdin:
    if command.strip() == 'tick':
        previous = nodes[nodes.index(target)-1].name
        persistence.save_agent_scan_cursor('Tessera',382,previous)
        with patch.object(heartbeat, 'WANDERER_ROSTER', ('Tessera',)), patch.object(heartbeat, '_drop_in', return_value=target):
            result = heartbeat.run_tick(382, Steady(1), max_nodes=1, pace=0)
    else:
        with persistence._connect() as conn:
            conn.execute("UPDATE causal_queue SET due_at='2000-01-01' WHERE status='pending'")
            if command.strip() == 'land':
                conn.execute("UPDATE verb_maturation SET due_at='2000-01-01' WHERE status='pending'")
        result = {'hops': drain_due_hops(world_seed=382, broadcaster_batch=heartbeat._pump_broadcast_batch)}
        if command.strip() == 'land':
            result['landed'] = heartbeat.drain_matured_verbs(world_seed=382)
    print(json.dumps(result), flush=True)
`, db], { cwd: repo, env: { ...process.env,
    NESTED_WORLDS_CANONICAL_SEED: '382', NESTED_WORLDS_MATURATION_SCALE: '1',
    NESTED_WORLDS_DISABLE_AI: '1', NESTED_WORLDS_DISABLE_IMAGES: '1' },
    stdio: ['pipe', 'pipe', 'pipe'] });
  let errors = '';
  child.stderr.on('data', data => { errors += data; });
  const port = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', code => reject(new Error(`server ${code}: ${errors}`)));
    child.stdout.once('data', data => resolve(Number(String(data).trim())));
  });
  const command = value => new Promise(resolve => {
    child.stdout.once('data', data => resolve(JSON.parse(String(data).trim())));
    child.stdin.write(value + '\n');
  });
  return { child, command, url: `http://127.0.0.1:${port}` };
}
async function stop(server) {
  if (server?.child.exitCode === null) {
    const exited = once(server.child, 'exit');
    server.child.kill('SIGKILL');
    await exited;
  }
}

for (const route of ['/', '/app']) {
  test(`${route} familiar inhabitant action keeps response ownership and survives restart`, async ({ page, request }) => {
    const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-m4-browser-'));
    const db = path.join(directory, 'world.db');
    let server;
    try {
      server = await serve(db);
      const world = await (await request.get(server.url + '/world?depth=3')).json();
      const target = world.world.children[0].children[0];
      await page.addInitScript(node => {
        if (location.protocol !== 'http:') return;
        localStorage.setItem('nw_seen_intro', '1');
        localStorage.setItem('nw_player_name', 'M4Visitor');
        localStorage.setItem('nw_last_node', node);
        sessionStorage.setItem('nw_sound_invited', '1');
      }, target.name);
      const notices = [];
      page.on('websocket', socket => socket.on('framereceived', ({ payload }) => {
        try { notices.push(JSON.parse(payload)); } catch { /* transport frame */ }
      }));
      await page.goto(server.url + route);
      await page.waitForLoadState('networkidle');
      if (route === '/') await page.locator('#btn-act').click();
      else await page.getByRole('button', { name: 'Kindle', exact: true }).click();
      const [response] = await Promise.all([
        page.waitForResponse(r => new URL(r.url()).pathname === '/act'),
        page.getByRole('button', { name: 'Kindle this Galaxy', exact: true }).click(),
      ]);
      const own = await response.json();
      const personal = route === '/' ? page.locator('#act-response') : page.getByText(own.flavor, { exact: true });
      await expect(personal).toHaveText(own.flavor);
      await page.waitForLoadState('networkidle');
      const reads = { world: 0, node: 0, history: 0 };
      page.on('request', req => {
        const endpoint = new URL(req.url()).pathname.slice(1);
        if (endpoint in reads) reads[endpoint]++;
      });
      const tick = await server.command('tick');
      expect(tick.fresh).toBe(0);
      expect(tick.act).toContain('kindled');
      await expect.poll(() => notices.find(m => m.type === 'agent_done')).toBeTruthy();
      const done = notices.find(m => m.type === 'agent_done');
      expect(done.nodes_visited).toBe(tick.work.visited);
      expect(done.nodes_visited).toBeGreaterThan(0);
      const visitText = route === '/' ? `Agent: ${done.nodes_visited} nodes from`
        : `Agent visited ${done.nodes_visited} nodes from`;
      await expect(page.getByText(visitText, { exact: false }).first()).toBeVisible();
      await expect.poll(() => notices.find(m => m.type === 'scale_act' && m.actor === 'Tessera')).toBeTruthy();
      const accepted = notices.find(m => m.type === 'scale_act' && m.actor === 'Tessera');
      expect(accepted.flavor).toBeUndefined();
      expect(accepted.narration.phase).toBe('accepted');
      await expect(page.getByText(accepted.narration.text, { exact: false }).first()).toBeVisible();
      await expect(personal).toHaveText(own.flavor);
      await server.command('ripples');
      await expect.poll(() => notices.find(m => m.narration?.phase === 'arrival' &&
        m.narration.source_event_id === accepted.event_id)).toBeTruthy();
      expect(reads.world).toBe(0);
      expect(reads.history).toBe(0);
      expect(reads.node).toBeLessThanOrEqual(1);

      // Miss the terminal notice and kill the process with accepted work.
      await page.goto('about:blank');
      await stop(server);
      server = await serve(db);
      expect((await server.command('tick')).act).toBeNull(); // durable opportunity fence
      expect((await server.command('land')).landed).toBe(2); // human + inhabitant
      const history = await (await request.get(`${server.url}/history?node_name=${encodeURIComponent(target.name)}`)).json();
      const outcome = history.mutations.find(m => m.type === 'SCALE_ACT_MATURED' &&
        m.narration.source_event_id === accepted.event_id);
      expect(outcome.narration.actor_label).toBe('Tessera');
      await page.goto(server.url + route);
      await expect(page.getByText(outcome.narration.text, { exact: false }).first()).toBeVisible();
      const node = await (await request.get(`${server.url}/node?node_name=${encodeURIComponent(target.name)}`)).json();
      expect(node.node.pending_actions).toEqual([]);
      expect(node.node.properties.star_density).toBe(459);
      await page.screenshot({ path: path.join(tmpdir(), `enfolded-m4-${route === '/' ? 'explorer' : 'scene'}.png`) });
    } finally {
      await page.goto('about:blank').catch(() => {});
      await stop(server);
      await rm(directory, { recursive: true, force: true });
    }
  });
}

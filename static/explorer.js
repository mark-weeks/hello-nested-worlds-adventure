// ── Beta invite-key plumbing ───────────────────────────────────────────────
// The static shell loads ungated; every data / WS call is gated behind the
// invite key. Read `?key=` from the URL, stash it, and forward it on every
// request. No-op when the gate is off (no key present).
const _betaParams = new URLSearchParams(location.search);
if (_betaParams.get('key')) localStorage.setItem('nw_beta_key', _betaParams.get('key'));
function betaKey() { return localStorage.getItem('nw_beta_key') || _betaParams.get('key') || ''; }
function withKey(url) {
  const k = betaKey();
  if (!k) return url;
  return url + (url.includes('?') ? '&' : '?') + 'key=' + encodeURIComponent(k);
}

const LEVEL_COLORS = {
  Multiverse: '#dde8ff', Universe: '#00ccff', Galaxy: '#4488ff',
  'Planetary System': '#cc55ff', Planet: '#33ee88', Region: '#ffcc33',
  Room: '#ff4455', Object: '#909090', Molecule: '#33cccc',
  Atom: '#4466ff', SubatomicParticle: '#cc33ff',
};
const LEVEL_R = {
  Multiverse: 18, Universe: 14, Galaxy: 12, 'Planetary System': 11,
  Planet: 10, Region: 9, Room: 8, Object: 7, Molecule: 6,
  Atom: 5, SubatomicParticle: 4,
};

let selected    = null;
let worldParams = { seed: 42, depth: 6, min_b: 1, max_b: 3 };
let puzzleState = { attempt: 0, maxAttempts: 3, solved: false };
let observeES   = null;
let nodeG       = null;
let hierLayout  = null;   // the laid-out d3 hierarchy, for centring on a node

// ── Non-linear entry (drop-in + resume) ────────────────────────────────────
// There is no "start at the root": a first-time player is dropped in at a node
// in the middle of the world (one with places to go up AND down), seeded from
// their name so it's stable; a returning player resumes their last node. Both
// persist across sessions via localStorage.
const LAST_NODE_KEY  = 'nw_last_node';
const LAST_WORLD_KEY = 'nw_last_world';

function _entryHash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function findNodeByName(node, name) {
  if (!node) return null;
  if (node.name === name) return node;
  for (const c of node.children || []) {
    const hit = findNodeByName(c, name);
    if (hit) return hit;
  }
  return null;
}

function dropInNode(root, key) {
  const mids = [], nonRoot = [];
  (function walk(n, depth) {
    if (depth > 0) {
      nonRoot.push(n);
      if (n.children && n.children.length) mids.push(n);
    }
    for (const c of n.children || []) walk(c, depth + 1);
  })(root, 0);
  const pool = mids.length ? mids : (nonRoot.length ? nonRoot : [root]);
  return pool[_entryHash(key || 'anon') % pool.length];
}

function resolveEntryNode(root) {
  const saved = localStorage.getItem(LAST_NODE_KEY);
  if (saved) {
    const hit = findNodeByName(root, saved);
    if (hit) return hit;              // resume where the player left off
  }
  return dropInNode(root, playerName); // first-time drop-in (or saved world gone)
}

// ── Cross-device resume ─────────────────────────────────────────────────────
// localStorage remembers the last node per browser; the server remembers it per
// invite key, so the position follows the player across devices. On boot we pull
// the server copy (if this browser carries a per-user key) into localStorage so
// the existing resume path uses it; on every move we mirror the new position
// back. Shared-key / no-key sessions have no server row — the fetch returns null
// and we silently keep the local cache.
async function hydrateFromServer() {
  if (!betaKey()) return;
  try {
    const res = await fetch(withKey('/position'));
    if (!res.ok) return;
    const { position } = await res.json();
    if (!position || !position.node) return;
    localStorage.setItem(LAST_NODE_KEY, position.node);
    localStorage.setItem(LAST_WORLD_KEY, JSON.stringify({
      seed:  position.seed,        depth: position.depth,
      min_b: position.min_breadth, max_b: position.max_breadth,
    }));
  } catch (_) { /* offline or gate off — keep whatever this browser cached */ }
}

function savePositionToServer(name) {
  if (!betaKey()) return;
  const { seed, depth, min_b, max_b } = worldParams;
  try {
    fetch(withKey('/position'), {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ node: name, seed, depth,
                                min_breadth: min_b, max_breadth: max_b }),
    }).catch(() => {});           // fire-and-forget; localStorage is the backstop
  } catch (_) {}
}

const container = document.getElementById('graph');
const svg       = d3.select(container).append('svg');
const root_g    = svg.append('g');
const zoom      = d3.zoom().scaleExtent([0.05, 6]).on('zoom', e => root_g.attr('transform', e.transform));
svg.call(zoom);

function setStatus(msg) { document.getElementById('status').textContent = msg; }

function setMode(mode) {
  ['speak', 'observe', 'puzzle'].forEach(m => {
    document.getElementById('panel-' + m).classList.toggle('active', m === mode);
    document.getElementById('btn-'   + m).classList.toggle('active', m === mode);
  });
  if (mode === 'observe' && observeES) { observeES.close(); observeES = null; }
}

async function loadWorld() {
  worldParams = {
    seed:  +document.getElementById('seed').value,
    depth: +document.getElementById('depth').value,
    min_b: +document.getElementById('min_b').value,
    max_b: +document.getElementById('max_b').value,
  };
  // Remember the world so a returning player resumes in the same one (their
  // saved node only exists here).
  try { localStorage.setItem(LAST_WORLD_KEY, JSON.stringify(worldParams)); } catch (_) {}
  document.getElementById('gen-btn').disabled = true;
  setStatus('Generating world…');
  try {
    const { seed, depth, min_b, max_b } = worldParams;
    const res  = await fetch(withKey(`/world?seed=${seed}&depth=${depth}&min_breadth=${min_b}&max_breadth=${max_b}`));
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setStatus(`${data.node_count} nodes · seed ${seed} · depth ${depth}`);
    renderTree(data.world);
    if (playerName) wsConnect(seed);
    loadHistoryFeed(seed);
  } catch (e) {
    setStatus('Error: ' + e.message);
  } finally {
    document.getElementById('gen-btn').disabled = false;
  }
}

// The single most salient trait of a node, as a marker color — or null for
// unremarkable places. Priority order and colors mirror the React client's
// passageBadges (frontend/src/badges.js).
function nodeMark(data) {
  const p = data.properties || {};
  if (typeof p.danger_level === 'number' && p.danger_level >= 7) return '#f05a5a';
  if (p.condition === 'corrupted') return '#c88af0';
  if (p.disturbed) return '#ff8a4a';
  if (p.stabilized) return '#4af0c8';
  if ((data.ripple_score || 0) >= 0.3) return '#a078ff';
  return null;
}

function renderTree(worldRoot) {
  root_g.selectAll('*').remove();
  nodeG   = null;
  players = {};
  renderPlayers();

  const hier   = d3.hierarchy(worldRoot, d => d.children?.length ? d.children : null);
  const leaves = hier.leaves().length;
  const rowH   = Math.max(20, Math.min(40, (container.clientHeight - 60) / leaves));
  d3.tree().nodeSize([rowH, 200])(hier);
  hierLayout = hier;

  root_g.append('g').selectAll('path')
    .data(hier.links()).join('path')
    .attr('class', 'link')
    .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

  nodeG = root_g.append('g').selectAll('g')
    .data(hier.descendants()).join('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${d.y},${d.x})`)
    .on('click', (_, d) => selectNode(d.data));

  nodeG.append('circle')
    .attr('r',            d => LEVEL_R[d.data.level] || 7)
    .attr('fill',         d => LEVEL_COLORS[d.data.level] || '#666')
    .attr('fill-opacity', 0.8)
    .attr('stroke',       d => LEVEL_COLORS[d.data.level] || '#666')
    .attr('stroke-opacity', 0.5);

  // Affordance rings: places worth a detour — danger, corruption, unrest,
  // stabilization, accumulated causal pressure — carry a persistent colored
  // ring, so the map itself shows where the world has been lived in.
  // (Mirrors frontend/src/badges.js; parity is covered by the JS tests.)
  nodeG.filter(d => nodeMark(d.data) !== null)
    .append('circle')
    .attr('class',        'affordance-ring')
    .attr('r',            d => (LEVEL_R[d.data.level] || 7) + 4)
    .attr('fill',         'none')
    .attr('stroke',       d => nodeMark(d.data))
    .attr('stroke-width', 1.2)
    .attr('stroke-opacity', 0.85)
    .attr('pointer-events', 'none');

  nodeG.append('text')
    .attr('dy',               d => d.children ? '-14px' : '0')
    .attr('dx',               d => d.children ? '0' : '14px')
    .attr('text-anchor',      d => d.children ? 'middle' : 'start')
    .attr('dominant-baseline',d => d.children ? 'auto' : 'middle')
    .text(d => d.data.name);

  fitView();
  // Non-linear entry: resume the player's last node, or drop a first-timer into
  // the middle of the world — not always the root. Centre the view on it.
  const entry = resolveEntryNode(worldRoot);
  selectNode(entry);
  if (entry.id !== worldRoot.id) centerOnNode(entry);
}

// ── The world's past, visible on arrival ───────────────────────────────────
// Backfill recent mutations into the event feed so a new arrival sees a
// world already in motion — who solved what, which agents passed through,
// where danger stirred — instead of an empty feed.

function describeMutation(m) {
  const when = (m.at || '').slice(0, 10);
  const who = m.player || (m.data && m.data.agent) || 'someone';
  switch (m.type) {
    case 'PUZZLE_SOLVED': return `${when} · ${who} solved a puzzle at ${m.node}`;
    case 'PUZZLE_FAILED': return `${when} · a puzzle resisted ${who} at ${m.node}`;
    case 'PLAYER_SPEAK':  return `${when} · ${who} spoke with ${m.node}`;
    case 'PLAYER_CHAT':   return `${when} · ${who} said something at ${m.node}`;
    case 'AGENT_VISIT':   return `${when} · ${who} passed through ${m.node}`;
    case 'DANGER_ALERT':  return `${when} · danger stirred at ${m.node}`;
    default:              return `${when} · something happened at ${m.node}`;
  }
}

async function loadHistoryFeed(seed) {
  try {
    const res = await fetch(withKey(`/history?seed=${seed}`));
    if (!res.ok) return;
    const { mutations } = await res.json();
    // Oldest first, so the newest history line ends up nearest the live feed.
    for (const m of (mutations || []).slice(0, 12).reverse()) {
      pushFeed(`◦ ${describeMutation(m)}`, { cls: 'history-msg' });
    }
  } catch (_) { /* history is a garnish — never block the load on it */ }
}

function centerOnNode(nodeData) {
  if (!hierLayout) return;
  const d = hierLayout.descendants().find(n => n.data.id === nodeData.id
                                           || n.data.name === nodeData.name);
  if (!d) return;
  const W = container.clientWidth, H = container.clientHeight, scale = 0.8;
  // The tree is laid out horizontally: a node sits at screen point (d.y, d.x).
  svg.transition().duration(600).call(
    zoom.transform,
    d3.zoomIdentity.translate(W / 2 - d.y * scale, H / 2 - d.x * scale).scale(scale),
  );
}

function fitView() {
  const b = root_g.node().getBBox();
  if (!b.width || !b.height) return;
  const W = container.clientWidth, H = container.clientHeight, pad = 60;
  const scale = Math.min((W - pad) / b.width, (H - pad) / b.height, 1);
  svg.call(zoom.transform, d3.zoomIdentity
    .translate((W - b.width * scale) / 2 - b.x * scale,
               (H - b.height * scale) / 2 - b.y * scale)
    .scale(scale));
}

function selectNode(data) {
  selected = data;
  const color = LEVEL_COLORS[data.level] || '#3a8eff';

  root_g.selectAll('.node').classed('selected', d => d.data.id === data.id);
  root_g.selectAll('.node circle')
    .attr('fill-opacity',   d => d.data.id === data.id ? 1.0 : 0.8)
    .attr('stroke-opacity', d => d.data.id === data.id ? 1.0 : 0.5);

  document.getElementById('node-level').textContent = data.level;
  document.getElementById('node-level').style.color = color;
  document.getElementById('node-name').textContent  = data.name;
  document.getElementById('node-name').style.color  = color;
  let propsHtml = Object.entries(data.properties || {}).map(
    ([k, v]) => `<div class="prop-row"><span class="prop-key">${escHtml(String(k))}</span><span class="prop-val">${escHtml(String(v))}</span></div>`
  ).join('');
  if (data.ripple_score > 0) {
    const bars = '▮'.repeat(Math.max(1, Math.round(data.ripple_score * 8)));
    const hot = data.ripple_score >= 0.5 ? ' style="color:#c88af0"' : '';
    propsHtml += `<div class="prop-row" title="accumulated causal pressure">` +
      `<span class="prop-key">causal pressure</span>` +
      `<span class="prop-val"${hot}>${bars} ${data.ripple_score.toFixed(2)}</span></div>`;
  }
  document.getElementById('node-props').innerHTML = propsHtml;

  document.getElementById('speak-response').textContent = '';
  document.getElementById('speak-response').className = 'response-box';
  document.getElementById('observe-rows').innerHTML = '';
  document.getElementById('puzzle-content').innerHTML = '';
  loadPresences(data.name);
  puzzleState = { attempt: 0, maxAttempts: 3, solved: false };
  if (observeES) { observeES.close(); observeES = null; }

  // Remember where the player is so they resume here next session — locally for
  // this browser, and on the server so it follows them to other devices.
  localStorage.setItem(LAST_NODE_KEY, data.name);
  savePositionToServer(data.name);
  wsSend({ type: 'move', node: data.name });
}

// ── Addressable presences ───────────────────────────────────────────────────
// Agents whose traces sit in the selected node's history can be spoken to —
// "the Tessera who passed through here" — via /agent/voice, which grounds
// the reply in that agent's own persisted memory of this world.

let speakTarget = null;  // null = the node itself; otherwise an agent name

function _setSpeakTarget(name) {
  speakTarget = name;
  document.querySelectorAll('#speak-presences .presence-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.target === (name || ''));
  });
  document.getElementById('btn-do-speak').textContent =
    name ? `Speak to ${name}` : 'Speak to Node';
}

async function loadPresences(nodeName) {
  const el = document.getElementById('speak-presences');
  el.innerHTML = '';
  speakTarget = null;
  document.getElementById('btn-do-speak').textContent = 'Speak to Node';
  try {
    const res = await fetch(withKey(
      `/history?seed=${worldParams.seed}&node_name=${encodeURIComponent(nodeName)}`));
    if (!res.ok) return;
    const { mutations } = await res.json();
    const seen = new Map();
    for (const m of mutations || []) {
      const a = m.data && m.data.agent;
      if (a && !seen.has(a)) seen.set(a, (m.data && m.data.persona) || '');
    }
    if (!seen.size) return;
    const mk = (label, target) => {
      const btn = document.createElement('button');
      btn.className = 'presence-btn' + (target ? '' : ' active');
      btn.dataset.target = target || '';
      btn.textContent = label;
      btn.addEventListener('click', () => _setSpeakTarget(target));
      el.appendChild(btn);
    };
    mk('the place', null);
    let shown = 0;
    for (const [name, persona] of seen) {
      if (shown++ >= 4) break;
      mk(persona ? `${name} · ${persona}` : name, name);
    }
  } catch (_) { /* presences are a garnish */ }
}

async function speak() {
  if (!selected) { setStatus('Select a node first.'); return; }
  const message = document.getElementById('message').value.trim();
  if (!message) return;
  const box = document.getElementById('speak-response');
  box.textContent = '…';
  box.className = 'response-box dim';
  setStatus('Awaiting response…');
  try {
    const addressingAgent = !!speakTarget;
    const res  = await fetch(withKey(addressingAgent ? '/agent/voice' : '/speak'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(addressingAgent
        ? { agent_name: speakTarget, node_name: selected.name, message,
            seed: worldParams.seed }
        : { node_name: selected.name, message,
            seed: worldParams.seed, player_name: playerName }),
    });
    const data = await res.json();
    box.textContent = data.error || data.response;
    box.className   = data.error ? 'response-box error' : 'response-box';
    setStatus('Ready');
  } catch (e) {
    box.textContent = 'Network error: ' + e.message;
    box.className   = 'response-box error';
    setStatus('Error');
  }
}

function observe() {
  if (!selected) { setStatus('Select a node first.'); return; }
  if (observeES) { observeES.close(); observeES = null; }

  document.getElementById('observe-rows').innerHTML = '';
  const { seed, depth, min_b, max_b } = worldParams;
  const url = `/observe?seed=${seed}&depth=${depth}&min_breadth=${min_b}&max_breadth=${max_b}&node_name=${encodeURIComponent(selected.name)}`;

  setStatus('Agent traversing…');
  observeES = new EventSource(withKey(url));

  observeES.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.done) {
      setStatus(`Observer visited ${d.nodes_visited} node(s).`);
      observeES.close();
      observeES = null;
      return;
    }
    appendObserveRow(d);
  };
  observeES.onerror = () => {
    setStatus('Observe stream ended.');
    observeES.close();
    observeES = null;
  };
}

function appendObserveRow({ node, level, kind, strength }) {
  const color   = LEVEL_COLORS[level] || '#666';
  const pct     = Math.round(strength * 100);
  const kindFmt = kind.replace(/_/g, ' ').toLowerCase();
  const row     = document.createElement('div');
  row.className = 'obs-row';
  row.innerHTML = `
    <span class="obs-name"  style="color:${color}">${escHtml(node)}</span>
    <span class="obs-event">${escHtml(kindFmt)}</span>
    <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:${color}"></span></span>
    <span class="obs-strength">${strength.toFixed(2)}</span>`;
  const log = document.getElementById('observe-rows');
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

async function fetchPuzzle() {
  if (!selected) { setStatus('Select a node first.'); return; }
  const { seed, depth, min_b, max_b } = worldParams;
  const url = `/puzzle?seed=${seed}&depth=${depth}&min_breadth=${min_b}&max_breadth=${max_b}&node_name=${encodeURIComponent(selected.name)}`;
  setStatus('Searching for puzzle…');
  try {
    const res  = await fetch(withKey(url));
    const data = await res.json();
    if (!data.found) {
      document.getElementById('puzzle-content').innerHTML =
        '<div style="color:#2a4060;font-size:11px;margin-top:8px">No puzzle found in this subtree.</div>';
      setStatus('Ready');
      return;
    }
    puzzleState = { attempt: 0, maxAttempts: data.max_attempts, solved: false,
                    name: data.name, kind: data.kind };
    renderPuzzle(data);
    setStatus('Ready');
  } catch (e) {
    setStatus('Error: ' + e.message);
  }
}

function _diffStars(n) {
  // 1..4 filled stars; difficulty is a per-node property, not a scale ramp.
  const d = Math.max(1, Math.min(4, n || 2));
  return '★'.repeat(d) + '☆'.repeat(4 - d);
}

function renderPuzzle(data) {
  const diffLabels = { 1: 'gentle', 2: 'moderate', 3: 'tricky', 4: 'hard' };
  const diff = data.difficulty || 2;
  document.getElementById('puzzle-content').innerHTML = `
    <div class="puzzle-kind">${escHtml(data.kind.replace(/_/g, ' '))}
      <span class="puzzle-diff" title="difficulty: ${diffLabels[diff]}">${_diffStars(diff)}</span>
    </div>
    <div class="puzzle-name">${escHtml(data.name)}</div>
    <div class="puzzle-prompt">${escHtml(data.prompt)}</div>
    <div class="attempt-info" id="attempt-info">
      ${data.max_attempts} attempt${data.max_attempts !== 1 ? 's' : ''} allowed
    </div>
    <input class="puzzle-input" id="puzzle-answer" type="text" placeholder="Your answer…" autocomplete="off">
    <button id="puzzle-submit">Submit</button>
    <div class="puzzle-result" id="puzzle-result"></div>
    <div class="puzzle-hint"   id="puzzle-hint"></div>`;
  document.getElementById('puzzle-answer').addEventListener('keydown', e => {
    if (e.key === 'Enter') submitAnswer();
  });
  document.getElementById('puzzle-submit').addEventListener('click', submitAnswer);
  document.getElementById('puzzle-answer').focus();
}

async function submitAnswer() {
  if (puzzleState.solved) return;
  const answer = (document.getElementById('puzzle-answer')?.value || '').trim();
  if (!answer) return;

  const { seed, depth, min_b, max_b } = worldParams;
  try {
    const res  = await fetch(withKey('/puzzle/attempt'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, depth, min_breadth: min_b, max_breadth: max_b,
                             node_name: selected.name, answer,
                             player_name: playerName }),
    });
    const data = await res.json();
    const resultEl = document.getElementById('puzzle-result');
    const hintEl   = document.getElementById('puzzle-hint');
    const infoEl   = document.getElementById('attempt-info');

    // Attempts pool across the whole room (co-op), so the server's count is
    // the truth — a local counter drifts the moment anyone else guesses.
    puzzleState.attempt     = data.attempt ?? (puzzleState.attempt + 1);
    puzzleState.maxAttempts = data.max_attempts ?? puzzleState.maxAttempts;

    if (data.correct) {
      puzzleState.solved = true;
      resultEl.textContent = 'Correct.';
      resultEl.className   = 'puzzle-result correct';
      hintEl.textContent   = '';
      document.getElementById('puzzle-answer').disabled = true;
    } else if (data.result === 'FAILED') {
      resultEl.textContent = `Failed. The answer was: ${data.correct_answer}`;
      resultEl.className   = 'puzzle-result failed';
      hintEl.textContent   = '';
      document.getElementById('puzzle-answer').disabled = true;
    } else {
      const remaining = Math.max(0, puzzleState.maxAttempts - puzzleState.attempt);
      resultEl.textContent = 'Wrong.';
      resultEl.className   = 'puzzle-result wrong';
      hintEl.textContent   = data.hint ? `Hint: ${data.hint}` : '';
      infoEl.textContent   = `${remaining} attempt${remaining !== 1 ? 's' : ''} remaining`;
    }
  } catch (e) {
    setStatus('Error: ' + e.message);
  }
}

let playerName  = localStorage.getItem('nw_player_name') || _betaParams.get('name') || null;
let ws          = null;
let mySessionId = null;
let players     = {};
let colorIdx    = 0;

const PLAYER_COLORS = ['#ff6b6b','#ffd93d','#6bcb77','#4d96ff','#ff9ff3','#ff9f43','#54a0ff','#a29bfe'];
const eventFeed = [];

function showJoinModal() {
  document.getElementById('join-modal').classList.add('visible');
  setTimeout(() => document.getElementById('player-name-input').focus(), 50);
}

function hideJoinModal() {
  document.getElementById('join-modal').classList.remove('visible');
}

function joinModal() {
  const input = document.getElementById('player-name-input').value.trim();
  if (!input) return;
  playerName = input;
  localStorage.setItem('nw_player_name', playerName);
  hideJoinModal();
  loadWorld();
}

function wsConnect(seed) {
  if (ws) { ws.close(); ws = null; }
  players  = {};
  colorIdx = 0;
  renderPlayers();
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url   = withKey(`${proto}//${window.location.host}/ws?seed=${seed}&name=${encodeURIComponent(playerName)}`);
  try { ws = new WebSocket(url); } catch (_) { return; }
  // Announce our current position on (re)connect so others see us where we
  // actually are — including the initial drop-in / resume node.
  ws.onopen    = () => { if (selected) wsSend({ type: 'move', node: selected.name }); };
  ws.onmessage = e => { try { handleWsMsg(JSON.parse(e.data)); } catch (_) {} };
  ws.onclose   = () => { ws = null; };
  ws.onerror   = () => {};
}

function wsSend(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function assignColor() {
  return PLAYER_COLORS[(colorIdx++) % PLAYER_COLORS.length];
}

function handleWsMsg(msg) {
  switch (msg.type) {
    case 'welcome':
      mySessionId = msg.session_id;
      players = {};
      colorIdx = 0;
      for (const p of (msg.players || [])) {
        if (p.session_id !== mySessionId)
          players[p.session_id] = { name: p.name, node: p.node, color: assignColor() };
      }
      renderPlayers();
      updatePresenceRings();
      break;
    case 'player_join':
      if (msg.session_id !== mySessionId) {
        players[msg.session_id] = { name: msg.name, node: '', color: assignColor() };
        pushFeed(`${msg.name} joined`);
        renderPlayers();
        updatePresenceRings();
      }
      break;
    case 'player_leave':
      if (players[msg.session_id]) {
        pushFeed(`${players[msg.session_id].name} left`);
        delete players[msg.session_id];
        renderPlayers();
        updatePresenceRings();
      }
      break;
    case 'player_move':
      if (players[msg.session_id]) {
        players[msg.session_id].node = msg.node;
        renderPlayers();
        updatePresenceRings();
      }
      break;
    case 'puzzle_solved': {
      const others = (msg.contributors || []).filter(c => c !== msg.solver);
      const credit = others.length ? ` (with ${others.join(', ')})` : '';
      const by = msg.solver ? ` by ${msg.solver}${credit}` : '';
      pushFeed(`Puzzle solved: ${msg.puzzle} @ ${msg.node}${by}`);
      break;
    }
    case 'agent_done':
      pushFeed(`Agent: ${msg.nodes_visited} nodes from ${msg.node}`);
      break;
    case 'chat': {
      const nameHtml = `<span class="chat-name">${escHtml(msg.name)}</span>`;
      pushFeed(`${nameHtml} ${escHtml(msg.text)}`, { cls: 'chat-msg', html: true });
      break;
    }
    case 'causal_event': {
      const kindFmt = msg.kind.replace(/_/g, ' ').toLowerCase();
      pushFeed(`↯ ${kindFmt} · ${msg.node} ×${msg.strength.toFixed(2)}`);
      flashNode(msg.node, msg.strength);
      break;
    }
    case 'agent_encounter':
      pushFeed(`⚡ ${escHtml(msg.agent1)} meets ${escHtml(msg.agent2)} @ ${escHtml(msg.node)}`);
      flashNode(msg.node, 0.9);
      break;
  }
}

function flashNode(nodeName, strength) {
  if (!nodeG) return;
  const target = nodeG.filter(d => d.data.name === nodeName);
  if (target.empty()) return;
  const datum   = target.datum();
  const baseR   = LEVEL_R[datum.data.level] || 7;
  const color   = LEVEL_COLORS[datum.data.level] || '#3a8eff';
  const peakR   = baseR + Math.round(strength * 28);
  target.append('circle')
    .attr('r',              baseR)
    .attr('fill',           'none')
    .attr('stroke',         color)
    .attr('stroke-opacity', Math.min(strength + 0.2, 1))
    .attr('stroke-width',   2)
    .attr('pointer-events', 'none')
    .transition().duration(1400).ease(d3.easeCubicOut)
    .attr('r',              peakR)
    .attr('stroke-opacity', 0)
    .remove();
}

function renderPlayers() {
  const el   = document.getElementById('players-list');
  const list = Object.values(players);
  if (!list.length) {
    el.innerHTML = '<div style="color:#2a4060;font-size:10px">No other explorers online</div>';
  } else {
    el.innerHTML = list.map(p =>
      `<div class="player-row">` +
      `<span class="player-dot" style="background:${p.color}"></span>` +
      `<span class="player-name">${escHtml(p.name)}</span>` +
      `<span class="player-node">${escHtml(p.node || '—')}</span>` +
      `</div>`
    ).join('');
  }
}

function pushFeed(text, { cls = '', html = false } = {}) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const content = html ? text : escHtml(text);
  eventFeed.unshift({ content, time, cls });
  if (eventFeed.length > 20) eventFeed.pop();
  const el = document.getElementById('event-feed');
  el.innerHTML = eventFeed.map(e =>
    `<div class="feed-item ${escHtml(e.cls || '')}"><span class="feed-time">${e.time}</span>${e.content}</div>`
  ).join('');
}

function sendChat() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    pushFeed('Not connected — generate a world first.');
    return;
  }
  wsSend({ type: 'chat', text });
  input.value = '';
}

function updatePresenceRings() {
  if (!nodeG) return;
  nodeG.selectAll('.presence-ring').remove();
  const nodeColors = {};
  for (const p of Object.values(players)) {
    if (!p.node) continue;
    if (!nodeColors[p.node]) nodeColors[p.node] = [];
    nodeColors[p.node].push(p.color);
  }
  for (const [nodeName, colors] of Object.entries(nodeColors)) {
    const group = nodeG.filter(d => d.data.name === nodeName);
    colors.forEach((color, i) => {
      group.insert('circle', ':first-child')
        .attr('class',          'presence-ring')
        .attr('r',              d => (LEVEL_R[d.data.level] || 7) + 6 + i * 5)
        .attr('fill',           'none')
        .attr('stroke',         color)
        .attr('stroke-width',   1.5)
        .attr('stroke-dasharray', '4,3')
        .attr('opacity',        0.8)
        .attr('pointer-events', 'none');
    });
  }
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Wire up event listeners (replaces inline onclick/onkeydown handlers) ───
document.getElementById('btn-join').addEventListener('click', joinModal);
document.getElementById('player-name-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') joinModal();
});
document.getElementById('gen-btn').addEventListener('click', loadWorld);
document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendChat();
});
document.getElementById('chat-btn').addEventListener('click', sendChat);
document.getElementById('btn-speak'  ).addEventListener('click', () => setMode('speak'));
document.getElementById('btn-observe').addEventListener('click', () => setMode('observe'));
document.getElementById('btn-puzzle' ).addEventListener('click', () => setMode('puzzle'));
document.getElementById('btn-do-speak'  ).addEventListener('click', speak);
document.getElementById('btn-do-observe').addEventListener('click', observe);
document.getElementById('btn-do-puzzle' ).addEventListener('click', fetchPuzzle);
document.getElementById('message').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); speak(); }
});

// ── First-run intro ────────────────────────────────────────────────────────
// Invited testers arrive with ?name= in the URL and skip the join modal, so
// the onboarding can't live there — it runs here, once per browser, ahead of
// either boot path (auto-join for named users, join modal for anonymous ones).
const INTRO_SEEN = 'nw_seen_intro';

function restoreWorldInputs() {
  // A returning player resumes in the world they left off in, so pre-fill the
  // generator inputs from the last one before the first load. First-timers keep
  // the defaults.
  let saved;
  try { saved = JSON.parse(localStorage.getItem(LAST_WORLD_KEY)); } catch (_) { saved = null; }
  if (!saved) return;
  const set = (id, v) => { const el = document.getElementById(id); if (el && Number.isFinite(+v)) el.value = v; };
  set('seed', saved.seed); set('depth', saved.depth);
  set('min_b', saved.min_b); set('max_b', saved.max_b);
}

async function boot() {
  await hydrateFromServer();   // cross-device resume takes precedence over the local cache
  restoreWorldInputs();
  if (playerName) {
    loadWorld();
  } else {
    showJoinModal();
  }
}

function beginFromIntro() {
  localStorage.setItem(INTRO_SEEN, '1');
  document.getElementById('intro-modal').classList.remove('visible');
  boot();
}

document.getElementById('btn-begin').addEventListener('click', beginFromIntro);

if (!localStorage.getItem(INTRO_SEEN)) {
  document.getElementById('intro-modal').classList.add('visible');
} else {
  boot();
}

(() => {
  const seq = [38,38,40,40,37,39,37,39,66,65];
  const buf = [];
  const egg   = document.getElementById('egg');
  const close = document.getElementById('close');
  const open  = () => { if (egg) egg.style.display = 'flex'; };
  const hide  = () => { if (egg) egg.style.display = 'none'; };
  window.addEventListener('keydown', e => {
    buf.push(e.keyCode);
    if (buf.length > seq.length) buf.shift();
    if (seq.every((v,i) => buf[i] === v)) open();
  });
  if (egg)   egg.addEventListener('click',   e => { if (e.target === egg) hide(); });
  if (close) close.addEventListener('click', hide);
})();

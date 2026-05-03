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
  document.getElementById('gen-btn').disabled = true;
  setStatus('Generating world…');
  try {
    const { seed, depth, min_b, max_b } = worldParams;
    const res  = await fetch(`/world?seed=${seed}&depth=${depth}&min_breadth=${min_b}&max_breadth=${max_b}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setStatus(`${data.node_count} nodes · seed ${seed} · depth ${depth}`);
    renderTree(data.world);
    if (playerName) wsConnect(seed);
  } catch (e) {
    setStatus('Error: ' + e.message);
  } finally {
    document.getElementById('gen-btn').disabled = false;
  }
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

  nodeG.append('text')
    .attr('dy',               d => d.children ? '-14px' : '0')
    .attr('dx',               d => d.children ? '0' : '14px')
    .attr('text-anchor',      d => d.children ? 'middle' : 'start')
    .attr('dominant-baseline',d => d.children ? 'auto' : 'middle')
    .text(d => d.data.name);

  fitView();
  selectNode(worldRoot);
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
  document.getElementById('node-props').innerHTML = Object.entries(data.properties || {}).map(
    ([k, v]) => `<div class="prop-row"><span class="prop-key">${escHtml(String(k))}</span><span class="prop-val">${escHtml(String(v))}</span></div>`
  ).join('');

  document.getElementById('speak-response').textContent = '';
  document.getElementById('speak-response').className = 'response-box';
  document.getElementById('observe-rows').innerHTML = '';
  document.getElementById('puzzle-content').innerHTML = '';
  puzzleState = { attempt: 0, maxAttempts: 3, solved: false };
  if (observeES) { observeES.close(); observeES = null; }

  wsSend({ type: 'move', node: data.name });
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
    const res  = await fetch('/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_name: selected.name, node_level: selected.level,
                             node_properties: selected.properties || {}, message,
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
  observeES = new EventSource(url);

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
    const res  = await fetch(url);
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

function renderPuzzle(data) {
  document.getElementById('puzzle-content').innerHTML = `
    <div class="puzzle-kind">${escHtml(data.kind.replace(/_/g, ' '))}</div>
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

  puzzleState.attempt++;
  const { seed, depth, min_b, max_b } = worldParams;
  try {
    const res  = await fetch('/puzzle/attempt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, depth, min_breadth: min_b, max_breadth: max_b,
                             node_name: selected.name, answer,
                             attempt: puzzleState.attempt }),
    });
    const data = await res.json();
    const resultEl = document.getElementById('puzzle-result');
    const hintEl   = document.getElementById('puzzle-hint');
    const infoEl   = document.getElementById('attempt-info');

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
      const remaining = puzzleState.maxAttempts - puzzleState.attempt;
      resultEl.textContent = 'Wrong.';
      resultEl.className   = 'puzzle-result wrong';
      hintEl.textContent   = data.hint ? `Hint: ${data.hint}` : '';
      infoEl.textContent   = `${remaining} attempt${remaining !== 1 ? 's' : ''} remaining`;
    }
  } catch (e) {
    setStatus('Error: ' + e.message);
  }
}

let playerName  = localStorage.getItem('nw_player_name') || null;
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
  const url   = `${proto}//${window.location.host}/ws?seed=${seed}&name=${encodeURIComponent(playerName)}`;
  try { ws = new WebSocket(url); } catch (_) { return; }
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
    case 'puzzle_solved':
      pushFeed(`Puzzle solved: ${msg.puzzle} @ ${msg.node}`);
      break;
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

if (playerName) {
  loadWorld();
} else {
  showJoinModal();
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

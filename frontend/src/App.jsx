import { useState, useEffect, useCallback } from "react";
import SceneView from "./components/SceneView.jsx";
import TextPanel from "./components/TextPanel.jsx";
import useWorldSocket from "./ws.js";
import { withKey, urlName, betaKey } from "./auth.js";
import { entryPath } from "./entry.js";

const DEFAULT_SEED  = 42;
const WORLD_DEPTH   = 6;   // must match the depth used for /puzzle lookups
const MAX_EVENTS    = 40;
const MAX_TRANSIENTS = 12;
const NAME_KEY      = "nw_player_name";
const LAST_NODE_KEY = "nw_last_node";   // resume: the node the player last stood on
const LAST_SEED_KEY = "nw_last_seed";   // resume: the world it belonged to

// ── Cross-device resume ─────────────────────────────────────────────────────
// localStorage remembers the last node per browser; the server remembers it per
// invite key, so the position follows the player across devices. On mount we
// pull the server copy (if this browser carries a per-user key) into
// localStorage before the first load; on every move we mirror it back. No key /
// no server row → the local cache stands.
async function hydratePositionFromServer() {
  if (!betaKey()) return null;
  try {
    const res = await fetch(withKey("/position"));
    if (!res.ok) return null;
    const { position } = await res.json();
    if (!position || !position.node) return null;
    localStorage.setItem(LAST_NODE_KEY, position.node);
    const s = Number.isFinite(position.seed) ? position.seed : null;
    if (s != null) localStorage.setItem(LAST_SEED_KEY, String(s));
    return s;                       // seed to load, so the saved node exists in it
  } catch (_) {
    return null;                    // offline / gate off — keep the local cache
  }
}

function savePositionToServer(node, seed) {
  if (!betaKey() || !node) return;
  try {
    fetch(withKey("/position"), {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ node, seed, depth: WORLD_DEPTH }),
    }).catch(() => {});             // fire-and-forget; localStorage is the backstop
  } catch (_) {}
}

export default function App() {
  const [seed, setSeed]           = useState(() => {
    const saved = parseInt(localStorage.getItem(LAST_SEED_KEY), 10);
    return Number.isFinite(saved) ? saved : DEFAULT_SEED;
  });
  const [nodeStack, setNodeStack] = useState([]);
  const [players, setPlayers]     = useState([]);
  const [events, setEvents]       = useState([]);
  const [transients, setTransients] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [playerName, setPlayerName] = useState(() => localStorage.getItem(NAME_KEY) || urlName() || "");

  const pushEvent = useCallback((evt) => {
    setEvents(ev => [evt, ...ev].slice(0, MAX_EVENTS));
  }, []);

  // Transients are short-lived visual overlays in SceneView (ripples,
  // encounter glyphs, solve sparkles). Only the ones whose node matches
  // the currently-rendered scene are pushed; when the player navigates,
  // a separate effect drops them all so a stray ripple from the previous
  // node never bleeds into the new one.
  const pushTransient = useCallback((t) => {
    const id = (typeof crypto !== "undefined" && crypto.randomUUID)
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
    const entry = { ...t, id, startedAt: performance.now() };
    setTransients(prev => [...prev, entry].slice(-MAX_TRANSIENTS));
    setTimeout(() => {
      setTransients(prev => prev.filter(x => x.id !== id));
    }, t.duration ?? 1500);
  }, []);

  const loadWorld = useCallback((s) => {
    setLoading(true);
    setPlayers([]);
    setEvents([]);
    localStorage.setItem(LAST_SEED_KEY, String(s));
    fetch(withKey(`/world?seed=${s}&depth=${WORLD_DEPTH}`))
      .then(r => r.json())
      .then(data => {
        // Non-linear entry: resume the last node if it's in this world, else
        // drop a first-time player in at a mid-world node. The returned path is
        // the nav stack, so "back" walks the real ancestry.
        const savedNode = localStorage.getItem(LAST_NODE_KEY);
        const name = localStorage.getItem(NAME_KEY) || urlName() || "";
        setNodeStack(entryPath(data.world, savedNode, name));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const currentNodeName = nodeStack[nodeStack.length - 1]?.name;

  const { connected, sendMessage } = useWorldSocket(seed, playerName, {
    onPlayerJoin: (msg) => {
      setPlayers(p => [...p, { name: msg.name, session_id: msg.session_id, node: "" }]);
      pushEvent({ type: "system", text: `${msg.name} joined` });
    },
    onPlayerLeave: (msg) => {
      setPlayers(p => {
        const leaving = p.find(x => x.session_id === msg.session_id);
        pushEvent({ type: "system", text: `${leaving?.name ?? "Someone"} left` });
        return p.filter(x => x.session_id !== msg.session_id);
      });
    },
    onPlayerMove:   (msg) => setPlayers(p => p.map(x => x.session_id === msg.session_id ? { ...x, node: msg.node } : x)),
    onChat:         (msg) => pushEvent({ type: "chat",   name: msg.name, text: msg.text }),
    onCausalEvent:  (msg) => {
      pushEvent({ type: "causal", kind: msg.kind, node: msg.node, strength: msg.strength });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "ripple", strength: msg.strength ?? 1.0,
                        eventKind: msg.kind, duration: 1500 });
      }
    },
    onPuzzleSolved: (msg) => {
      const credit = msg.contributors?.length > 1
        ? ` (with ${msg.contributors.filter(c => c !== msg.solver).join(", ")})`
        : "";
      const by = msg.solver ? ` by ${msg.solver}${credit}` : "";
      pushEvent({ type: "puzzle", text: `Puzzle solved: ${msg.puzzle} @ ${msg.node}${by}` });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "solve", duration: 2000 });
      }
    },
    onAgentDone:      (msg) => pushEvent({ type: "system", text: `Agent visited ${msg.nodes_visited} nodes from ${msg.node}` }),
    onAgentEncounter: (msg) => {
      pushEvent({ type: "system", text: `⚡ ${msg.agent1} meets ${msg.agent2} @ ${msg.node}` });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "encounter",
                        agent1: msg.agent1, agent2: msg.agent2,
                        duration: 1800 });
      }
    },
  });

  // Mount once. First pull any server-side (cross-device) resume into
  // localStorage, then load — so the position follows the player across devices,
  // falling back to this browser's cache when there's no server row.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await hydratePositionFromServer();
      if (cancelled) return;
      if (s != null && s !== seed) setSeed(s);
      loadWorld(s != null ? s : seed);
    })();
    return () => { cancelled = true; };
  }, [loadWorld]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Broadcast our position whenever it changes or we (re)connect, so other
  // players see us where we actually are — including the initial drop-in /
  // resume node, which isn't reached through navigateTo().
  useEffect(() => {
    if (connected && currentNodeName) sendMessage({ type: "move", node: currentNodeName });
  }, [connected, currentNodeName, sendMessage]);

  // Persist the current node so a returning player resumes here next session —
  // locally for this browser, and on the server so it follows them to other
  // devices.
  useEffect(() => {
    if (currentNodeName) {
      localStorage.setItem(LAST_NODE_KEY, currentNodeName);
      savePositionToServer(currentNodeName, seed);
    }
  }, [currentNodeName, seed]);

  // Drop all transients when the player navigates — a leftover ripple from
  // the previous node is meaningless in the new scene.
  useEffect(() => { setTransients([]); }, [currentNodeName]);

  const handleLoadWorld = useCallback((s) => {
    setSeed(s);
    loadWorld(s);
  }, [loadWorld]);

  // Position is broadcast by the effect above (keyed on currentNodeName), so
  // navigation only has to update the stack — no direct send here.
  const navigateTo = useCallback((node) => {
    setNodeStack(s => [...s, node]);
  }, []);

  const navigateUp = useCallback(() => {
    setNodeStack(s => (s.length <= 1 ? s : s.slice(0, -1)));
  }, []);

  const sendChat = useCallback((text) => {
    sendMessage({ type: "chat", text });
  }, [sendMessage]);

  const currentNode = nodeStack[nodeStack.length - 1] ?? null;

  if (!playerName) {
    return <NameEntry onSubmit={(name) => { localStorage.setItem(NAME_KEY, name); setPlayerName(name); }} />;
  }

  if (loading || !currentNode) {
    return <div style={s.loading}>Generating world…</div>;
  }

  return (
    <div style={s.layout}>
      <SceneView
        node={currentNode}
        players={players}
        transients={transients}
        onNavigate={navigateTo}
        onNavigateUp={navigateUp}
        canGoUp={nodeStack.length > 1}
        seed={seed}
      />
      <TextPanel
        node={currentNode}
        players={players}
        connected={connected}
        events={events}
        seed={seed}
        depth={WORLD_DEPTH}
        playerName={playerName}
        onLoadWorld={handleLoadWorld}
        onChat={sendChat}
      />
    </div>
  );
}

function NameEntry({ onSubmit }) {
  const [value, setValue] = useState("");
  const submit = () => {
    const trimmed = value.trim().slice(0, 32);
    if (trimmed) onSubmit(trimmed);
  };
  return (
    <div style={s.nameWrap}>
      <div style={s.nameBox}>
        <div style={s.nameTitle}>Enfolded</div>
        <div style={s.nameDesc}>Choose a name for your explorer</div>
        <input
          autoFocus
          type="text"
          maxLength={32}
          placeholder="Your name"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          style={s.nameInput}
        />
        <button onClick={submit} style={s.nameButton}>Enter</button>
      </div>
    </div>
  );
}

const s = {
  layout:  { display: "flex", height: "100vh", overflow: "hidden", background: "#07080f" },
  loading: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontSize: "1.1rem", color: "#4a5580", fontFamily: "Courier New, monospace" },
  nameWrap: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#07080f", fontFamily: "Courier New, monospace" },
  nameBox: { background: "#0d1020", border: "1px solid #2a4060", padding: "32px 28px", minWidth: 320, textAlign: "center" },
  nameTitle: { fontSize: "1.1rem", color: "#3a8eff", letterSpacing: "2px", marginBottom: 8 },
  nameDesc: { fontSize: "0.85rem", color: "#6a7090", marginBottom: 18 },
  nameInput: { width: "100%", background: "#07080f", border: "1px solid #2a4060", color: "#b0bcd0", padding: "8px 10px", fontFamily: "inherit", fontSize: "0.9rem", marginBottom: 12, outline: "none" },
  nameButton: { background: "#1a3060", border: "1px solid #3a8eff", color: "#b0bcd0", padding: "8px 22px", fontFamily: "inherit", fontSize: "0.9rem", cursor: "pointer" },
};

import { useState, useEffect, useCallback } from "react";
import SceneView from "./components/SceneView.jsx";
import TextPanel from "./components/TextPanel.jsx";
import useWorldSocket from "./ws.js";
import { withKey, urlName } from "./auth.js";

const DEFAULT_SEED  = 42;
const WORLD_DEPTH   = 6;   // must match the depth used for /puzzle lookups
const MAX_EVENTS    = 40;
const MAX_TRANSIENTS = 12;
const NAME_KEY      = "nw_player_name";

export default function App() {
  const [seed, setSeed]           = useState(DEFAULT_SEED);
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
    fetch(withKey(`/world?seed=${s}&depth=${WORLD_DEPTH}`))
      .then(r => r.json())
      .then(data => { setNodeStack([data.world]); setLoading(false); })
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

  useEffect(() => { loadWorld(DEFAULT_SEED); }, [loadWorld]);

  // Drop all transients when the player navigates — a leftover ripple from
  // the previous node is meaningless in the new scene.
  useEffect(() => { setTransients([]); }, [currentNodeName]);

  const handleLoadWorld = useCallback((s) => {
    setSeed(s);
    loadWorld(s);
  }, [loadWorld]);

  const navigateTo = useCallback((node) => {
    setNodeStack(s => [...s, node]);
    sendMessage({ type: "move", node: node.name });
  }, [sendMessage]);

  const navigateUp = useCallback(() => {
    setNodeStack(s => {
      if (s.length <= 1) return s;
      const next = s.slice(0, -1);
      sendMessage({ type: "move", node: next[next.length - 1].name });
      return next;
    });
  }, [sendMessage]);

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
        <div style={s.nameTitle}>Nested Worlds</div>
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

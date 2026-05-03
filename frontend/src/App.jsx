import { useState, useEffect, useCallback } from "react";
import SceneView from "./components/SceneView.jsx";
import TextPanel from "./components/TextPanel.jsx";
import useWorldSocket from "./ws.js";

const DEFAULT_SEED = 42;
const MAX_EVENTS   = 40;

export default function App() {
  const [seed, setSeed]           = useState(DEFAULT_SEED);
  const [nodeStack, setNodeStack] = useState([]);
  const [players, setPlayers]     = useState([]);
  const [events, setEvents]       = useState([]);
  const [loading, setLoading]     = useState(true);

  const pushEvent = useCallback((evt) => {
    setEvents(ev => [evt, ...ev].slice(0, MAX_EVENTS));
  }, []);

  const loadWorld = useCallback((s) => {
    setLoading(true);
    setPlayers([]);
    setEvents([]);
    fetch(`/world?seed=${s}&depth=6`)
      .then(r => r.json())
      .then(data => { setNodeStack([data.world]); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const { connected, sendMessage } = useWorldSocket(seed, "Traveller", {
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
    onCausalEvent:  (msg) => pushEvent({ type: "causal", kind: msg.kind, node: msg.node, strength: msg.strength }),
    onPuzzleSolved: (msg) => pushEvent({ type: "puzzle", text: `Puzzle solved: ${msg.puzzle} @ ${msg.node}` }),
    onAgentDone:      (msg) => pushEvent({ type: "system", text: `Agent visited ${msg.nodes_visited} nodes from ${msg.node}` }),
    onAgentEncounter: (msg) => pushEvent({ type: "system", text: `⚡ ${msg.agent1} meets ${msg.agent2} @ ${msg.node}` }),
  });

  useEffect(() => { loadWorld(DEFAULT_SEED); }, [loadWorld]);

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

  if (loading || !currentNode) {
    return <div style={s.loading}>Generating world…</div>;
  }

  return (
    <div style={s.layout}>
      <SceneView
        node={currentNode}
        players={players}
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
        onLoadWorld={handleLoadWorld}
        onChat={sendChat}
      />
    </div>
  );
}

const s = {
  layout:  { display: "flex", height: "100vh", overflow: "hidden", background: "#07080f" },
  loading: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontSize: "1.1rem", color: "#4a5580", fontFamily: "Courier New, monospace" },
};

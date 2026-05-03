import { useState, useEffect, useCallback } from "react";
import SceneView from "./components/SceneView.jsx";
import TextPanel from "./components/TextPanel.jsx";
import useWorldSocket from "./ws.js";

const SEED = 42;

export default function App() {
  const [world, setWorld] = useState(null);
  const [currentNode, setCurrentNode] = useState(null);
  const [players, setPlayers] = useState([]);

  const { connected, sendMessage } = useWorldSocket(SEED, "Traveller", {
    onPlayerJoin: (msg) => setPlayers((p) => [...p, { name: msg.name, session_id: msg.session_id, node: "" }]),
    onPlayerLeave: (msg) => setPlayers((p) => p.filter((x) => x.session_id !== msg.session_id)),
    onPlayerMove: (msg) => setPlayers((p) => p.map((x) => x.session_id === msg.session_id ? { ...x, node: msg.node } : x)),
  });

  useEffect(() => {
    fetch(`/api/world?seed=${SEED}&depth=6`)
      .then((r) => r.json())
      .then((data) => {
        setWorld(data.world);
        setCurrentNode(data.world);
      });
  }, []);

  const navigateTo = useCallback((node) => {
    setCurrentNode(node);
    sendMessage({ type: "move", node: node.name });
  }, [sendMessage]);

  if (!world || !currentNode) {
    return <div style={styles.loading}>Loading world…</div>;
  }

  return (
    <div style={styles.layout}>
      <SceneView node={currentNode} players={players} onNavigate={navigateTo} />
      <TextPanel node={currentNode} players={players} connected={connected} />
    </div>
  );
}

const styles = {
  layout: { display: "flex", height: "100vh", overflow: "hidden" },
  loading: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontSize: "1.2rem", color: "#b0bcd0" },
};

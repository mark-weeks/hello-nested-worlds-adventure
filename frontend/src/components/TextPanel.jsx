import { useState } from "react";
import Interact from "./Interact.jsx";

export default function TextPanel({ node, players, connected, events, seed, depth, playerName, onLoadWorld, onChat }) {
  const [seedInput, setSeedInput] = useState(String(seed));
  const [chatInput, setChatInput] = useState("");

  const here = players.filter(p => p.node === node.name);

  const handleLoad = () => {
    const s = parseInt(seedInput, 10);
    if (!isNaN(s)) onLoadWorld(s);
  };

  const handleChat = () => {
    const text = chatInput.trim();
    if (!text || !connected) return;
    onChat(text);
    setChatInput("");
  };

  return (
    <div style={s.panel}>

      <div style={s.section}>
        <div style={s.label}>World</div>
        <div style={s.row}>
          <input
            style={s.seedInput}
            type="number"
            value={seedInput}
            onChange={e => setSeedInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLoad()}
          />
          <button style={s.btn} onClick={handleLoad}>Load</button>
        </div>
      </div>

      <div style={s.section}>
        <div style={s.label}>{node.level}</div>
        <div style={s.name}>{node.name}</div>
      </div>

      {Object.keys(node.properties).length > 0 && (
        <div style={s.section}>
          <div style={s.label}>Properties</div>
          {Object.entries(node.properties).map(([k, v]) => (
            <div key={k} style={s.prop}>
              <span style={s.propKey}>{k}</span>
              <span style={s.propVal}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}

      <Interact node={node} seed={seed} depth={depth} playerName={playerName} />

      {node.children.length > 0 && (
        <div style={s.section}>
          <div style={s.label}>Passages ({node.children.length})</div>
          {node.children.map(c => (
            <div key={c.id} style={s.passage}>
              → {c.name} <span style={s.passageLevel}>({c.level})</span>
            </div>
          ))}
        </div>
      )}

      {here.length > 0 && (
        <div style={s.section}>
          <div style={s.label}>Present here</div>
          {here.map(p => <div key={p.session_id} style={s.player}>◈ {p.name}</div>)}
        </div>
      )}

      <div style={s.feedSection}>
        <div style={s.label}>Events</div>
        <div style={s.feed}>
          {events.length === 0
            ? <div style={s.empty}>No events yet</div>
            : events.map((ev, i) => <EventRow key={i} ev={ev} />)
          }
        </div>
      </div>

      <div style={s.row}>
        <input
          style={s.chatInput}
          type="text"
          maxLength={256}
          placeholder={connected ? "Say something…" : "Not connected"}
          value={chatInput}
          onChange={e => setChatInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleChat()}
          disabled={!connected}
        />
        <button style={{ ...s.btn, opacity: connected ? 1 : 0.4 }} onClick={handleChat} disabled={!connected}>↵</button>
      </div>

      <div style={s.status}>
        <span style={{ color: connected ? "#4af0a0" : "#f04a4a" }}>
          {connected ? "● connected" : "○ disconnected"}
        </span>
      </div>

    </div>
  );
}

function EventRow({ ev }) {
  if (ev.type === "chat")
    return <div style={er.chat}><span style={er.name}>{ev.name}</span> {ev.text}</div>;
  if (ev.type === "causal")
    return <div style={er.causal}>↯ {ev.kind.replace(/_/g, " ").toLowerCase()} · {ev.node} ×{ev.strength?.toFixed(2)}</div>;
  if (ev.type === "puzzle")
    return <div style={er.puzzle}>{ev.text}</div>;
  return <div style={er.system}>{ev.text}</div>;
}

const s = {
  panel:       { flex: "0 0 300px", display: "flex", flexDirection: "column", padding: "16px 14px 10px", borderLeft: "1px solid #1e2235", gap: "14px", fontFamily: "Courier New, monospace", minHeight: 0, overflowY: "auto" },
  section:     { display: "flex", flexDirection: "column", gap: "5px", flexShrink: 0 },
  feedSection: { display: "flex", flexDirection: "column", gap: "5px", flex: 1, minHeight: 0 },
  label:       { fontSize: "10px", color: "#4a5580", textTransform: "uppercase", letterSpacing: "0.12em" },
  name:        { fontSize: "18px", color: "#d0daf0", fontWeight: "bold", lineHeight: 1.2 },
  prop:        { display: "flex", justifyContent: "space-between", fontSize: "12px", gap: "8px" },
  propKey:     { color: "#6878a8" },
  propVal:     { color: "#9aaac8", textAlign: "right", wordBreak: "break-all" },
  passage:     { fontSize: "12px", color: "#7888b0" },
  passageLevel:{ color: "#4a5580" },
  player:      { fontSize: "12px", color: "#4af0c8" },
  row:         { display: "flex", gap: "6px", flexShrink: 0 },
  seedInput:   { flex: 1, background: "#10131f", border: "1px solid #2a3050", color: "#b0bcd0", padding: "4px 6px", fontFamily: "inherit", fontSize: "12px", minWidth: 0 },
  chatInput:   { flex: 1, background: "#10131f", border: "1px solid #2a3050", color: "#b0bcd0", padding: "4px 6px", fontFamily: "inherit", fontSize: "12px", minWidth: 0 },
  btn:         { background: "#0e1828", border: "1px solid #2a4060", color: "#3a8eff", padding: "4px 10px", cursor: "pointer", fontFamily: "inherit", fontSize: "11px", flexShrink: 0 },
  feed:        { overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "3px" },
  empty:       { fontSize: "11px", color: "#2a3555" },
  status:      { fontSize: "11px", flexShrink: 0 },
};

const er = {
  chat:   { fontSize: "12px", color: "#9aaac8", lineHeight: 1.4 },
  name:   { color: "#3a8eff" },
  causal: { fontSize: "11px", color: "#3a5070" },
  puzzle: { fontSize: "11px", color: "#4af0a0" },
  system: { fontSize: "11px", color: "#3a5070" },
};

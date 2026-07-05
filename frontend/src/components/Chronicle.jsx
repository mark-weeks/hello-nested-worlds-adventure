import { useCallback, useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";

// The world chronicle: the permanent record of everything every player and
// agent has done in this world, paginated backward in time and grouped into
// deterministically named eras (GET /chronicle). This is how a new arrival
// perceives the history they are building on.

function describeEntry(e) {
  const who = e.player || (e.data && e.data.agent) || "someone";
  switch (e.type) {
    case "PUZZLE_SOLVED": return `${who} solved a puzzle at ${e.node}`;
    case "PUZZLE_FAILED": return `a puzzle resisted ${who} at ${e.node}`;
    case "PLAYER_SPEAK":  return `${who} spoke with ${e.node}`;
    case "PLAYER_CHAT":   return `${who} said something at ${e.node}`;
    case "AGENT_VISIT":   return `${who} passed through ${e.node}`;
    case "DANGER_ALERT":  return `danger stirred at ${e.node}`;
    case "SCALE_ACT":     return `${who} chose to ${(e.data && e.data.verb) || "act"} at ${e.node}`;
    case "AGENT_TALK":    return `${(e.data && e.data.a) || "someone"} and ${(e.data && e.data.b) || "someone"} spoke at ${e.node}`;
    default:              return `something happened at ${e.node}`;
  }
}

export default function Chronicle({ seed, onClose }) {
  const [entries, setEntries] = useState([]);
  const [meta, setMeta] = useState("");
  const [cursor, setCursor] = useState(null);
  const [done, setDone] = useState(false);
  const loading = useRef(false);

  const loadPage = useCallback(async (before) => {
    if (loading.current) return;
    loading.current = true;
    try {
      const q = before ? `&before=${before}` : "";
      const r = await fetch(withKey(`/chronicle?seed=${seed}&limit=40${q}`));
      const data = await r.json();
      setMeta(`seed ${data.seed} · ${data.total} recorded events` +
        (data.began ? ` since ${data.began.slice(0, 10)}` : "") +
        ` · now: ${data.era_now}`);
      setEntries(prev => before ? [...prev, ...(data.entries || [])] : (data.entries || []));
      setCursor(data.next_before);
      setDone(!data.next_before);
    } catch {
      setMeta("The chronicle is unreadable right now.");
    } finally {
      loading.current = false;
    }
  }, [seed]);

  useEffect(() => { loadPage(null); }, [loadPage]);

  // Group entries under era headers as we render.
  let lastEra = null;
  const rows = [];
  for (const e of entries) {
    if (e.era && e.era !== lastEra) {
      lastEra = e.era;
      rows.push(<div key={`era-${e.id}`} style={c.era}>{e.era}</div>);
    }
    rows.push(
      <div key={e.id} style={c.row}>
        <span style={c.when}>{(e.at || "").slice(5, 16)}</span> {describeEntry(e)}
      </div>
    );
  }

  return (
    <div style={c.overlay} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={c.box}>
        <div style={c.title}>World Chronicle</div>
        <div style={c.meta}>{meta}</div>
        <div style={c.list}>
          {rows.length ? rows
            : <div style={c.empty}>Nothing has happened here yet. You would be first.</div>}
        </div>
        <div style={c.btnRow}>
          {!done && <button style={c.btn} onClick={() => loadPage(cursor)}>further back</button>}
          <button style={c.btn} onClick={onClose}>close</button>
        </div>
      </div>
    </div>
  );
}

const c = {
  overlay: { position: "fixed", inset: 0, background: "rgba(7,8,15,0.88)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" },
  box:     { background: "#0b0d1a", border: "1px solid #2a4060", padding: "28px 32px", width: "min(520px, calc(100vw - 48px))", maxHeight: "80vh", display: "flex", flexDirection: "column", gap: "12px", fontFamily: "Courier New, monospace" },
  title:   { fontSize: "13px", letterSpacing: "3px", textTransform: "uppercase", color: "#3a8eff" },
  meta:    { fontSize: "10px", color: "#4a6080", letterSpacing: "1px" },
  list:    { overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "2px", minHeight: "120px" },
  era:     { fontSize: "10px", letterSpacing: "2px", textTransform: "uppercase", color: "#3a8eff", margin: "10px 0 4px", borderBottom: "1px solid #141828", paddingBottom: "3px" },
  row:     { fontSize: "10px", color: "#5a7090", lineHeight: 1.5 },
  when:    { color: "#2a4050" },
  empty:   { fontSize: "10px", color: "#2a4060" },
  btnRow:  { display: "flex", gap: "10px" },
  btn:     { background: "#0e1828", border: "1px solid #2a4060", color: "#3a8eff", padding: "5px 12px", cursor: "pointer", fontFamily: "inherit", fontSize: "11px" },
};

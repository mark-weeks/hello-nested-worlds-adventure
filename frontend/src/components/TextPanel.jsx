import { useState } from "react";
import Chronicle from "./Chronicle.jsx";
import Interact from "./Interact.jsx";
import Wayback from "./Wayback.jsx";
import { passageBadges } from "../badges.js";
import { causalFeedLine, displayName, nodeAddress } from "../names.js";

export default function TextPanel({ node, players, agents = {}, connected, events, seed, depth, playerName, onChat, onJump, passageLoadStatus = "idle", onPassageRetry, wrapPassage = null, onWrapCross, onSolved, onNodeChanged, soundOn, onToggleSound, onWaybackListen }) {
  const [chatInput, setChatInput] = useState("");
  const [chronicleOpen, setChronicleOpen] = useState(false);
  const [waybackOpen, setWaybackOpen] = useState(false);

  const here = players.filter(p => p.node === node.name);

  const handleChat = () => {
    const text = chatInput.trim();
    if (!text || !connected) return;
    onChat(text);
    setChatInput("");
  };

  return (
    <div style={s.panel}>

      <div style={s.section}>
        <div style={s.label}>{node.level}</div>
        {/* Display layer: the readable phrase carries the identity a player
            speaks; the address (path digits) sits beneath as its own field,
            and hovering the name reveals the full canonical form. */}
        <div style={s.name} title={node.name}>{displayName(node.name)}</div>
        {nodeAddress(node.name) && (
          <div style={s.address}
               title="this place's address — its path from the root of the multiverse">
            ⌖ {nodeAddress(node.name)}
          </div>
        )}
        <div style={s.nodeActions}>
          <button
            style={s.waybackBtn}
            title="Replay this node from its first recorded state to now"
            onClick={() => setWaybackOpen(true)}
          >Replay History</button>
          <a href="/guide" style={s.guideLink} title="How to play Enfolded">
            Player's Guide ↗
          </a>
        </div>
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
          {node.ripple_score > 0 && (
            <div style={s.prop} title="accumulated causal pressure from events here and nearby">
              <span style={s.propKey}>causal pressure</span>
              <span style={{ ...s.propVal, color: node.ripple_score >= 0.5 ? "#c88af0" : "#9aaac8" }}>
                {"▮".repeat(Math.max(1, Math.round(node.ripple_score * 8)))} {node.ripple_score.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      <Interact node={node} seed={seed} depth={depth} playerName={playerName} onSolved={onSolved} onNodeChanged={onNodeChanged} />

      {node.children.length > 0 && (
        <div style={s.section}>
          <div style={s.label}>Passages ({node.children.length})</div>
          {node.children.map(c => (
            <button
              key={c.id}
              type="button"
              style={s.passage}
              title={`Travel to ${c.name}`}
              onClick={() => onJump?.(c.name)}
            >
              → {displayName(c.name)} <span style={s.passageLevel}>({c.level})</span>
              {passageBadges(c).map(b => (
                <span key={b.key} style={{ ...s.badge, color: b.css, borderColor: b.css + "55" }}>{b.label}</span>
              ))}
            </button>
          ))}
        </div>
      )}

      {passageLoadStatus === "loading" && (
        <div style={s.section}>
          <div style={s.passageStatus}>Opening the passages within…</div>
        </div>
      )}

      {passageLoadStatus === "error" && (
        <div style={s.section}>
          <div style={s.passageStatus}>The inner passages did not open.</div>
          <button style={s.deepenBtn} onClick={onPassageRetry}>
            Retry passages
          </button>
        </div>
      )}

      {wrapPassage && (
        <div style={s.section}>
          <div style={s.label}>
            {wrapPassage.direction === "inward"
              ? "The world continues inward"
              : "The world continues beyond"}
          </div>
          <button style={s.deepenBtn} onClick={() => onWrapCross?.(wrapPassage)}>
            {wrapPassage.direction === "inward" ? "Descend into the whole ↓" : "Ascend beyond ↑"}
          </button>
          <div style={s.wrapHint}>{wrapPassage.passage}</div>
        </div>
      )}

      {here.length > 0 && (
        <div style={s.section}>
          <div style={s.label}>Present here</div>
          {here.map(p => <div key={p.session_id} style={s.player}>◈ {p.name}</div>)}
        </div>
      )}

      {(players.length > 0 || Object.keys(agents).length > 0) && (
        <div style={s.section}>
          <div style={s.label}>Travelers</div>
          {players.map(p => (
            <div
              key={p.session_id}
              style={s.traveler}
              title={`go to ${p.name}`}
              onClick={() => p.node && onJump?.(p.node)}
            >
              <span style={s.travelerName}>◈ {p.name}</span>
              <span style={s.travelerNode} title={p.node}>{p.node ? displayName(p.node) : "—"}</span>
            </div>
          ))}
          {Object.entries(agents).map(([name, a]) => (
            <div
              key={name}
              style={s.traveler}
              title={`follow ${name}`}
              onClick={() => a.node && onJump?.(a.node)}
            >
              <span style={{ ...s.travelerName, color: "#f0c878" }}>
                ✦ {name}{a.persona ? <span style={s.travelerPersona}> · {a.persona}</span> : null}
              </span>
              <span style={s.travelerNode} title={a.node}>{a.node ? displayName(a.node) : "…arriving"}</span>
            </div>
          ))}
        </div>
      )}

      <div style={s.feedSection}>
        <div style={s.labelRow}>
          <span style={s.label}>Recent events</span>
          <button
            style={s.chronicleBtn}
            title="The world's full history — everything every player and agent has done here"
            onClick={() => setChronicleOpen(true)}
          >View full chronicle</button>
        </div>
        <div style={s.feed}>
          {events.length === 0
            ? <div style={s.empty}>No events yet</div>
            : events.map((ev, i) => <EventRow key={i} ev={ev} />)
          }
        </div>
      </div>

      {chronicleOpen && <Chronicle seed={seed} onClose={() => setChronicleOpen(false)} />}
      {waybackOpen && (
        <Wayback
          seed={seed}
          node={node}
          onListen={onWaybackListen}
          onClose={() => setWaybackOpen(false)}
        />
      )}

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
        <span style={s.statusRight}>
          {onToggleSound && (
            <button
              id="btn-sound"
              style={s.soundBtn}
              aria-pressed={!!soundOn}
              title="Ambient sound: every place hums its own deterministic tone"
              onClick={onToggleSound}
            >♪ {soundOn ? "on" : "off"}</button>
          )}
        </span>
      </div>

    </div>
  );
}

function EventRow({ ev }) {
  if (ev.type === "chat")
    return <div style={er.chat}><span style={er.name}>{ev.name}</span> {ev.text}</div>;
  if (ev.type === "causal")
    return <div style={er.causal}>{causalFeedLine(ev.kind, ev.node, ev.strength)}</div>;
  if (ev.type === "puzzle")
    return <div style={er.puzzle}>{ev.text}</div>;
  if (ev.type === "history")
    return <div style={er.history}>◦ {ev.text}</div>;
  return <div style={er.system}>{ev.text}</div>;
}

const s = {
  panel:       { flex: "0 0 300px", display: "flex", flexDirection: "column", padding: "16px 14px 10px", borderLeft: "1px solid #1e2235", gap: "14px", fontFamily: "Courier New, monospace", minHeight: 0, overflowY: "auto" },
  section:     { display: "flex", flexDirection: "column", gap: "5px", flexShrink: 0 },
  feedSection: { display: "flex", flexDirection: "column", gap: "5px", flex: 1, minHeight: 0 },
  labelRow:    { display: "flex", justifyContent: "space-between", alignItems: "center" },
  nodeActions: { display: "flex", gap: "7px", alignItems: "stretch", flexWrap: "wrap", marginTop: "3px" },
  statusRight: { display: "flex", gap: "10px", alignItems: "center" },
  soundBtn:    { background: "none", border: "1px solid #1e2235", color: "#4a5580", padding: "1px 8px", cursor: "pointer", fontFamily: "inherit", fontSize: "9px", letterSpacing: "0.1em" },
  guideLink:   { display: "inline-flex", alignItems: "center", color: "#83a9d8", border: "1px solid #2a4060", padding: "4px 8px", fontSize: "10px", letterSpacing: "0.04em", textDecoration: "none" },
  chronicleBtn:{ background: "#0e1828", border: "1px solid #5268a8", color: "#9aaee8", padding: "4px 8px", cursor: "pointer", fontFamily: "inherit", fontSize: "10px", letterSpacing: "0.04em" },
  waybackBtn:  { alignSelf: "flex-start", background: "#111a30", border: "1px solid #5268a8", color: "#9aaee8", padding: "3px 8px", cursor: "pointer", fontFamily: "inherit", fontSize: "9px", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: "3px" },
  label:       { fontSize: "10px", color: "#4a5580", textTransform: "uppercase", letterSpacing: "0.12em" },
  name:        { fontSize: "18px", color: "#d0daf0", fontWeight: "bold", lineHeight: 1.2 },
  address:     { fontSize: "10px", color: "#4a5580", letterSpacing: "0.08em" },
  prop:        { display: "flex", justifyContent: "space-between", fontSize: "12px", gap: "8px" },
  propKey:     { color: "#6878a8" },
  propVal:     { color: "#9aaac8", textAlign: "right", wordBreak: "normal", overflowWrap: "break-word", hyphens: "auto", maxWidth: "58%" },
  passage:     { appearance: "none", background: "none", border: 0, padding: "2px 0", textAlign: "left", fontFamily: "inherit", fontSize: "12px", color: "#91a4d0", cursor: "pointer" },
  passageLevel:{ color: "#4a5580" },
  badge:       { fontSize: "9px", border: "1px solid", borderRadius: "3px", padding: "0 4px", marginLeft: "5px", letterSpacing: "0.06em", whiteSpace: "nowrap" },
  player:      { fontSize: "12px", color: "#4af0c8" },
  traveler:    { display: "flex", justifyContent: "space-between", gap: "8px", fontSize: "11px", cursor: "pointer", padding: "1px 0" },
  travelerName: { color: "#4af0c8", whiteSpace: "nowrap" },
  travelerPersona: { color: "#5a6a8a" },
  travelerNode: { color: "#5a6a8a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  row:         { display: "flex", gap: "6px", flexShrink: 0 },
  chatInput:   { flex: 1, background: "#10131f", border: "1px solid #2a3050", color: "#b0bcd0", padding: "4px 6px", fontFamily: "inherit", fontSize: "12px", minWidth: 0 },
  btn:         { background: "#0e1828", border: "1px solid #2a4060", color: "#3a8eff", padding: "4px 10px", cursor: "pointer", fontFamily: "inherit", fontSize: "11px", flexShrink: 0 },
  deepenBtn:   { background: "#111a30", border: "1px solid #5268a8", color: "#9aaee8", padding: "7px 10px", cursor: "pointer", fontFamily: "inherit", fontSize: "11px", letterSpacing: "0.08em", textTransform: "uppercase" },
  passageStatus:{ fontSize: "11px", color: "#6f82ad", fontStyle: "italic" },
  wrapHint:    { fontSize: "10px", color: "#56628a", fontStyle: "italic", lineHeight: 1.4 },
  feed:        { overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "3px" },
  empty:       { fontSize: "11px", color: "#2a3555" },
  status:      { fontSize: "11px", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" },
};

const er = {
  chat:    { fontSize: "12px", color: "#9aaac8", lineHeight: 1.4 },
  name:    { color: "#3a8eff" },
  causal:  { fontSize: "11px", color: "#3a5070" },
  puzzle:  { fontSize: "11px", color: "#4af0a0" },
  system:  { fontSize: "11px", color: "#3a5070" },
  history: { fontSize: "11px", color: "#56628a", fontStyle: "italic" },
};

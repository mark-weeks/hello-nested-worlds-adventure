import { useState } from "react";
import Chronicle from "./Chronicle.jsx";
import Interact from "./Interact.jsx";
import Wayback from "./Wayback.jsx";
import { causalFeedLine, displayName, nodeAddress } from "../names.js";

export default function TextPanel({ node, players, agents = {}, connected, events, seed, depth, playerName, onChat, onJump, onSolved, onNodeChanged, onEnsurePosition, soundOn, onToggleSound, onWaybackListen, scoreVolume, onScoreVolume }) {
  const [chatInput, setChatInput] = useState("");
  const [chronicleOpen, setChronicleOpen] = useState(false);
  const [waybackOpen, setWaybackOpen] = useState(false);
  const handleChat = () => {
    const text = chatInput.trim();
    if (!text || !connected) return;
    onChat(text); setChatInput("");
  };
  return <div className="world-panel">
    <section className="node-identity" aria-labelledby="node-name">
      <div id="node-level">{node.level}</div>
      <h1 id="node-name" tabIndex={-1} title={node.name}>{displayName(node.name)}</h1>
      <div id="node-address" title="Position: path from the root of the multiverse">⌖ {nodeAddress(node.name) || "1"}</div>
      <p id="node-description">{node.senses?.description || node.properties?.aspect}</p>
    </section>
    <Interact node={node} seed={seed} depth={depth} playerName={playerName} onSolved={onSolved} onNodeChanged={onNodeChanged} onJump={onJump} onEnsurePosition={onEnsurePosition} />
    <details className="secondary">
      <summary>Conditions here</summary>
      <p className="quiet">{globalThis.EnfoldedInterface.cue(node)}</p>
      {Object.entries(node.properties || {}).filter(([k])=>k!=="aspect").map(([k,v])=><div className="prop" key={k}><span>{k.replaceAll('_',' ')}</span><span>{typeof v === "object" ? JSON.stringify(v) : String(v)}</span></div>)}
      {node.ripple_score>0 && <div className="prop"><span>Causal pressure</span><span>{node.ripple_score.toFixed(2)}</span></div>}
    </details>
    <details className="secondary">
      <summary>History & journal</summary>
      <div className="control-row">
        <button onClick={()=>setWaybackOpen(true)}>Replay History</button>
        <a className="control" href={`/journal?seed=${seed}&node=${encodeURIComponent(node.name)}`} target="_blank" rel="noopener">Journal ↗</a>
        <button onClick={()=>setChronicleOpen(true)}>View full chronicle</button>
      </div>
      <div className="feed" aria-label="Recent events">
        {events.length ? events.map((ev,i)=><p className="quiet" key={i}>{ev.type==='chat' ? `${ev.name}: ${ev.text}` : ev.text || causalFeedLine(ev.kind,ev.node,ev.strength)}</p>) : <p className="quiet">No events yet.</p>}
      </div>
    </details>
    <details className="secondary">
      <summary>Travelers & chat</summary>
      {players.map(p=><button className="traveler" key={p.session_id} disabled={!p.node} onClick={()=>onJump?.(p.node)}><span>◈ {p.name}</span><span>{p.node===node.name ? "Here" : p.node ? displayName(p.node) : "Arriving"}</span></button>)}
      {Object.entries(agents).map(([name,a])=><button className="traveler" key={name} disabled={!a.node} onClick={()=>onJump?.(a.node)}><span>✦ {name}{a.persona ? ` · ${a.persona}` : ""}</span><span>{a.node===node.name ? "Here" : a.node ? displayName(a.node) : "Arriving"}</span></button>)}
      {!players.length && !Object.keys(agents).length && <p className="quiet">No other travelers are in view.</p>}
      <div className="chat-row">
        <input aria-label="Message to travelers" maxLength={256} placeholder={connected ? "Say something…" : "Not connected"} value={chatInput} onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>e.key==='Enter' && handleChat()} disabled={!connected} />
        <button onClick={handleChat} disabled={!connected || !chatInput.trim()}>Send</button>
      </div>
    </details>
    <details className="secondary">
      <summary>Sound & help</summary>
      <div className="sound-controls">
        <button id="btn-sound" onClick={onToggleSound} aria-pressed={!!soundOn}>{soundOn ? 'Pause score' : 'Listen to this world'}</button>
        <label>Volume <input aria-label="Score volume" type="range" min="0" max="1" step=".05" value={scoreVolume} onChange={e=>onScoreVolume(Number(e.target.value))} /></label>
      </div>
      <div className="control-row"><a className="control" href="/guide">Player's Guide ↗</a><a className="control" href="/ideas" target="_blank" rel="noopener noreferrer">Ideas ↗</a></div>
    </details>
    <p className="quiet" role="status">{connected ? "● Connected to the shared world" : "○ Reconnecting to the shared world"}</p>
    {chronicleOpen && <Chronicle seed={seed} onClose={()=>setChronicleOpen(false)} />}
    {waybackOpen && <Wayback seed={seed} node={node} onListen={onWaybackListen} onClose={()=>setWaybackOpen(false)} />}
  </div>;
}

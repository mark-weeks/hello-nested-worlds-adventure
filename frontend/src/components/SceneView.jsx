import { useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import { displayName } from "../names.js";
import { passageBadges } from "../badges.js";
import { startSensory } from "../../../static/sensory.js";
import "./scene.css";

export default function SceneView({node, players, transients = [], onNavigate, onNavigateUp, canGoUp, seed}) {
  const canvas = useRef(null), liveTransients = useRef(transients);
  liveTransients.current = transients;
  const [image, setImage] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    const abort = new AbortController(); let current = true;
    setImage(null);
    if (!node.senses?.plate) fetch(withKey("/image"), {
      method: 'POST', headers: {'Content-Type': 'application/json'}, signal: abort.signal,
      body: JSON.stringify({node_name: node.name, seed: seed ?? 0}),
    }).then(r => r.json()).then(data => { if (current && data.url) setImage(data.url); }).catch(() => {});
    return () => { current = false; abort.abort(); };
  }, [seed, node.name, node.senses?.revision]);
  useEffect(() => {
    if (!canvas.current.getContext('2d')) { setUnavailable(true); return; }
    setUnavailable(false);
    return startSensory(canvas.current, node, {imageUrl: image, transients: () => liveTransients.current});
  }, [node, image]);
  const s = node.senses || {};
  const presence = players.filter(p => p.node === node.name);
  return <section className="scene-view cinematic-scene" aria-label="Living scene">
    <canvas ref={canvas} className="living-canvas" role="img" aria-label={`Scene of ${displayName(node.name)}, a ${node.level}. ${node.properties?.aspect || ''}${s.woven ? ' A woven resonator holds here.' : ''}${s.memory ? ' A remembered harmonic remains.' : ''}`} />
    <div className="scene-vignette" />
    <nav className="scene-nav" aria-label="Scene navigation">
      {canGoUp && <button onClick={onNavigateUp}>↑ Enclosing world</button>}
      <a href="/">World map ↗</a>
    </nav>
    <div className="scene-title">
      <p className="scene-kicker">ENFOLDED <span> / {node.level}</span></p>
      <h1>{displayName(node.name)}</h1>
      <p className="scene-aspect">{node.properties?.aspect}</p>
      <p className="scene-condition">{[s.woven && 'A resonator holds the light', s.memory && 'A harmonic memory remains', s.echo > .1 && 'An outward resonance remains', s.echo < -.1 && 'An inward resonance remains'].filter(Boolean).join(' · ')}</p>
    </div>
    <section className="scene-passages" aria-label={unavailable ? "Text scene" : "Passages"}>
      {unavailable && <p>The view is quiet. The passages remain open to exploration.</p>}
      {!!presence.length && <p className="scene-presence">Here with you · {presence.map(p => p.name).join(', ')}</p>}
      {!!node.children?.length && <span className="scene-kicker">WITHIN THIS PLACE</span>}
      <div className="scene-passage-grid">{node.children?.map(child => <button key={child.name} onClick={() => onNavigate(child)} title={child.name}>
        <span>{child.level} ↘</span><strong>{displayName(child.name)}</strong>
        <small>{passageBadges(child).map(b => b.label).join(' · ')}</small>
      </button>)}</div>
    </section>
  </section>;
}

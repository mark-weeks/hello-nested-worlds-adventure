import { useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import { displayName } from "../names.js";
import { passageBadges } from "../badges.js";
import { startSensory } from "../../../static/sensory.js";
import "./scene.css";

export default function SceneView({node, transients = [], onNavigate, onNavigateUp, canGoUp, seed}) {
  const canvas = useRef(null), liveTransients = useRef(transients);
  liveTransients.current = transients;
  const [image, setImage] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  // One generated plate per visit: a paid image is fetched when the place or
  // its curated plate changes, never on every material revision. The shared
  // renderer below reinterprets live senses on top of the stable plate.
  const plated = !!node.senses?.plate;
  useEffect(() => {
    const abort = new AbortController(); let current = true;
    setImage(null);
    if (!plated) fetch(withKey("/image"), {
      method: 'POST', headers: {'Content-Type': 'application/json'}, signal: abort.signal,
      body: JSON.stringify({node_name: node.name, seed: seed ?? 0}),
    }).then(r => r.json()).then(data => { if (current && data.url) setImage(data.url); }).catch(() => {});
    return () => { current = false; abort.abort(); };
  }, [seed, node.name, plated]);
  useEffect(() => {
    if (!canvas.current.getContext('2d')) { setUnavailable(true); return; }
    setUnavailable(false);
    return startSensory(canvas.current, node, {imageUrl: image, transients: () => liveTransients.current});
  }, [node, image]);
  return <section className="scene-view cinematic-scene" aria-label="Living scene">
    <canvas ref={canvas} className="living-canvas" role="img" aria-labelledby="node-name" aria-describedby="node-description" />
    <div className="scene-vignette" />
    <nav className="scene-nav" aria-label="Scene navigation">
      {canGoUp && <button onClick={onNavigateUp}>↑ Enclosing world</button>}
      <a href="/">World map ↗</a>
    </nav>
    <section className="scene-passages" aria-label={unavailable ? "Text scene" : "Passages"}>
      {unavailable && <p>The view is quiet. The passages remain open to exploration.</p>}
      {!!node.children?.length && <span className="scene-kicker">WITHIN THIS PLACE</span>}
      <div className="scene-passage-grid">{node.children?.map(child => <button key={child.name} onClick={() => onNavigate(child)} title={child.name}>
        <span>{child.level} ↘</span><strong>{displayName(child.name)}</strong>
        <small>{passageBadges(child).map(b => b.label).join(' · ')}</small>
      </button>)}</div>
    </section>
  </section>;
}

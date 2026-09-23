import { useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import "../../../static/navigation.js";
import { startSensory } from "../../../static/sensory.js";
import "./scene.css";

export default function SceneView({node, transients = [], parent, onJump, passageLoadStatus, onPassageRetry, wrapPassage, onWrapCross, seed}) {
  const navigation=useRef(null);
  useEffect(()=>{ navigation.current.context={node,parent,seed,jump:onJump,status:passageLoadStatus,retry:onPassageRetry,wrap:wrapPassage,cross:onWrapCross,view:"World map ↗",href:"/"}; },[node,parent,seed,onJump,passageLoadStatus,onPassageRetry,wrapPassage,onWrapCross]);
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
    <div className="scene-art">
      <canvas ref={canvas} className="living-canvas" role="img" aria-labelledby="node-name" aria-describedby="node-description" />
      {unavailable && <p className="scene-fallback">The view is quiet. The passages remain open to exploration.</p>}
    </div>
    <enfolded-navigation ref={navigation} />
  </section>;
}

import { useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import "../../../static/navigation.js";
import { startSensory } from "../../../static/sensory.js";
import "./scene.css";

export default function SceneView({world, node, transients = [], parent, onJump, passageLoadStatus, onPassageRetry, wrapPassage, onWrapCross, seed}) {
  const navigation = useRef(null);
  const [view, setView] = useState(() => ({
    map: history.state?.worldMap ?? (location.pathname === "/"),
    lastScene: null,
  }));
  useEffect(() => {
    navigation.current.context = {
      node, parent, seed, jump: onJump, status: passageLoadStatus, retry: onPassageRetry,
      wrap: wrapPassage, cross: onWrapCross, view: view.map ? "Living scene" : "World map",
      switchView() {
        // Each history entry remembers the player's choice across reloads.
        history.replaceState({ ...history.state, worldMap: !view.map }, "");
        setView({ map: !view.map, lastScene: view.map ? null : { node, seed } });
      },
    };
  }, [node, parent, seed, onJump, passageLoadStatus, onPassageRetry, wrapPassage, onWrapCross, view.map]);

  // Retain the last plate while browsing. Switching views at one place must
  // not request a second generated image, or generate plates for map travel.
  const scene = view.map ? view.lastScene : { node, seed };
  return <section className="scene-view cinematic-scene" aria-label={view.map ? "World map" : "Living scene"}>
    {scene && <SceneArt key={scene.node.name} node={scene.node} seed={scene.seed} visible={!view.map} transients={transients} />}
    {view.map && <WorldMap world={world} currentNode={node} onJump={onJump} navigation={navigation} />}
    <enfolded-navigation ref={navigation} />
  </section>;
}

// Load the vendored map renderer on first use. Passages and interactions
// stay usable even if the browser loses the connection during that read.
function WorldMap({navigation, ...props}) {
  const [MapView, setMapView] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    import("./MapView.jsx").then(module => {
      if (active) setMapView(() => module.default);
    }, () => {
      if (active) setFailed(true);
    });
    return () => { active = false; };
  }, []);
  if (MapView) {
    // The player may already have tabbed on while the chunk loaded.
    const atToggle = navigation.current?.shadowRoot.activeElement?.dataset.target === "view";
    return <MapView {...props} focusOnOpen={atToggle} />;
  }
  return <p role="status">{failed ? "The map could not open. You can still travel using the passages below." : "Opening the world map…"}</p>;
}

function SceneArt({node, seed, visible, transients}) {
  const canvas = useRef(null), liveTransients = useRef(transients);
  const caption = useRef(null);
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
    }).then(r => r.ok ? r.json() : null).then(data => {
      if (current && typeof data?.url === 'string' && data.url) setImage(data.url);
    }).catch(() => {});
    return () => { current = false; abort.abort(); };
  }, [seed, node.name, plated]);
  useEffect(() => {
    if (!visible) return;
    const credit = caption.current;
    if (!canvas.current.getContext('2d')) {
      credit.textContent = '';
      setUnavailable(true);
      return;
    }
    setUnavailable(false);
    return startSensory(canvas.current, node, {
      imageUrl: plated ? null : image,
      transients: () => liveTransients.current,
      onArtSource: text => { credit.textContent = text; },
    });
  }, [node, plated, image, visible]);
  return visible && <figure className="scene-figure">
    <div className="scene-art">
      <canvas ref={canvas} className="living-canvas" role="img" aria-labelledby="node-name" aria-describedby="node-description scene-art-source" />
      {unavailable && <p className="scene-fallback">The view is quiet. The passages remain open to exploration.</p>}
    </div>
    <figcaption id="scene-art-source" ref={caption} className="art-source" />
  </figure>;
}

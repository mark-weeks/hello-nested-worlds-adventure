import { useEffect, useRef, useState } from "react";
import { Application, Assets, Container, Graphics, Sprite, Text, TextStyle } from "pixi.js";
import { withKey } from "../auth.js";
import { passageBadges } from "../badges.js";

export default function SceneView({
  node, players, transients = [],
  onNavigate, onNavigateUp, canGoUp, seed,
}) {
  const containerRef = useRef(null);
  const appRef = useRef(null);
  // The transient layer survives node changes; we only clear its children
  // when the prop list changes, not on every other re-render.
  const transientLayerRef = useRef(null);
  const transientsRef = useRef(transients);
  // `Application.init()` is async: in PixiJS v8 `app.screen`/`app.renderer`
  // don't exist until it resolves, but the [node, players, bgUrl] effect below
  // runs synchronously on the same mount commit — before init completes. Any
  // read of `app.screen` before then throws, and with no error boundary that
  // white-screens the whole app (observed in headless Chromium and on slow /
  // mobile devices). This flag gates every draw on init having finished.
  const readyRef = useRef(false);
  const [bgUrl, setBgUrl] = useState(null);

  // Fetch fal.ai background image URL whenever the node changes
  useEffect(() => {
    setBgUrl(null);
    // `/image` is a gated, rate-limited endpoint like every other data call —
    // it must carry the invite key or it 403s under the beta gate, silently
    // leaving the scene without its fal.ai background (the /app headline
    // feature). All the other fetches already go through withKey(); this one
    // was the lone exception.
    // Node identity is server-derived: (seed, name) is the whole request.
    fetch(withKey("/image"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_name: node.name,
        seed: seed ?? 0,
      }),
    })
      .then((r) => r.json())
      .then((d) => { if (d.url) setBgUrl(d.url); })
      .catch(() => {});
  }, [node.id ?? node.name]);

  // Keep the ref in sync so the ticker callback always sees the latest list.
  useEffect(() => { transientsRef.current = transients; }, [transients]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const app = new Application();
    appRef.current = app;

    let tickCallback = null;

    app.init({
      resizeTo: container,
      background: 0x07080f,
      antialias: true,
    }).then(() => {
      // The effect may have been torn down (or the app destroyed) while init
      // was in flight — bail rather than touch a dead renderer.
      if (appRef.current !== app || !app.renderer) return;
      container.appendChild(app.canvas);

      // Static layer (rebuilds when node/players change) + transient overlay
      // that the ticker draws into every frame from the latest prop list.
      const transientLayer = new Container();
      transientLayer.eventMode = "none";
      transientLayerRef.current = transientLayer;

      readyRef.current = true;
      renderScene(app, node, players, onNavigate, bgUrl);
      app.stage.addChild(transientLayer);

      tickCallback = () => {
        if (!app.renderer) return;
        paintTransients(transientLayer, transientsRef.current, app.screen);
      };
      app.ticker.add(tickCallback);
    }).catch(() => {
      // WebGL/WebGPU unavailable (headless without GPU, locked-down mobile).
      // Leave the scene blank; the rest of the app (text panel, speak, puzzle)
      // stays fully usable instead of white-screening.
    });

    return () => {
      readyRef.current = false;
      if (tickCallback && app.ticker) app.ticker.remove(tickCallback);
      app.destroy(true, { children: true });
      appRef.current = null;
      transientLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const app = appRef.current;
    const transientLayer = transientLayerRef.current;
    // Skip until init has finished — otherwise app.screen throws (see readyRef).
    if (!app || !app.stage || !app.renderer || !readyRef.current) return;
    // Rebuild static content; preserve the transient layer by detaching and
    // re-attaching it on top of the rebuilt scene.
    if (transientLayer && transientLayer.parent === app.stage) {
      app.stage.removeChild(transientLayer);
    }
    app.stage.removeChildren();
    renderScene(app, node, players, onNavigate, bgUrl);
    if (transientLayer) {
      transientLayer.removeChildren();  // clear stale transient graphics
      app.stage.addChild(transientLayer);
    }
  }, [node, players, onNavigate, bgUrl]);

  return (
    <div style={styles.wrapper}>
      <div ref={containerRef} style={styles.canvas} />
      {canGoUp && (
        <button style={styles.upBtn} onClick={onNavigateUp}>← back</button>
      )}
      <a href="/" style={styles.switchLink} title="Switch to D3 explorer">D3 ↗</a>
    </div>
  );
}

// ── Static scene rendering ────────────────────────────────────────────────

function renderScene(app, node, players, onNavigate, bgUrl) {
  // Guard against a not-yet-initialised or torn-down renderer — `app.screen`
  // throws until init resolves, and an unguarded throw here has no error
  // boundary above it and would blank the entire app.
  if (!app || !app.renderer) return;
  const { width, height } = app.screen;

  // Placeholder color background (index 0 — replaced by Sprite once loaded)
  _addColorBg(app, node, width, height);

  // Node name
  const label = new Text({
    text: `${node.level}: ${node.name}`,
    style: new TextStyle({ fill: 0xb0bcd0, fontSize: 18, fontFamily: "Courier New" }),
  });
  label.x = 24;
  label.y = 24;
  app.stage.addChild(label);

  // Hotspots for child nodes
  node.children.forEach((child, i) => {
    const x = 80 + (i % 4) * 180;
    const y = height / 2 + Math.floor(i / 4) * 80;
    const hotspot = makeHotspot(app, child, x, y, onNavigate);
    app.stage.addChild(hotspot);
  });

  // Player presence markers — each carries a name label so co-presence is
  // legible at a glance, not just "a green dot is there."
  players.filter((p) => p.node === node.name).forEach((p, i) => {
    const group = new Container();
    group.x = 28 + i * 70;
    group.y = height - 36;

    const marker = new Graphics();
    marker.circle(0, 0, 6).fill(playerColor(p.name)).stroke({ width: 1, color: 0x07080f });
    group.addChild(marker);

    const tag = new Text({
      text: p.name,
      style: new TextStyle({ fill: 0xa0c0e0, fontSize: 11, fontFamily: "Courier New" }),
    });
    tag.x = 12;
    tag.y = -6;
    group.addChild(tag);

    app.stage.addChild(group);
  });

  // Async: swap out the color bg with the fal.ai generated image
  if (bgUrl) {
    Assets.load(bgUrl).then((texture) => {
      if (!app.stage || app.stage.destroyed) return;
      const sprite  = new Sprite(texture);
      sprite.width  = width;
      sprite.height = height;
      app.stage.removeChildAt(0);
      app.stage.addChildAt(sprite, 0);
    }).catch(() => {});
  }
}

// ── Transient overlay: ripples, encounters, solve sparkles ────────────────

function paintTransients(layer, list, screen) {
  if (!layer || layer.destroyed) return;
  layer.removeChildren();
  if (!list.length) return;

  const cx  = screen.width  / 2;
  const cy  = screen.height / 2;
  const now = performance.now();

  for (const t of list) {
    const age      = (now - t.startedAt) / 1000;
    const duration = (t.duration ?? 1500) / 1000;
    if (age < 0 || age > duration) continue;
    const progress = age / duration;

    if (t.kind === "ripple") {
      // Expanding concentric circle, color keyed off the EventKind so
      // PUZZLE_SOLVED ripples read different from DANGER_ALERT etc.
      const r = 30 + 220 * progress;
      const alpha = (1 - progress) * (0.25 + 0.55 * (t.strength ?? 1));
      const color = rippleColor(t.eventKind);
      const g = new Graphics();
      g.circle(0, 0, r).stroke({ width: 2, color, alpha });
      g.x = cx;
      g.y = cy;
      layer.addChild(g);

    } else if (t.kind === "encounter") {
      // Two crossed glyphs converging at center, then fading. Reads as
      // "two presences just met here."
      const g = new Graphics();
      const offset = 60 * (1 - progress);
      const alpha  = 1 - progress;
      g.circle(-offset, 0, 9).fill({ color: 0xff8a4a, alpha });
      g.circle( offset, 0, 9).fill({ color: 0x4af0c8, alpha });
      g.moveTo(-offset, 0).lineTo(offset, 0).stroke({ width: 1, color: 0xffffff, alpha: alpha * 0.5 });
      g.x = cx;
      g.y = cy - 40;
      layer.addChild(g);

    } else if (t.kind === "solve") {
      // Four-pointed sparkle expanding outward in gold.
      const r = 24 + 100 * progress;
      const alpha = (1 - progress) ** 2;
      const g = new Graphics();
      for (let i = 0; i < 4; i++) {
        const angle = (i * Math.PI) / 2 + Math.PI / 4;
        const x = Math.cos(angle) * r;
        const y = Math.sin(angle) * r;
        g.moveTo(0, 0).lineTo(x, y).stroke({ width: 2, color: 0xf0c878, alpha });
      }
      g.circle(0, 0, 6).fill({ color: 0xf0c878, alpha });
      g.x = cx;
      g.y = cy;
      layer.addChild(g);
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

function _addColorBg(app, node, width, height) {
  const bg = new Graphics();
  bg.rect(0, 0, width, height).fill(levelColor(node.level));
  if (app.stage) app.stage.addChildAt(bg, 0);
}

// Hotspot affordance — closes design.md item #4. The visual treatment is
// shared across every hotspot regardless of child level so players learn it
// once: a recessed plate with a soft cast shadow, a single-pixel top-edge
// highlight (light from above), and a border that brightens on hover. The
// shadow lifts a hair when hovered so the plate reads as just-pressed.
const _HOTSPOT = Object.freeze({
  width:    120,
  height:   40,
  radius:   6,
  // Surface colors — kept dark enough to sit calmly against any generated bg.
  plateRest:  0x141826,
  plateHover: 0x1c2342,
  // Highlight + border tones; alpha is applied in the stroke calls so a
  // single colour can serve both rest and hover with different intensity.
  edgeRest:   0x3a4670,
  edgeHover:  0x6a80c8,
  borderRest: 0x4a5580,
  borderHover: 0x7a90d8,
  labelRest:  0x99aacc,
  labelHover: 0xc8d8ff,
  shadowYRest:  4,
  shadowYHover: 3,
});

function makeHotspot(app, node, x, y, onNavigate) {
  const W = _HOTSPOT.width, H = _HOTSPOT.height, R = _HOTSPOT.radius;

  const group = new Container();
  group.x = x;
  group.y = y;
  group.eventMode = "static";
  group.cursor = "pointer";

  // Cast shadow — sits below the plate to suggest the surface lifts off
  // the background. Drawn first so everything else stacks above it.
  const shadow = new Graphics();
  shadow.roundRect(-W / 2 + 2, -H / 2 + 2, W - 4, H - 2, R).fill({ color: 0x000000, alpha: 0.5 });
  shadow.y = _HOTSPOT.shadowYRest;
  group.addChild(shadow);

  // Plate — the apparent material surface.
  const plate = new Graphics();
  group.addChild(plate);

  // Top-edge highlight — single-pixel bright line just inside the top edge
  // suggests light falling from above on a slightly raised surface.
  const topEdge = new Graphics();
  group.addChild(topEdge);

  // Border — an outline that keeps the plate legible against bright
  // background images. Brightens on hover.
  const border = new Graphics();
  group.addChild(border);

  const label = new Text({
    text: node.name,
    style: new TextStyle({ fill: _HOTSPOT.labelRest, fontSize: 12, fontFamily: "Courier New" }),
  });
  label.anchor.set(0.5);
  group.addChild(label);

  // Affordance markers: small colored studs on the plate's top edge signal
  // what's notable through this passage (danger, corruption, pressure…)
  // before the player commits to it. Learnable like the plate treatment
  // itself — same colors as the text-panel badges.
  passageBadges(node).slice(0, 3).forEach((b, bi) => {
    const stud = new Graphics();
    stud.circle(W / 2 - 10 - bi * 10, -H / 2 + 1, 3)
        .fill({ color: b.color, alpha: 0.95 })
        .stroke({ width: 1, color: 0x07080f, alpha: 0.8 });
    group.addChild(stud);
  });

  const paint = (hovered) => {
    const plateColor  = hovered ? _HOTSPOT.plateHover  : _HOTSPOT.plateRest;
    const edgeColor   = hovered ? _HOTSPOT.edgeHover   : _HOTSPOT.edgeRest;
    const borderColor = hovered ? _HOTSPOT.borderHover : _HOTSPOT.borderRest;
    const edgeAlpha   = hovered ? 0.9 : 0.7;
    const borderAlpha = hovered ? 0.9 : 0.7;

    plate.clear().roundRect(-W / 2, -H / 2, W, H, R).fill({ color: plateColor });
    topEdge.clear()
      .moveTo(-W / 2 + 4, -H / 2 + 1)
      .lineTo( W / 2 - 4, -H / 2 + 1)
      .stroke({ width: 1, color: edgeColor, alpha: edgeAlpha });
    border.clear()
      .roundRect(-W / 2, -H / 2, W, H, R)
      .stroke({ width: 1, color: borderColor, alpha: borderAlpha });
    label.style.fill = hovered ? _HOTSPOT.labelHover : _HOTSPOT.labelRest;
    shadow.y = hovered ? _HOTSPOT.shadowYHover : _HOTSPOT.shadowYRest;
  };

  paint(false);

  group.on("pointerover", () => paint(true));
  group.on("pointerout",  () => paint(false));
  group.on("pointertap",  () => onNavigate(node));

  return group;
}

function levelColor(level) {
  const palette = {
    Multiverse: 0x0a0320, Universe: 0x0b0a28, Galaxy: 0x0a1030,
    "Planetary System": 0x0d1520, Planet: 0x0e1c18, Region: 0x121a12,
    Room: 0x141010, Object: 0x1a1008,
  };
  return palette[level] ?? 0x07080f;
}

const _PLAYER_PALETTE = [
  0x4af0c8, 0xff8a4a, 0xa078ff, 0xf0c878, 0x4a8eff, 0xf04a8e, 0x88f04a, 0xc04ff0,
];

function playerColor(name) {
  // Cheap deterministic hash → palette index, so the same name always gets
  // the same color across sessions.
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return _PLAYER_PALETTE[Math.abs(h) % _PLAYER_PALETTE.length];
}

function rippleColor(kind) {
  switch (kind) {
    case "PUZZLE_SOLVED":     return 0xf0c878;
    case "PUZZLE_FAILED":     return 0xff5050;
    case "DANGER_ALERT":      return 0xff8a4a;
    case "STRUCTURAL_CHANGE": return 0xa078ff;
    case "AGENT_VISIT":
    default:                  return 0x4af0c8;
  }
}

const styles = {
  wrapper:    { flex: "0 0 65%", position: "relative", overflow: "hidden" },
  canvas:     { width: "100%", height: "100%" },
  upBtn:      { position: "absolute", top: 16, left: 16, background: "rgba(10,14,28,0.85)", border: "1px solid #2a4060", color: "#3a8eff", padding: "6px 14px", cursor: "pointer", fontFamily: "Courier New, monospace", fontSize: "12px", zIndex: 10, letterSpacing: "0.05em" },
  switchLink: { position: "absolute", bottom: 12, left: 16, fontSize: "10px", color: "#2a3555", textDecoration: "none", letterSpacing: "0.08em" },
};

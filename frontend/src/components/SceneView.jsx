import { useEffect, useRef, useState } from "react";
import { Application, Assets, Graphics, Sprite, Text, TextStyle } from "pixi.js";

export default function SceneView({ node, players, onNavigate, onNavigateUp, canGoUp, seed }) {
  const containerRef = useRef(null);
  const appRef = useRef(null);
  const [bgUrl, setBgUrl] = useState(null);

  // Fetch fal.ai background image URL whenever the node changes
  useEffect(() => {
    setBgUrl(null);
    fetch("/image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: node.id ?? node.name,
        node_level: node.level,
        node_properties: node.properties ?? {},
        seed: seed ?? 0,
      }),
    })
      .then((r) => r.json())
      .then((d) => { if (d.url) setBgUrl(d.url); })
      .catch(() => {});
  }, [node.id ?? node.name]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const app = new Application();
    appRef.current = app;

    app.init({
      resizeTo: container,
      background: 0x07080f,
      antialias: true,
    }).then(() => {
      container.appendChild(app.canvas);
      renderScene(app, node, players, onNavigate, bgUrl);
    });

    return () => {
      app.destroy(true, { children: true });
      appRef.current = null;
    };
  }, []);

  useEffect(() => {
    const app = appRef.current;
    if (!app || !app.stage) return;
    app.stage.removeChildren();
    renderScene(app, node, players, onNavigate, bgUrl);
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

function renderScene(app, node, players, onNavigate, bgUrl) {
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

  // Player presence markers
  players.filter((p) => p.node === node.name).forEach((p, i) => {
    const marker = new Graphics();
    marker.circle(0, 0, 8).fill(0x4af0c8);
    marker.x = 24 + i * 22;
    marker.y = height - 32;
    app.stage.addChild(marker);
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

function _addColorBg(app, node, width, height) {
  const bg = new Graphics();
  bg.rect(0, 0, width, height).fill(levelColor(node.level));
  if (app.stage) app.stage.addChildAt(bg, 0);
}

function makeHotspot(app, node, x, y, onNavigate) {
  const g = new Graphics();
  g.roundRect(-60, -20, 120, 40, 6).fill(0x1a1d2e).stroke({ width: 1, color: 0x4a5580 });
  g.x = x;
  g.y = y;
  g.eventMode = "static";
  g.cursor = "pointer";

  const label = new Text({
    text: node.name,
    style: new TextStyle({ fill: 0x8898bb, fontSize: 12, fontFamily: "Courier New" }),
  });
  label.anchor.set(0.5);
  g.addChild(label);

  g.on("pointerover", () => g.clear().roundRect(-60, -20, 120, 40, 6).fill(0x252a40).stroke({ width: 1, color: 0x6a80cc }));
  g.on("pointerout",  () => g.clear().roundRect(-60, -20, 120, 40, 6).fill(0x1a1d2e).stroke({ width: 1, color: 0x4a5580 }));
  g.on("pointertap",  () => onNavigate(node));

  return g;
}

function levelColor(level) {
  const palette = {
    Multiverse: 0x0a0320, Universe: 0x0b0a28, Galaxy: 0x0a1030,
    "Planetary System": 0x0d1520, Planet: 0x0e1c18, Region: 0x121a12,
    Room: 0x141010, Object: 0x1a1008,
  };
  return palette[level] ?? 0x07080f;
}

const styles = {
  wrapper:    { flex: "0 0 65%", position: "relative", overflow: "hidden" },
  canvas:     { width: "100%", height: "100%" },
  upBtn:      { position: "absolute", top: 16, left: 16, background: "rgba(10,14,28,0.85)", border: "1px solid #2a4060", color: "#3a8eff", padding: "6px 14px", cursor: "pointer", fontFamily: "Courier New, monospace", fontSize: "12px", zIndex: 10, letterSpacing: "0.05em" },
  switchLink: { position: "absolute", bottom: 12, left: 16, fontSize: "10px", color: "#2a3555", textDecoration: "none", letterSpacing: "0.08em" },
};

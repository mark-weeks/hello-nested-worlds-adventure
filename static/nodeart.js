// Per-node generative art — every place in the multiverse has a visual
// identity of its own, drawn deterministically from (seed, node): the same
// node always paints the same, two nodes never paint alike, and the painting
// is a visual expression of what the node IS (properties) and what has
// HAPPENED to it (ripple pressure, causal effect marks, activity).
//
// Pure 2D canvas — no WebGL, no vendor key, no network. This is the
// always-present base layer of the scene; the fal.ai image, when available,
// is an enhancement washed over it. Shared verbatim by the React client
// (ES import) and the D3 explorer (via /nodeart-global.js), with Vitest
// determinism/distinctness tests in frontend/src/__tests__/nodeart.test.js.

// ── Deterministic randomness ────────────────────────────────────────────────

export function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Level baselines ─────────────────────────────────────────────────────────
// Base hue (degrees) and form family per scale. The node's own hash swings
// the hue and every structural parameter, so siblings at the same level
// still read as different places.

const LEVEL_BASE = {
  Multiverse:          { hue: 262, family: "folds" },
  Universe:            { hue: 230, family: "filaments" },
  Galaxy:              { hue: 215, family: "spiral" },
  "Planetary System":  { hue: 190, family: "orbits" },
  Planet:              { hue: 150, family: "horizon" },
  Region:              { hue: 95,  family: "ridges" },
  Room:                { hue: 30,  family: "panels" },
  Object:              { hue: 45,  family: "sigil" },
  Molecule:            { hue: 175, family: "bonds" },
  Atom:                { hue: 205, family: "shells" },
  SubatomicParticle:   { hue: 285, family: "speckle" },
};

const BIOME_HUES = { tundra: 195, jungle: 130, desert: 45, ocean: 210,
                     volcanic: 15, temperate: 110, irradiated: 80 };

// ── Parameter derivation (pure — unit-tested) ───────────────────────────────

export function nodeArtParams(seed, node) {
  const props = node.properties || {};
  const base = LEVEL_BASE[node.level] || { hue: 220, family: "speckle" };
  const h = hashString(`${seed}:${node.name}`);
  const rng = mulberry32(h);

  let hue = (base.hue + Math.floor(rng() * 70) - 35 + 360) % 360;
  if (props.biome in BIOME_HUES) hue = BIOME_HUES[props.biome];

  const pressure = Math.max(0, Math.min(1, node.ripple_score || 0));
  const danger = typeof props.danger_level === "number" ? props.danger_level : 0;

  return {
    family: base.family,
    prng: h,
    hue,
    // What has happened here bends how it looks:
    saturation: Math.round(38 + pressure * 42),        // pressure saturates
    jitter: (props.disturbed ? 2.5 : 0) + pressure * 4, // unrest shakes lines
    glitch: props.condition === "corrupted",            // matter mis-slices
    halo: !!props.stabilized,                           // settled places glow
    dangerVignette: danger >= 7,
    activity: Math.max(0, Math.min(48, node.activity || 0)), // trace etchings
    // Structural inputs per family:
    density: Math.round(3 + rng() * 6),
    count: Math.round(
      props.star_density ? 40 + (props.star_density / 500) * 160 :
      props.planet_count ? props.planet_count :
      props.bond_count ? props.bond_count :
      props.moons != null ? 3 + props.moons :
      props.exits ? 2 + props.exits * 2 :
      4 + rng() * 8),
    lighting: props.lighting || "",
    shape: props.shape || "",
    spin: props.spin || "",
    coherence: typeof props.coherence === "number" ? props.coherence : 0.6,
    atomicNumber: props.atomic_number || 8,
  };
}

// ── Rendering ───────────────────────────────────────────────────────────────

function hsl(h, s, l, a = 1) {
  return `hsla(${h}, ${s}%, ${l}%, ${a})`;
}

export function drawNodeArt(canvas, seed, node) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const W = canvas.width, H = canvas.height;
  const p = nodeArtParams(seed, node);
  const rng = mulberry32(p.prng);
  const jitter = () => (rng() - 0.5) * 2 * p.jitter;

  // Ground: a deep gradient in the node's own hue.
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, hsl(p.hue, p.saturation, 7));
  grad.addColorStop(1, hsl((p.hue + 25) % 360, p.saturation, 13));
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  const cx = W / 2, cy = H / 2, R = Math.min(W, H);

  const FAMILIES = {
    folds() { // Multiverse: nested irregular rings, everything enfolding
      for (let i = p.density + 3; i > 0; i--) {
        ctx.beginPath();
        const r = (R * 0.46 * i) / (p.density + 3);
        for (let a = 0; a <= Math.PI * 2 + 0.1; a += 0.22) {
          const wobble = 1 + 0.12 * Math.sin(a * (2 + (i % 3)) + i) + jitter() / 80;
          const x = cx + Math.cos(a) * r * wobble;
          const y = cy + Math.sin(a) * r * wobble * 0.72;
          if (a === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = hsl((p.hue + i * 9) % 360, p.saturation, 32 + i * 4, 0.5);
        ctx.lineWidth = 1.1;
        ctx.stroke();
      }
    },
    filaments() { // Universe: a cosmic web of strands and knots
      const pts = Array.from({ length: 9 + p.density }, () =>
        [rng() * W, rng() * H]);
      ctx.lineWidth = 0.8;
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const d = Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]);
          if (d < R * 0.5) {
            ctx.beginPath();
            ctx.moveTo(pts[i][0] + jitter(), pts[i][1] + jitter());
            ctx.lineTo(pts[j][0] + jitter(), pts[j][1] + jitter());
            ctx.strokeStyle = hsl(p.hue, p.saturation, 40, 0.75 - d / (R * 0.8));
            ctx.stroke();
          }
        }
      }
      for (const [x, y] of pts) {
        ctx.beginPath();
        ctx.arc(x, y, 1.6 + rng() * 2.2, 0, Math.PI * 2);
        ctx.fillStyle = hsl(p.hue, p.saturation + 12, 62, 0.9);
        ctx.fill();
      }
    },
    spiral() { // Galaxy: arms of stars
      const arms = p.shape === "ring" ? 0 : p.shape === "elliptical" ? 1 :
                   p.shape === "irregular" ? 5 : 2 + (p.prng % 2);
      for (let i = 0; i < p.count; i++) {
        const t = rng() * 5.2;
        const arm = Math.floor(rng() * Math.max(1, arms));
        const ang = arms === 0 ? rng() * Math.PI * 2
          : t + (arm * Math.PI * 2) / Math.max(1, arms) + jitter() / 22;
        const r = arms === 0 ? R * 0.3 + jitter() * 2.5
          : (t / 5.2) * R * 0.44;
        const x = cx + Math.cos(ang) * r;
        const y = cy + Math.sin(ang) * r * 0.62;
        ctx.beginPath();
        ctx.arc(x, y, rng() < 0.9 ? 0.9 : 2.1, 0, Math.PI * 2);
        ctx.fillStyle = hsl((p.hue + rng() * 40) % 360, p.saturation, 55 + rng() * 30, 0.85);
        ctx.fill();
      }
      const core = ctx.createRadialGradient(cx, cy, 1, cx, cy, R * 0.13);
      core.addColorStop(0, hsl(p.hue, 30, 88, 0.9));
      core.addColorStop(1, hsl(p.hue, 40, 40, 0));
      ctx.fillStyle = core;
      ctx.fillRect(0, 0, W, H);
    },
    orbits() { // Planetary System: nested ellipses, bodies on them
      const n = Math.max(1, Math.min(12, p.count));
      for (let i = 1; i <= n; i++) {
        const rx = (R * 0.46 * i) / n, ry = rx * 0.4;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.strokeStyle = hsl(p.hue, p.saturation, 34, 0.55);
        ctx.lineWidth = 0.8;
        ctx.stroke();
        const a = rng() * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry,
                1.6 + rng() * 2.6, 0, Math.PI * 2);
        ctx.fillStyle = hsl((p.hue + i * 24) % 360, p.saturation + 15, 60);
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(cx, cy, 5 + rng() * 3, 0, Math.PI * 2);
      ctx.fillStyle = hsl(45, 80, 70);
      ctx.fill();
    },
    horizon() { // Planet: a limb of the world against its sky
      const horizonY = H * (0.55 + rng() * 0.2);
      for (let i = 0; i < 4; i++) { // sky bands
        ctx.fillStyle = hsl((p.hue + 180 + i * 8) % 360, p.saturation - 8,
                            16 + i * 5, 0.5);
        ctx.fillRect(0, (horizonY / 4) * i + jitter(), W, horizonY / 4 + 2);
      }
      ctx.beginPath(); // the planet limb
      ctx.ellipse(cx, horizonY + R * 0.75, R * 1.05, R * 0.78, 0, Math.PI, 0);
      ctx.fillStyle = hsl(p.hue, p.saturation + 8, 22);
      ctx.fill();
      ctx.beginPath(); // atmosphere line
      ctx.ellipse(cx, horizonY + R * 0.75, R * 1.05, R * 0.78, 0, Math.PI, 0);
      ctx.strokeStyle = hsl(p.hue, p.saturation + 20, 60, 0.8);
      ctx.lineWidth = 1.6;
      ctx.stroke();
      for (let m = 0; m < Math.min(8, p.count); m++) { // moons
        ctx.beginPath();
        ctx.arc(W * (0.1 + rng() * 0.8), horizonY * (0.15 + rng() * 0.6),
                1.2 + rng() * 2, 0, Math.PI * 2);
        ctx.fillStyle = hsl(0, 0, 78, 0.9);
        ctx.fill();
      }
    },
    ridges() { // Region: receding terrain lines
      const layers = 5 + (p.density % 3);
      for (let l = 0; l < layers; l++) {
        const baseY = H * (0.35 + (l / layers) * 0.6);
        ctx.beginPath();
        ctx.moveTo(0, H);
        for (let x = 0; x <= W; x += 8) {
          const y = baseY
            + Math.sin(x / (26 + l * 9) + l * 7 + p.prng % 10) * (9 + l * 3)
            + jitter();
          ctx.lineTo(x, y);
        }
        ctx.lineTo(W, H);
        ctx.closePath();
        ctx.fillStyle = hsl((p.hue + l * 6) % 360, p.saturation,
                            10 + l * 5, 0.85);
        ctx.fill();
      }
    },
    panels() { // Room: rectilinear interior, one light source
      const cols = 3 + (p.count % 4);
      for (let i = 0; i < cols * 2; i++) {
        const x = rng() * W * 0.9, y = rng() * H * 0.7;
        const w = 20 + rng() * (W / cols), h = 24 + rng() * (H * 0.4);
        ctx.fillStyle = hsl(p.hue, p.saturation - 10, 12 + rng() * 12, 0.9);
        ctx.fillRect(x + jitter(), y + jitter(), w, h);
        ctx.strokeStyle = hsl(p.hue, p.saturation, 34, 0.6);
        ctx.strokeRect(x, y, w, h);
      }
      const lx = W * (0.2 + rng() * 0.6), ly = H * (0.1 + rng() * 0.25);
      const lum = { bright: 0.5, dim: 0.28, dark: 0.12, flickering: 0.38 }[p.lighting] ?? 0.3;
      const light = ctx.createRadialGradient(lx, ly, 2, lx, ly, R * 0.7);
      light.addColorStop(0, hsl(42, 60, 75, lum));
      light.addColorStop(1, hsl(42, 60, 40, 0));
      ctx.fillStyle = light;
      ctx.fillRect(0, 0, W, H);
    },
    sigil() { // Object: one made thing, centered
      const sides = 3 + (p.prng % 6);
      const r = R * 0.3;
      ctx.beginPath();
      for (let i = 0; i <= sides; i++) {
        const a = (i / sides) * Math.PI * 2 - Math.PI / 2;
        const rr = r * (1 + (i % 2) * (0.18 + rng() * 0.2));
        const x = cx + Math.cos(a) * rr + jitter();
        const y = cy + Math.sin(a) * rr + jitter();
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = hsl(p.hue, p.saturation, 20, 0.95);
      ctx.fill();
      ctx.strokeStyle = hsl(p.hue, p.saturation + 18, 55);
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.beginPath(); // the maker's mark
      ctx.arc(cx, cy, r * 0.28, 0, Math.PI * 2);
      ctx.strokeStyle = hsl((p.hue + 40) % 360, p.saturation + 10, 62, 0.9);
      ctx.stroke();
    },
    bonds() { // Molecule: a committee of atoms voting by attraction
      const n = Math.max(3, Math.min(12, p.count));
      const pts = Array.from({ length: n }, (_, i) => {
        const a = (i / n) * Math.PI * 2 + rng() * 0.7;
        const r = R * (0.16 + rng() * 0.22);
        return [cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.8];
      });
      ctx.lineWidth = 1.4;
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n, k = (i + 2 + (p.prng % 3)) % n;
        for (const t of [j, k]) {
          ctx.beginPath();
          ctx.moveTo(pts[i][0] + jitter(), pts[i][1] + jitter());
          ctx.lineTo(pts[t][0] + jitter(), pts[t][1] + jitter());
          ctx.strokeStyle = hsl(p.hue, p.saturation, 42, 0.7);
          ctx.stroke();
        }
      }
      for (const [x, y] of pts) {
        ctx.beginPath();
        ctx.arc(x, y, 3.4 + rng() * 3, 0, Math.PI * 2);
        ctx.fillStyle = hsl((p.hue + rng() * 50) % 360, p.saturation + 12, 52);
        ctx.fill();
      }
    },
    shells() { // Atom: a certainty and a cloud
      const shells = Math.max(1, Math.min(7, Math.ceil(p.atomicNumber / 16)));
      for (let i = 1; i <= shells; i++) {
        ctx.beginPath();
        ctx.arc(cx, cy, (R * 0.42 * i) / shells, 0, Math.PI * 2);
        ctx.strokeStyle = hsl(p.hue, p.saturation, 40, 0.5);
        ctx.lineWidth = 0.9;
        ctx.stroke();
        const a = rng() * Math.PI * 2; // an electron mid-thought
        ctx.beginPath();
        ctx.arc(cx + Math.cos(a) * (R * 0.42 * i) / shells,
                cy + Math.sin(a) * (R * 0.42 * i) / shells,
                1.8, 0, Math.PI * 2);
        ctx.fillStyle = hsl((p.hue + 30) % 360, 70, 68);
        ctx.fill();
      }
      const nucleus = ctx.createRadialGradient(cx, cy, 1, cx, cy, 9);
      nucleus.addColorStop(0, hsl(p.hue, 60, 82));
      nucleus.addColorStop(1, hsl(p.hue, 70, 38, 0.2));
      ctx.fillStyle = nucleus;
      ctx.fillRect(cx - 12, cy - 12, 24, 24);
    },
    speckle() { // SubatomicParticle: a rumor of position
      const spread = 1.15 - p.coherence * 0.7; // coherent = tight cloud
      for (let i = 0; i < 260; i++) {
        const a = rng() * Math.PI * 2;
        const r = Math.abs(rng() + rng() - 1) * R * 0.45 * spread;
        ctx.beginPath();
        ctx.arc(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.8,
                0.7 + rng() * 1.1, 0, Math.PI * 2);
        ctx.fillStyle = hsl((p.hue + rng() * 60) % 360, p.saturation + 20,
                            50 + rng() * 35, 0.35 + p.coherence * 0.5);
        ctx.fill();
      }
    },
  };

  (FAMILIES[p.family] || FAMILIES.speckle)();

  // ── The marks the world has left ──────────────────────────────────────────
  if (p.halo) { // stabilized: a settled, symmetric ring
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.47, 0, Math.PI * 2);
    ctx.strokeStyle = hsl(165, 70, 62, 0.55);
    ctx.lineWidth = 1.4;
    ctx.stroke();
  }
  if (p.dangerVignette) { // danger: the edges run hot
    const v = ctx.createRadialGradient(cx, cy, R * 0.35, cx, cy, R * 0.75);
    v.addColorStop(0, "rgba(0,0,0,0)");
    v.addColorStop(1, hsl(4, 75, 30, 0.5));
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, W, H);
  }
  if (p.glitch) { // corrupted: slices of the image mis-remember their place
    for (let i = 0; i < 5; i++) {
      const y = rng() * H, h = 3 + rng() * 7, dx = (rng() - 0.5) * 26;
      const slice = ctx.getImageData(0, y, W, h);
      ctx.putImageData(slice, dx, y);
    }
  }
  // Activity etchings: every ~interaction leaves a small tick on the border.
  ctx.strokeStyle = hsl(p.hue, 30, 70, 0.6);
  ctx.lineWidth = 1;
  for (let i = 0; i < p.activity; i++) {
    const a = (i / 48) * Math.PI * 2;
    const r1 = R * 0.485, r2 = R * 0.5;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
    ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
    ctx.stroke();
  }
}

// Per-node ambient sound — the audible third of each node's personality,
// alongside its generative art and its voice. Pure WebAudio synthesis (no
// assets, no network), deterministic in (seed, node): the same place plays
// the same endless piece for every visitor, forever.
//
// Unlike node NAMES and era names (frozen compatibility surfaces — see
// tests/test_continuity_freeze.py), sound is derived at listen time and
// nothing durable keys on it. These mappings are FREELY TUNABLE: retune
// modes, voicings, and textures at will; only determinism (all randomness
// from the node's seeded PRNG, no wall-clock) and the quiet master gain
// are contracts.
//
// The arrangement, per node:
//   * HARMONY — a mode and root chosen from what the node IS: danger
//     darkens toward Phrygian, corruption goes eerie (insen), a
//     stabilized place brightens to Lydian; the root's pitch class comes
//     from the art's hue, so a place sounds the color it looks.
//   * PAD — three detuned voices (root / fifth / color tone) through a
//     slowly breathing lowpass. Deep scales sit low and dark; small
//     scales sit high and glassy.
//   * SUB — a near-inaudible foundation an octave below the root.
//   * TEXTURE — filtered noise whose band comes from the node's own
//     atmosphere properties (air, weather, glow, membrane, sky…).
//   * EVENTS — a generative music box: sparse, scale-locked bell tones
//     sequenced by the node's PRNG. A Multiverse chimes every ~9–16s;
//     a particle sparkles every ~2–5s. Causal pressure and accumulated
//     activity make a place audibly busier.
//   * SPACE — a cross-feedback delay pair, damped, wider and longer for
//     stabilized (haloed) places.
//   * HISTORY MARKS — activity adds tape-like pitch wow (the audible
//     wear the art draws as etchings); corruption gates slow dropouts
//     (the audible glitch); danger roughens the pad unless warded calm.
import { hashString, mulberry32, nodeArtParams } from "./nodeart.js";

// Root register per scale (MIDI, C-based). Events ring one to two octaves
// above; the sub sits one below (floored so nothing disappears into DC).
const LEVEL_ROOT_MIDI = {
  Multiverse: 24, Universe: 26, Galaxy: 29, "Planetary System": 31,
  Planet: 34, Region: 38, Room: 43, Object: 48,
  Molecule: 53, Atom: 57, SubatomicParticle: 62,
};
const LEVEL_INDEX = Object.keys(LEVEL_ROOT_MIDI);

// Modes as semitone sets — the emotional vocabulary. Tunable freely.
const MODES = {
  lydian:    [0, 2, 4, 6, 7, 9, 11],  // stabilized: bright, floating
  majorPent: [0, 2, 4, 7, 9],         // calm default: open, songful
  mixolydian:[0, 2, 4, 5, 7, 9, 10],  // calm default: warm, unresolved
  dorian:    [0, 2, 3, 5, 7, 9, 10],  // calm default: gentle melancholy
  aeolian:   [0, 2, 3, 5, 7, 8, 10],  // uneasy: minor gravity
  phrygian:  [0, 1, 3, 5, 7, 8, 10],  // danger: the flat second looms
  insen:     [0, 1, 5, 7, 10],        // corrupted: hollow, eerie
};

const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);

function _chooseMode(props, rng) {
  const danger = Number(props?.danger_level) || 0;
  if (props?.condition === "corrupted") return "insen";
  if ((danger >= 7 || props?.disturbed) && !props?.stabilized) return "phrygian";
  if (props?.stabilized) return "lydian";
  if (danger >= 4) return "aeolian";
  return ["majorPent", "mixolydian", "dorian"][Math.floor(rng() * 3)];
}

function _textureBand(props, rng) {
  // The noise layer's character comes from the node's own atmosphere.
  for (const key of ["air", "weather", "glow", "membrane", "sky", "dust",
                     "light_temper", "lighting"]) {
    if (props && props[key] !== undefined) {
      const r = mulberry32(hashString(`tex:${key}:${props[key]}`));
      return { center: 220 + r() * 2200, q: 0.7 + r() * 4 };
    }
  }
  return { center: 400 + rng() * 800, q: 1.2 };
}

export function soundscapeParams(seed, node) {
  const art = nodeArtParams(seed, node);
  const rng = mulberry32(hashString(`${seed}:${node.name}:sound`));
  const props = node.properties || {};
  const levelIdx = Math.max(0, LEVEL_INDEX.indexOf(node.level));
  const depth01 = levelIdx / (LEVEL_INDEX.length - 1); // 0=Multiverse … 1=Particle

  // Root: the level's register, pitched by the art's hue — a place sounds
  // the color it looks. Slight per-node offset keeps siblings apart.
  const pitchClass = Math.floor(((art.hue % 360) / 360) * 12);
  const rootMidi = (LEVEL_ROOT_MIDI[node.level] ?? 43) + pitchClass;
  const rootHz = midiHz(rootMidi);

  const modeName = _chooseMode(props, rng);
  const scale = MODES[modeName];

  // Pad voicing: root, fifth, and a color tone from the mode (3rd degree
  // or, for pentatonics, the 2nd) — one voice a few cents wide.
  const colorInterval = scale.length >= 7 ? scale[2] : scale[1];
  const rough = (Number(props.danger_level) || 0) >= 6 && !props.stabilized;
  const pad = {
    freqs: [rootHz, midiHz(rootMidi + 7), midiHz(rootMidi + 12 + colorInterval)],
    detuneCents: rough ? 22 + rng() * 14 : 4 + rng() * 6,
    filterBase: rootHz * (3 + rng() * 2),
    filterSweepHz: 0.02 + rng() * 0.05,   // minutes-long spectral weather
    breatheHz: 0.05 + rng() * 0.07,       // incommensurate with the sweep
    gain: 0.5,
  };

  const sub = { freq: Math.max(27, rootHz / 2), gain: 0.35 };
  const texture = { ..._textureBand(props, rng), gain: rough ? 0.2 : 0.12 };

  // The music box: sparse at cosmic scales, quick at quantum ones; causal
  // pressure and lived-in activity make a place audibly busier.
  const busy = Math.min(0.35, art.jitter * 0.05 + art.activity * 0.004);
  const intervalMin = (9 - 6.8 * depth01) * (1 - busy);
  const eventOctave = depth01 > 0.6 ? 24 : 12;
  const events = {
    intervalMin,
    intervalMax: intervalMin * (1.7 + rng() * 0.3),
    notePool: scale.map(s => midiHz(rootMidi + eventOctave + s))
      .concat(scale.slice(0, 3).map(s => midiHz(rootMidi + eventOctave + 12 + s))),
    decay: 4.2 - 2.6 * depth01,          // long cosmic bells, quick sparkles
    type: depth01 > 0.5 ? "triangle" : "sine",
    gain: 0.4,
  };

  const space = {
    delayA: 0.23 + rng() * 0.1,
    delayB: 0.41 + rng() * 0.12,
    feedback: art.halo ? 0.42 : 0.3,     // stabilized places ring longer
    damp: 2800,
    send: art.halo ? 0.5 : 0.35,
  };

  return {
    rootMidi, rootHz, mode: modeName, scale,
    pad, sub, texture, events, space,
    // History, audible: wear-wow from accumulated activity; dropout gating
    // for corrupted matter; shimmer partial for the stabilized halo.
    wow: { depthCents: Math.min(12, art.activity * 0.3), rateHz: 0.13 },
    dropouts: !!art.glitch,
    shimmer: !!art.halo,
    rough,
    gain: 0.05,                          // ambience, never music-forward
    // Legacy convenience fields (kept for callers/tests of the first cut).
    freq: rootHz,
  };
}

// Back-compat alias: the original thin API name.
export const ambienceParams = soundscapeParams;


export class NodeAmbience {
  constructor() {
    this.ctx = null;
    this.graph = null;      // active layer nodes for teardown
    this.timer = null;      // event-scheduler interval id
    this.enabled = false;
    this.current = null;
  }

  enable(seed, node) {
    this.enabled = true;
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      this.ctx = new AC();
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
    if (node) this.setNode(seed, node);
  }

  disable() {
    this.enabled = false;
    this._stop();
  }

  setNode(seed, node) {
    if (!this.enabled || !this.ctx || !node) return;
    const key = `${seed}:${node.name}`;
    if (this.current === key) return;
    this.current = key;
    this._stop();
    this._start(soundscapeParams(seed, node),
                mulberry32(hashString(`${key}:performance`)));
  }

  _start(p, prng) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const stopFns = [];
    const oscs = [];

    // Master chain: everything → gentle compressor → destination. The
    // compressor is seatbelt, not sound: it only acts if layers gang up.
    const master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, t);
    master.gain.exponentialRampToValueAtTime(p.gain, t + 2.5);
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -28; comp.knee.value = 20; comp.ratio.value = 6;
    comp.attack.value = 0.01; comp.release.value = 0.3;
    master.connect(comp);
    comp.connect(ctx.destination);

    // Space: two cross-fed damped delays; pads and bells send into it.
    const send = ctx.createGain(); send.gain.value = p.space.send;
    const dA = ctx.createDelay(1.0); dA.delayTime.value = p.space.delayA;
    const dB = ctx.createDelay(1.0); dB.delayTime.value = p.space.delayB;
    const fbA = ctx.createGain(); fbA.gain.value = p.space.feedback;
    const fbB = ctx.createGain(); fbB.gain.value = p.space.feedback;
    const damp = ctx.createBiquadFilter();
    damp.type = "lowpass"; damp.frequency.value = p.space.damp;
    send.connect(dA); dA.connect(fbA); fbA.connect(dB);
    dB.connect(fbB); fbB.connect(damp); damp.connect(dA);
    dA.connect(master); dB.connect(master);

    // PAD — three voices through a breathing lowpass.
    const padOut = ctx.createGain(); padOut.gain.value = 0;
    const padFilter = ctx.createBiquadFilter();
    padFilter.type = "lowpass";
    padFilter.frequency.value = p.pad.filterBase;
    padFilter.Q.value = 0.9;
    padFilter.connect(padOut);
    padOut.connect(master); padOut.connect(send);
    const detunes = [0, -p.pad.detuneCents, p.pad.detuneCents];
    p.pad.freqs.forEach((f, i) => {
      const o = ctx.createOscillator();
      o.type = p.rough && i === 1 ? "sawtooth" : "sine";
      o.frequency.value = f;
      o.detune.value = detunes[i % 3];
      const g = ctx.createGain();
      g.gain.value = [0.5, 0.32, 0.2][i % 3];
      o.connect(g); g.connect(padFilter);
      o.start(t); oscs.push(o);
    });
    // Spectral weather: a minutes-long filter sweep + slow breathing, at
    // incommensurate rates so the drone never audibly loops.
    const sweep = ctx.createOscillator(); sweep.frequency.value = p.pad.filterSweepHz;
    const sweepAmt = ctx.createGain(); sweepAmt.gain.value = p.pad.filterBase * 0.45;
    sweep.connect(sweepAmt); sweepAmt.connect(padFilter.frequency);
    sweep.start(t); oscs.push(sweep);
    const breathe = ctx.createOscillator(); breathe.frequency.value = p.pad.breatheHz;
    const breatheAmt = ctx.createGain(); breatheAmt.gain.value = p.pad.gain * 0.25;
    breathe.connect(breatheAmt); breatheAmt.connect(padOut.gain);
    breathe.start(t); oscs.push(breathe);
    padOut.gain.setValueAtTime(0.0001, t);
    padOut.gain.exponentialRampToValueAtTime(p.pad.gain, t + 3);

    // History wow: accumulated activity bends the pad like worn tape.
    if (p.wow.depthCents > 0.5) {
      const wow = ctx.createOscillator(); wow.frequency.value = p.wow.rateHz;
      const wowAmt = ctx.createGain(); wowAmt.gain.value = p.wow.depthCents;
      wow.connect(wowAmt);
      // Bend every pad voice together — the whole memory warps at once.
      for (const o of oscs.slice(0, 3)) wowAmt.connect(o.detune);
      wow.start(t); oscs.push(wow);
    }

    // Corruption: slow square gating — the drone drops out and recovers.
    if (p.dropouts) {
      const gate = ctx.createOscillator();
      gate.type = "square"; gate.frequency.value = 0.09 + prng() * 0.05;
      const gateAmt = ctx.createGain(); gateAmt.gain.value = p.pad.gain * 0.35;
      gate.connect(gateAmt); gateAmt.connect(padOut.gain);
      gate.start(t); oscs.push(gate);
    }

    // SUB — the foundation, felt more than heard.
    const subOsc = ctx.createOscillator();
    subOsc.type = "sine"; subOsc.frequency.value = p.sub.freq;
    const subGain = ctx.createGain(); subGain.gain.value = p.sub.gain;
    subOsc.connect(subGain); subGain.connect(master);
    subOsc.start(t); oscs.push(subOsc);

    // TEXTURE — the node's atmosphere as filtered noise (deterministic
    // buffer from the node's own PRNG).
    const noiseLen = 2 * ctx.sampleRate;
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const data = noiseBuf.getChannelData(0);
    for (let i = 0; i < noiseLen; i++) data[i] = prng() * 2 - 1;
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuf; noise.loop = true;
    const band = ctx.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = p.texture.center; band.Q.value = p.texture.q;
    const texGain = ctx.createGain(); texGain.gain.value = p.texture.gain;
    noise.connect(band); band.connect(texGain); texGain.connect(master);
    noise.start(t); oscs.push(noise);

    // EVENTS — the generative music box. A lookahead scheduler walks the
    // node's own deterministic sequence of scale-locked bells.
    let nextAt = t + 1.2 + prng() * 1.5;
    const scheduleAhead = 0.5;
    const tick = () => {
      const now = ctx.currentTime;
      while (nextAt < now + scheduleAhead) {
        const f = p.events.notePool[Math.floor(prng() * p.events.notePool.length)];
        this._bell(ctx, f, nextAt, p, send, master);
        nextAt += p.events.intervalMin +
          prng() * (p.events.intervalMax - p.events.intervalMin);
      }
    };
    tick();
    this.timer = setInterval(tick, 200);
    stopFns.push(() => clearInterval(this.timer));

    this.graph = { master, oscs, stopFns };
  }

  _bell(ctx, freq, at, p, send, master) {
    // A two-partial bell: fundamental + quiet octave (or twelfth when the
    // place is haloed — the stabilization shimmer).
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(p.events.gain, at + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, at + p.events.decay);
    g.connect(master); g.connect(send);
    const partials = p.shimmer ? [[freq, 1], [freq * 2, 0.2], [freq * 3, 0.12]]
                               : [[freq, 1], [freq * 2, 0.18]];
    for (const [f, amt] of partials) {
      const o = ctx.createOscillator();
      o.type = p.events.type; o.frequency.value = f;
      const og = ctx.createGain(); og.gain.value = amt;
      o.connect(og); og.connect(g);
      o.start(at); o.stop(at + p.events.decay + 0.1);
    }
  }

  _stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    if (!this.graph || !this.ctx) return;
    const { master, oscs, stopFns } = this.graph;
    const t = this.ctx.currentTime;
    try {
      for (const fn of stopFns) fn();
      master.gain.cancelScheduledValues(t);
      master.gain.setValueAtTime(Math.max(master.gain.value, 0.0001), t);
      master.gain.exponentialRampToValueAtTime(0.0001, t + 0.6); // fade out
      for (const o of oscs) o.stop(t + 0.7);
    } catch (_) { /* context may already be closed */ }
    this.graph = null;
    if (!this.enabled) this.current = null;
  }
}

// Per-node ambient sound — the audible face of the same identity the art
// draws. Pure WebAudio synthesis (no assets, no network), deterministic in
// (seed, node): the same place hums the same way for every visitor, forever.
//
// The mapping mirrors nodeart.js's visual grammar:
//   * scale depth → register (a Multiverse drones low, a particle sings high)
//   * the node's hue swing → detune between the two voices (its "chord")
//   * causal jitter → tremolo depth (a pressured place wavers)
//   * danger → a rough dissonant beat; stabilized → the voices lock pure
//
// Off by default; browsers require a user gesture to start audio anyway, so
// the toggle in each client is both the consent and the activation.
import { hashString, mulberry32, nodeArtParams } from "./nodeart.js";

// Register per scale: deepest structures lowest. Frequencies avoid plain
// octaves so adjacent scales feel related but distinct.
const LEVEL_FREQ = {
  Multiverse: 55, Universe: 73.4, Galaxy: 98, "Planetary System": 130.8,
  Planet: 164.8, Region: 220, Room: 293.7, Object: 392,
  Molecule: 523.3, Atom: 659.3, SubatomicParticle: 880,
};

export function ambienceParams(seed, node) {
  const p = nodeArtParams(seed, node);
  const rng = mulberry32(hashString(`${seed}:${node.name}:sound`));
  const base = LEVEL_FREQ[node.level] || 220;
  const danger = Number(node.properties?.danger_level) || 0;
  return {
    freq: base * (1 + (rng() - 0.5) * 0.06),   // each place slightly off-center
    detuneCents: 4 + Math.round((p.hue % 30)), // the node's own beat interval
    tremHz: 0.1 + p.jitter * 3.0,
    tremDepth: 0.15 + p.jitter * 0.5,
    rough: danger >= 6 && !node.properties?.stabilized,
    gain: 0.035,                                // ambience, not music
  };
}

export class NodeAmbience {
  constructor() {
    this.ctx = null;
    this.nodes = null;
    this.enabled = false;
    this.current = null; // {seed, name} of what is sounding
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
    this._start(ambienceParams(seed, node));
  }

  _start(p) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, t);
    master.gain.exponentialRampToValueAtTime(p.gain, t + 1.5); // fade in
    master.connect(ctx.destination);

    const voiceA = ctx.createOscillator();
    voiceA.type = "sine";
    voiceA.frequency.value = p.freq;

    const voiceB = ctx.createOscillator();
    voiceB.type = p.rough ? "sawtooth" : "sine";
    voiceB.frequency.value = p.freq;
    voiceB.detune.value = p.rough ? 35 : p.detuneCents;
    const bGain = ctx.createGain();
    bGain.gain.value = p.rough ? 0.25 : 0.6;

    const trem = ctx.createOscillator();
    trem.frequency.value = p.tremHz;
    const tremGain = ctx.createGain();
    tremGain.gain.value = p.tremDepth * p.gain;
    trem.connect(tremGain);
    tremGain.connect(master.gain);

    voiceA.connect(master);
    voiceB.connect(bGain);
    bGain.connect(master);
    voiceA.start(t); voiceB.start(t); trem.start(t);
    this.nodes = { master, oscs: [voiceA, voiceB, trem] };
  }

  _stop() {
    if (!this.nodes || !this.ctx) return;
    const { master, oscs } = this.nodes;
    const t = this.ctx.currentTime;
    try {
      master.gain.cancelScheduledValues(t);
      master.gain.setValueAtTime(Math.max(master.gain.value, 0.0001), t);
      master.gain.exponentialRampToValueAtTime(0.0001, t + 0.4); // fade out
      for (const o of oscs) o.stop(t + 0.5);
    } catch (_) { /* context may already be closed */ }
    this.nodes = null;
    if (!this.enabled) this.current = null;
  }
}

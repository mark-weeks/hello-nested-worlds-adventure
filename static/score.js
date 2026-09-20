// A continuous, sample-based score. World state chooses orchestration; the audio
// clock owns phrasing. Recorded performances and room tails survive node changes.
export function scoreDirection(node) {
  const s = node?.senses || {};
  const root = [48, 50, 53, 55][s.family ?? 0] || 48;
  const minor = s.polarity < 0 || s.tension > .6;
  const memory = s.memory ? parseInt(s.memory.slice(0, 4), 16) || 0 : 0;
  return {root, third: minor ? 3 : 4, tension: s.tension || 0,
    energy: s.energy || 0, echo: s.echo || 0, woven: !!s.woven,
    register: ['Molecule','Atom','SubatomicParticle'].includes(node?.level) ? 7 : node?.level === 'Object' ? 3 : 0,
    motif: memory % 4, atmosphere: s.atmosphere || 'still',
    bright: s.texture === 'filament' || s.texture === 'crystalline',
    revision: s.revision || node?.name || '', name: node?.name};
}
const FILES = {cello: 48, violin: 60, harp: 48, harp_high: 72, flute: 60, tremolo: 60};
const MELODY = [[0, 7, 12, 4, 9, 7, 2, 0], [0, 2, 7, 9, 12, 7, 4, 2],
  [12, 7, 9, 4, 7, 2, 4, 0], [0, 4, 2, 7, 4, 12, 9, 7]];
const BEAT = .9;
export class NodeAmbience {
  constructor() { this.enabled = false; this.buffers = {}; this.volume = .55; this.sources = new Set(); }
  enable(seed, node) {
    if (this.enabled) { this.setNode(seed, node); return true; }
    const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AC) return false;
    this.ctx ||= new AC();
    this.ctx.resume().catch(() => {});
    if (!this.master) {
      const ctx = this.ctx;
      this.master = ctx.createGain(); this.master.gain.value = this.volume;
      const limit = ctx.createDynamicsCompressor();
      limit.threshold.value = -14; limit.knee.value = 10; limit.ratio.value = 8;
      this.master.connect(limit); limit.connect(ctx.destination);
      this.room = ctx.createConvolver();
      const impulse = ctx.createBuffer(2, ctx.sampleRate * 2.8, ctx.sampleRate);
      for (let c = 0; c < 2; c++) {
        const data = impulse.getChannelData(c);
        for (let i = 0; i < data.length; i++) data[i] = Math.sin(i * (1.711 + c * .133)) * Math.sin(i * .173) * Math.pow(1 - i / data.length, 3) * .32;
      }
      this.room.buffer = impulse;
      const wet = ctx.createGain(); wet.gain.value = .32;
      this.room.connect(wet); wet.connect(this.master);
    }
    this.enabled = true;
    this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, .2);
    this.pending = this.direction = scoreDirection(node);
    this.step = 0; this.next = this.ctx.currentTime + .1;
    this.loading ||= Promise.all(Object.keys(FILES).map(async name => {
      try {
        const response = await fetch(`/media/score/${name}.mp3`);
        if (!response.ok) throw new Error('sample unavailable');
        this.buffers[name] = await this.ctx.decodeAudioData(await response.arrayBuffer());
      } catch (_) { /* The score remains silent until actual instruments are available. */ }
    }));
    this.timer = setInterval(() => this.schedule(), 80);
    return true;
  }
  setVolume(value) {
    this.volume = Math.max(0, Math.min(1, Number(value) || 0));
    if (this.master && this.enabled) this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, .2);
  }
  setNode(seed, node) {
    const next = scoreDirection(node);
    if (this.pending?.revision === next.revision && this.pending?.name === next.name) return;
    const previous = this.pending;
    this.pending = next;
    // A small change cue is immediate; harmony and the longer phrase stay intact.
    if (this.enabled && previous?.name === next.name && previous?.echo !== next.echo) {
      this.note('harp_high', next.root + (next.echo < previous.echo ? 0 : 12), this.ctx.currentTime + .03, 3, .16);
    }
  }
  schedule() {
    if (!this.enabled || this.ctx.state !== 'running') return;
    // Returning from a suspended/background tab must not emit a backlog of notes.
    if (this.next < this.ctx.currentTime - .2) this.next = this.ctx.currentTime + .05;
    while (this.next < this.ctx.currentTime + .25) {
      if (this.step % 8 === 0) this.direction = this.pending;
      const d = this.direction, beat = this.step % 8, t = this.next;
      // A 16-phrase arc provides arrival, development, space, and return.
      // It keeps moving across navigation instead of looping one short cue.
      const phrase = Math.floor(this.step / 8) % 16;
      const root = d.root + [0, 5, 0, 7, 0, 2, 5, 0][Math.floor(phrase / 2)];
      const space = phrase % 4 === 3 && d.tension < .6;
      const reach = Math.max(.4, 1 + Math.min(0, d.echo) / 20);
      if (beat === 0 || beat === 4) {
        this.note('cello', root - (beat === 4 ? 5 : 0), t, 4.3, .15);
        this.note('violin', root + 12 + (beat === 4 ? 7 : d.third), t + .03, 4.4, .08 + d.energy * .06);
      }
      const motif = MELODY[(d.motif + Math.floor(phrase / 4)) % 4][beat];
      const pitch = root + 12 + d.register + (motif === 4 ? d.third : motif);
      if ((!space && (beat % 2 === 0 || d.woven || d.energy > .5)) || beat === 0) this.note(pitch >= 60 ? 'harp_high' : 'harp', pitch, t, 3.8, (.10 + d.energy * .09) * reach);
      if (!space && (beat === 2 || beat === 6)) this.note('flute', root + 12 + (beat === 2 ? 7 : d.third), t, 2.2, d.bright ? .07 : .035);
      if (d.tension > .35 && beat % 4 === 0) this.note('tremolo', root + 12 + (d.tension > .7 ? 1 : 7), t, 3.8, d.tension * .075);
      this.air(t, d);
      this.step++; this.next += BEAT;
    }
  }
  note(instrument, midi, time, length, level) {
    if (!this.buffers[instrument] || !this.enabled) return;
    const ctx = this.ctx, source = ctx.createBufferSource(), envelope = ctx.createGain();
    source.buffer = this.buffers[instrument];
    source.playbackRate.value = 2 ** ((midi - FILES[instrument]) / 12);
    const duration = Math.min(length, source.buffer.duration / source.playbackRate.value);
    envelope.gain.setValueAtTime(0, time);
    envelope.gain.linearRampToValueAtTime(level, time + Math.min(.4, duration / 4));
    envelope.gain.setTargetAtTime(.001, time + duration * .6, duration * .15);
    source.connect(envelope); envelope.connect(this.master); envelope.connect(this.room);
    this.sources.add(source);
    source.onended = () => { this.sources.delete(source); source.disconnect(); envelope.disconnect(); };
    source.start(time); source.stop(time + duration);
  }
  air(time, d) {
    if (d.atmosphere === 'still') return;
    const ctx = this.ctx, source = ctx.createBufferSource(), filter = ctx.createBiquadFilter(), gain = ctx.createGain();
    if (!this.noise) {
      this.noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const data = this.noise.getChannelData(0);
      let state = 1937;
      for (let i = 0; i < data.length; i++) { state = (Math.imul(1664525, state) + 1013904223) >>> 0; data[i] = state / 2147483648 - 1; }
    }
    source.buffer = this.noise;
    filter.type = 'bandpass'; filter.frequency.value = d.atmosphere === 'rain' ? 3300 : d.atmosphere === 'electric' ? 1700 : 380;
    filter.Q.value = .5;
    gain.gain.setValueAtTime(0, time); gain.gain.linearRampToValueAtTime(.015, time + .2); gain.gain.linearRampToValueAtTime(0, time + .9);
    source.connect(filter); filter.connect(gain); gain.connect(this.master);
    this.sources.add(source);
    source.onended = () => { this.sources.delete(source); source.disconnect(); filter.disconnect(); gain.disconnect(); };
    source.start(time); source.stop(time + .95);
  }
  disable() {
    this.enabled = false; clearInterval(this.timer);
    if (!this.ctx) return;
    for (const source of this.sources) { try { source.stop(); } catch (_) { /* already ended */ } }
    this.master?.gain.setTargetAtTime(0, this.ctx.currentTime, .05);
  }
  destroy() { this.disable(); this.ctx?.close(); }
}

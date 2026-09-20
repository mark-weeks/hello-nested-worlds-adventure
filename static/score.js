// Scale is an audible identity, not a transposition of one backing track.
// The family motif connects places; each scale supplies its own musical form.
const hash = text => { let h=2166136261; for(const c of String(text)) h=Math.imul(h^c.charCodeAt(0),16777619); return h>>>0; };
const clamp = (n,a,b) => Math.max(a,Math.min(b,Number(n)||0));
export const SCORE_PROFILES = {
  Multiverse: {voice:'cello', beat:2.1, register:-12, wet:.85, cutoff:900, title:'Membrane tides'},
  Universe: {voice:'bassoon', beat:1.5, register:-5, wet:.7, cutoff:2300, title:'Vacuum chorale'},
  Galaxy: {voice:'tremolo', beat:.65, register:0, wet:.65, cutoff:6500, title:'Stellar procession'},
  'Planetary System': {voice:'marimba', beat:.48, register:0, wet:.28, cutoff:7500, title:'Orbital clockwork'},
  Planet: {voice:'horn', beat:1.2, register:0, wet:.5, cutoff:4300, title:'Horizon song'},
  Region: {voice:'flute', beat:.72, register:12, wet:.18, cutoff:6500, title:'Open-air call and answer'},
  Room: {voice:'harp', beat:1.1, register:0, wet:.75, cutoff:4300, title:'Resonant enclosure'},
  Object: {voice:'pizzicato', beat:.55, register:12, wet:.06, cutoff:8000, title:'Close material gestures'},
  Molecule: {voice:'marimba', beat:.29, register:12, wet:.12, cutoff:10000, title:'Bond hockets'},
  Atom: {voice:'glock', beat:.82, register:24, wet:.45, cutoff:12000, title:'Spectral bells'},
  SubatomicParticle: {voice:'sine', beat:.19, register:36, wet:.03, cutoff:14000, title:'Discrete sparks'},
};
export function scoreDirection(node) {
  const s=node?.senses || {}, p=node?.properties || {}, level=node?.level || 'Room';
  const profile=SCORE_PROFILES[level] || SCORE_PROFILES.Room;
  const identity=hash(node?.name || 'place');
  const memory=s.memory ? parseInt(s.memory.slice(0,4),16)||0 : identity;
  const minor=s.polarity<0 || s.tension>.6;
  let tempo=1, color=1, density=.5;
  if(level==='Multiverse') tempo=1.35-clamp(p.hum_period_years,0,1000)/1200;
  if(level==='Universe') {tempo=.8+clamp(p.vacuum_hum_hz,0,100)/150;color=.6+clamp(p.dark_matter_ratio,0,1);}
  if(level==='Galaxy') {density=clamp(p.star_density ?? 250,1,999)/999;tempo=.8+clamp(p.drift_kmps,0,1000)/1300;}
  if(level==='Planetary System') {tempo=.85+clamp(p.planet_count ?? 5,1,12)/25;density=p.asteroid_belt?.8:.3;}
  if(level==='Planet') {tempo=1.4-clamp(p.day_length_hours ?? 24,2,240)/250;color=p.biome==='forest'?.75:1;}
  if(level==='Region') {tempo=p.terrain==='waterways'?.8:p.terrain==='terraced'?1:1.15;density=clamp(p.danger_level ?? 3,1,10)/10;}
  if(level==='Room') {color=p.lighting==='bright'?1.6:p.lighting==='dim'?.7:p.lighting==='dark'?.4:1;density=p.air==='cool and mineral'?.25:.5;}
  if(level==='Object') {color=p.surface==='mirror smooth'?1.7:p.surface==='engraved'?1.25:.8;density=p.fractured?.9:.45;}
  if(level==='Molecule') {tempo=p.reactive?1.25:.8;density=clamp(p.bond_count ?? 4,1,12)/12;}
  if(level==='Atom') {color=1.8-clamp(p.resonance_nm ?? 500,180,780)/780;density=p.ionized?.85:.3;}
  if(level==='SubatomicParticle') {tempo=.75+clamp(p.coherence ?? .5,0,1);density=p.spin==='superposed'?.8:.35;}
  return {...profile, level, root:[48,50,53,55][s.family ?? 0] || 48, third:minor?3:4,
    tension:s.tension||0,energy:s.energy||0,echo:s.echo||0,woven:!!s.woven,
    motif:memory%4,variant:identity%7,atmosphere:s.atmosphere || 'still',
    bright:s.texture==='filament'||s.texture==='crystalline',material:p.material || s.texture || '',
    geometry:p.geometry || '',spin:p.spin,ceiling:clamp(p.ceiling_m ?? 12,2,40),
    beat:profile.beat/tempo,cutoff:profile.cutoff*color,density,
    revision:s.revision || hash(JSON.stringify(p)).toString(),name:node?.name};
}
export const SCORE_SAMPLES = {cello:48,violin:60,harp:48,harp_high:72,flute:60,tremolo:60,horn:48,bassoon:48,marimba:60,glock:72,pizzicato:60};
const FILES=SCORE_SAMPLES;
const MELODY=[[0,7,12,4,9,7,2,0],[0,2,7,9,12,7,4,2],[12,7,9,4,7,2,4,0],[0,4,2,7,4,12,9,7]];
// This pure score is also used by render/listening evaluations. Timing, ranges,
// articulations, silence and spatial placement are testable before audio begins.
export function scoreEvents(d,step) {
  const beat=step%16, phrase=Math.floor(step/16), events=[];
  const root=d.root+[0,5,0,7][Math.floor(phrase/2)%4];
  const contour=MELODY[(d.motif+Math.floor(phrase/4))%4];
  const interval=contour[(beat+d.variant)%8], note=interval===4?d.third:interval;
  const pan=((beat+d.variant)%5-2)*.3;
  const emit=(instrument,pitch,duration,gain,delay=0,options={})=>events.push({instrument,midi:pitch,time:delay,length:duration,level:gain,pan,wet:d.wet,cutoff:d.cutoff,...options});
  const pitch=root+d.register;
  // Space in the fourth phrase is composed, never an accidental loading gap.
  const resting=phrase%4===3 && beat>8 && d.tension<.6;
  if(resting) return events;
  switch(d.level) {
    case 'Multiverse':
      if(beat%4===0) {emit('cello',pitch+(beat%8?7:0),9,.32,0,{attack:2.0,pan:-.45});emit('sine',pitch+12,8,.05,.3,{attack:2,pan:.45});}
      if(beat===6) emit('horn',root-12+d.third,6,.08,0,{attack:1.8});
      break;
    case 'Universe':
      if(beat%4===0) {emit('bassoon',pitch+(beat%8?d.third:0),5,.27,0,{attack:.8});emit('horn',root+(beat%8?7:0),5,.12,.25,{attack:1.1,pan:-pan});}
      break;
    case 'Galaxy':
      if(beat%4===0) {emit('tremolo',root+12+(beat%8?7:d.third),3.4,.22,0,{attack:.45});emit('horn',root,2.8,.2,0,{pan:-.5,attack:.3});}
      if(beat%2===0 || d.density>.6) emit('violin',root+12+note,1.2,.13,0,{attack:.09,pan:.5});
      break;
    case 'Planetary System':
      if(beat%3===0) emit('marimba',root+note,1.4,.38,0,{attack:.005,pan:-.6});
      if(beat%4===0) emit('harp_high',root+24+(beat%8?7:0),2,.2,.06,{attack:.005,pan:.6});
      if(d.density>.6 && beat%2) emit('pizzicato',root+12, .3,.12,0,{attack:.002});
      break;
    case 'Planet':
      if([0,3,8,11].includes(beat)) emit('horn',root+[0,d.third,7,12][Math.floor(beat/3)%4],3.8,.3,0,{attack:.45,pan:-.25});
      if(beat%4===2) emit('flute',root+19+(beat%8?5:0),2.4,.18,.12,{attack:.18,pan:.5});
      break;
    case 'Region':
      if([0,2,5,8,10,13].includes(beat)) emit('flute',pitch+note,1.3,.26,0,{attack:.08,pan:.25});
      if(beat%4===3) emit('marimba',root+note,1.0,.27,.08,{attack:.005,pan:-.5});
      if(d.density>.65 && beat%4===0) emit('pizzicato',root, .5,.19,0,{attack:.003});
      break;
    case 'Room':
      if([0,5,11].includes(beat)) {
        emit('harp',root+note,3.6,.4,0,{attack:.008,pan:-.35});
        emit('harp_high',root+12+note,2.4,.16,.16+d.ceiling/100,{attack:.008,pan:.6,wet:.8});
      }
      break;
    case 'Object': {
      const voice=/metal|crystal|glass|filament|light/.test(d.material)?'glock':/wood|bone|chitin/.test(d.material)?'marimba':'pizzicato';
      if([0,1,4,7,8,12].includes(beat)) emit(voice,pitch+note,.65,.32,0,{attack:.002,pan:pan*.4});
      if(d.density>.7 && beat%4===2) emit('pizzicato',pitch+1,.15,.18,.09,{attack:.001,pan:-pan});
      break;
    }
    case 'Molecule': {
      const period=d.geometry.includes('branch')?3:d.geometry.includes('sheet')?4:5;
      if(beat%period!==period-1) emit(beat%2?'glock':'marimba',pitch+note,.45,.25,0,{attack:.002,pan:beat%2?.7:-.7});
      if(d.density>.55 && beat%period===0) emit('pizzicato',pitch+7,.2,.16,.11,{attack:.001,pan:0});
      break;
    }
    case 'Atom':
      if([0,4,9,13].includes(beat)) {emit('glock',pitch+[0,12,7,d.third][Math.floor(beat/4)%4],2.5,.26,0,{attack:.002});emit('sine',pitch+12,1.3,.065,.1,{attack:.02,pan:-pan});}
      if(d.density>.6 && beat%4===2) emit('sine',pitch+19,.16,.09,0,{attack:.003});
      break;
    default:
      if([0,1,5,8,10,14].includes((beat+d.variant)%16)) emit('sine',pitch+(d.spin==='down'?-7:note),.055,.14,0,{attack:.002,pan:beat%2?-.85:.85,wet:.03});
      if(d.density>.6 && beat%4===0) emit('glock',pitch+12,.08,.14,.045,{attack:.001,pan:-pan});
  }
  // History alters articulation and dynamics within the scale's own language.
  for(const e of events) {e.level*=clamp(1+d.energy*.35+d.echo*.018,.65,1.6);if(d.woven)e.wet=Math.min(.95,e.wet+.12);}
  return events;
}
export class NodeAmbience {
  constructor() { this.enabled = false; this.buffers = {}; this.volume = .55; this.sources = new Set(); this.voices = new Set(); }
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
        let state=27183+c*901, smooth=0;
        for(let i=0;i<data.length;i++) {
          state=(Math.imul(1664525,state)+1013904223)>>>0;
          smooth=.7*smooth+.3*(state/2147483648-1);
          data[i]=smooth*Math.pow(1-i/data.length,3)*.14;
        }
        // Early reflections establish space before a diffuse, non-tonal tail.
        for(const [j,delay] of [.031,.047,.073,.109,.163].entries())
          data[Math.floor((delay+c*.003)*ctx.sampleRate)]+=.35/(j+1);
      }
      this.room.buffer = impulse;
      const wet = ctx.createGain(); wet.gain.value = .32;
      this.room.connect(wet); wet.connect(this.master);
    }
    this.enabled = true;
    this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, .2);
    this.pending = this.direction = scoreDirection(node); this.phase = 0;
    this.step = 0; this.next = this.ctx.currentTime + .1;
    this.loading = Promise.all(Object.keys(FILES).map(async name => {
      if(this.buffers[name]) return;
      try {
        const response = await fetch(`/media/score/${name}.mp3`);
        if (!response.ok) throw new Error('sample unavailable');
        const buffer = await this.ctx.decodeAudioData(await response.arrayBuffer());
        let peak=0;for(let c=0;c<buffer.numberOfChannels;c++) for(const x of buffer.getChannelData(c)) peak=Math.max(peak,Math.abs(x));
        const scale=peak>.001?.8/peak:1;
        for(let c=0;c<buffer.numberOfChannels;c++) { const data=buffer.getChannelData(c); for(let i=0;i<data.length;i++) data[i]*=scale; }
        this.buffers[name] = buffer;
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
    if (this.enabled && previous && previous.level !== next.level) {
      // Hear the new scale on arrival, not after an old seven-second phrase.
      // Release old instruments gracefully; preserve the continuous transport.
      const t=this.ctx.currentTime;
      for(const voice of this.voices) {voice.gain.gain.cancelAndHoldAtTime(t);voice.gain.gain.setTargetAtTime(0,t,.35);}
      this.direction=next; this.phase=this.step; this.next=t+.08;
    }
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
      const d=this.direction, t=this.next;
      for(const event of scoreEvents(d,this.step-(this.phase || 0))) {
        this.note(event.instrument,event.midi,t+event.time,event.length,event.level,event);
      }
      if(['Planet','Region','Room'].includes(d.level)) this.air(t,d);
      this.step++; this.next+=d.beat;
    }
  }
  note(instrument, midi, time, length, level, options={}) {
    if ((!this.buffers[instrument] && instrument!=='sine') || !this.enabled) return;
    const ctx=this.ctx, source=instrument==='sine'?ctx.createOscillator():ctx.createBufferSource();
    let duration=length;
    if(instrument==='sine') {source.type='sine';source.frequency.value=440*2**((midi-69)/12);}
    else {source.buffer=this.buffers[instrument];source.playbackRate.value=2**((midi-FILES[instrument])/12);duration=Math.min(length,source.buffer.duration/source.playbackRate.value);}
    const envelope=ctx.createGain(),filter=ctx.createBiquadFilter(),pan=ctx.createStereoPanner(),send=ctx.createGain();
    filter.type='lowpass';filter.frequency.value=Math.min(ctx.sampleRate*.45,options.cutoff || 9000);filter.Q.value=.45;
    pan.pan.value=options.pan || 0;send.gain.value=options.wet ?? .3;
    const attack=Math.min(options.attack ?? .02,duration*.3);
    envelope.gain.setValueAtTime(0,time);envelope.gain.linearRampToValueAtTime(level,time+attack);
    envelope.gain.setTargetAtTime(.0001,time+duration*.55,duration*.13);
    envelope.gain.linearRampToValueAtTime(0,time+duration);
    source.connect(filter);filter.connect(envelope);envelope.connect(pan);pan.connect(this.master);pan.connect(send);send.connect(this.room);
    const voice={source,gain:envelope};this.voices.add(voice);this.sources.add(source);
    source.onended=()=>{this.voices.delete(voice);this.sources.delete(source);for(const node of [source,filter,envelope,pan,send])node.disconnect();};
    source.start(time);source.stop(time+duration);
  }
  air(time,d) {
    if(d.atmosphere==='still') return;
    const ctx=this.ctx,source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();
    if(!this.noise) {
      this.noise=ctx.createBuffer(1,ctx.sampleRate*2,ctx.sampleRate);
      const data=this.noise.getChannelData(0);let state=1937;
      for(let i=0;i<data.length;i++){state=(Math.imul(1664525,state)+1013904223)>>>0;data[i]=state/2147483648-1;}
    }
    source.buffer=this.noise;filter.type='bandpass';filter.frequency.value=d.atmosphere==='rain'?3300:d.atmosphere==='electric'?1700:380;filter.Q.value=.5;
    const duration=Math.min(d.beat,1.9);
    gain.gain.setValueAtTime(0,time);gain.gain.linearRampToValueAtTime(.012,time+duration*.2);gain.gain.linearRampToValueAtTime(0,time+duration);
    source.connect(filter);filter.connect(gain);gain.connect(this.master);this.sources.add(source);
    source.onended=()=>{this.sources.delete(source);source.disconnect();filter.disconnect();gain.disconnect();};
    source.start(time);source.stop(time+duration);
  }

  disable() {
    this.enabled = false; clearInterval(this.timer);
    if (!this.ctx) return;
    for (const source of this.sources) { try { source.stop(); } catch (_) { /* already ended */ } }
    this.master?.gain.setTargetAtTime(0, this.ctx.currentTime, .05);
  }
  destroy() { this.disable(); this.ctx?.close(); }
}

import {describe,it,expect} from 'vitest';
import '../../../static/clientlogic.js'; // score.js hashes through the shared EnfoldedClient helper
import {NodeAmbience,scoreDirection,scoreEvents,SCORE_PROFILES} from '../../../static/score.js';
const place=(name,senses)=>({name,senses});
describe('continuous orchestration',()=>{
  it('shares a tonal family while material, polarity, memory and danger direct the music',()=>{
    const a=scoreDirection(place('Gallery',{family:2,texture:'mineral',polarity:1,tension:.2}));
    const b=scoreDirection(place('Instrument',{family:2,texture:'filament',polarity:-1,tension:.8,memory:'00ff',woven:true}));
    expect(a.root).toBe(b.root);expect(a.third).toBe(4);expect(b.third).toBe(3);
    expect(b.bright).toBe(true);expect(b.woven).toBe(true);expect(b.motif).toBe(3);
  });
  it('updates a pending direction without destroying voices or resetting the musical clock',()=>{
    const score=new NodeAmbience(); score.step=19;score.next=14;score.enabled=true;score.ctx={currentTime:4};score.note=()=>{};
    const voices=score.sources;
    score.setNode(382,place('Instrument',{revision:'a',family:1}));
    score.setNode(382,place('Instrument',{revision:'b',family:1,echo:3}));
    expect(score.step).toBe(19);expect(score.next).toBe(14);expect(score.sources).toBe(voices);expect(score.pending.echo).toBe(3);
  });
  it('adopts the pending harmony on a phrase boundary and skips suspended backlog',()=>{
    const score=new NodeAmbience();score.enabled=true;score.ctx={currentTime:100,state:'running'};score.step=8;score.next=1;
    score.pending=scoreDirection(place('Chain',{family:3,polarity:-1}));score.direction=scoreDirection(place('Orchard',{family:0}));
    const notes=[];score.note=(...args)=>notes.push(args);score.air=()=>{};
    score.schedule();expect(score.step).toBe(9);expect(score.direction).toBe(score.pending);expect(notes.length).toBeLessThan(6);
    expect(notes.every(n=>n[2]>=100)).toBe(true);
  });
});


describe('audible scale and node identity',()=>{
  it('writes eleven distinct musical forms, rather than transposing one accompaniment',()=>{
    const signatures=Object.keys(SCORE_PROFILES).map(level=>{
      const d=scoreDirection({name:'Same identity',level,senses:{family:1}});
      return JSON.stringify(Array.from({length:16},(_,step)=>scoreEvents(d,step).map(e=>
        [e.instrument,step,e.length,e.pan,e.wet,e.attack])));
    });
    expect(new Set(signatures).size).toBe(11);
    const identities=['Room','Object','Molecule','Atom'].map(level=>{
      const d=scoreDirection({name:'same',level});
      return Array.from({length:16},(_,i)=>scoreEvents(d,i)).flat();
    });
    expect(identities[0].some(e=>e.instrument==='harp')).toBe(true);
    expect(identities[1].every(e=>e.instrument==='pizzicato')).toBe(true);
    expect(identities[2].some(e=>e.instrument==='marimba')).toBe(true);
    expect(identities[3].some(e=>e.instrument==='sine')).toBe(true);
  });
  it('changes actual notes, timing or articulation when material properties change',()=>{
    for(const [level,a,b] of [
      ['Object',{material:'wood'},{material:'metal'}],
      ['Region',{terrain:'overgrown',danger_level:8},{terrain:'terraced',danger_level:3}],
      ['Molecule',{geometry:'helical',bond_count:3},{geometry:'branched chain',bond_count:9}],
      ['Atom',{ionized:false,resonance_nm:780},{ionized:true,resonance_nm:180}],
      ['Room',{lighting:'bright',ceiling_m:4},{lighting:'dim',ceiling_m:38}],
    ]) {
      const music=properties=>{
        const d=scoreDirection({name:'Same node',level,properties});
        return {beat:d.beat,events:Array.from({length:16},(_,i)=>scoreEvents(d,i))};
      };
      expect(music(a)).not.toEqual(music(b));
    }
  });
  it('changes scales promptly with a fade, retaining the transport counter',()=>{
    const score=new NodeAmbience();score.enabled=true;score.step=19;score.next=14;score.ctx={currentTime:4};
    score.pending=score.direction=scoreDirection({name:'Room',level:'Room'});
    const calls=[];score.voices.add({gain:{gain:{cancelAndHoldAtTime:t=>calls.push(t),setTargetAtTime:(...v)=>calls.push(v)}}});
    score.setNode(382,{name:'Atom',level:'Atom'});
    expect(score.direction.level).toBe('Atom');expect(score.step).toBe(19);expect(score.next).toBe(4.08);expect(calls).toHaveLength(2);
  });
  it('fades voices on a scale change where cancelAndHoldAtTime is missing, as in Firefox',()=>{
    const score=new NodeAmbience();score.enabled=true;score.step=19;score.next=14;score.ctx={currentTime:4};
    score.pending=score.direction=scoreDirection({name:'Room',level:'Room'});
    const calls=[];
    score.voices.add({gain:{gain:{value:.4,cancelScheduledValues:t=>calls.push(['cancel',t]),
      setValueAtTime:(v,t)=>calls.push(['hold',v,t]),setTargetAtTime:(...v)=>calls.push(['target',...v])}}});
    expect(()=>score.setNode(382,{name:'Atom',level:'Atom'})).not.toThrow();
    expect(calls).toEqual([['cancel',4],['hold',.4,4],['target',0,4,.35]]);
    expect(score.direction.level).toBe('Atom');expect(score.next).toBe(4.08);
  });
});

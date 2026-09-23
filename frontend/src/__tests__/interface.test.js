import {describe,it,expect} from 'vitest';
import '../../../static/interface.js';
import samples from '../../e2e/fixtures/visual-language.json';
const {resolve,contrast,atmosphere}=globalThis.EnfoldedInterface;
describe('semantic interface foundations',()=>{
  it('derives different expressions for two objects and preserves identity independence',()=>{
    const a=samples[2].before,b=samples[3].before;
    expect(a.level).toBe(b.level);
    expect(resolve(a)).not.toEqual(resolve(b));
    expect(resolve({...a,name:'A completely different identity-999'})).toEqual(resolve(a));
  });
  it.each(samples)('$before.level: $operation responds only to observed substance',sample=>{
    expect(resolve(sample.before)).not.toEqual(resolve(sample.after));
    expect(resolve({...sample.before,pending_actions:[{verb:sample.operation}]})).toEqual(resolve(sample.before));
    expect(resolve({...sample.before,properties:{...sample.before.properties,restored:true,disrupted:true}})).toEqual(resolve(sample.before));
  });
  it('gives current weather priority over a retained atmospheric aspect',()=>{
    expect(atmosphere(samples[0].before)).toBe('heat');
    expect(atmosphere(samples[0].after)).toBe('mist');
  });
  it('keeps readable text, focus and boundaries even with extreme input palettes',()=>{
    const nodes=samples.flatMap(s=>[s.before,s.after]);
    for(const shadow of ['#ffffff','#ff0000','#000000','invalid']) for(const light of ['#ffffff','#000000','#ff0000','#00ff00','#0000ff'])nodes.push({senses:{shadow,light,lighting:'bright',energy:1,echo:12}});
    for(const node of nodes){
      const t=resolve(node);
      for(const bg of ['--canvas','--surface','--raised']) {
        for(const fg of ['--text','--muted','--link','--attention'])expect(contrast(t[fg],t[bg])).toBeGreaterThanOrEqual(4.5);
        expect(contrast(t['--accent'],t[bg])).toBeGreaterThanOrEqual(3);
        expect(contrast(t['--line'],t[bg])).toBeGreaterThanOrEqual(3);
      }
      expect(contrast(t['--on-accent'],t['--accent'])).toBeGreaterThanOrEqual(4.5);
    }
  });
});

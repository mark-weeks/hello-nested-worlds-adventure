// Shared, read-only interpretation. Never hashes identity into a permanent color.
(() => {
  const clamp = (n, lo=0, hi=1) => Math.min(hi, Math.max(lo, Number(n) || 0));
  const rgb = (hex, fallback='#18232d') => /^#[\da-f]{6}$/i.test(hex || '')
    ? hex.slice(1).match(/../g).map(n => parseInt(n, 16)) : rgb(fallback);
  const hex = c => '#' + c.map(n => Math.round(clamp(n,0,255)).toString(16).padStart(2,'0')).join('');
  const mix = (a,b,t) => a.map((v,i)=>v*(1-t)+b[i]*t);
  const luminance = c => c.map(v => { v/=255; return v<=.04045?v/12.92:((v+.055)/1.055)**2.4; }).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
  const contrast = (a,b) => { const x=luminance(rgb(a)), y=luminance(rgb(b)); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
  function readable(candidate, background, minimum) {
    let color=candidate;
    for(let i=0; i<30 && contrast(hex(color),hex(background))<minimum;i++) color=mix(color,[255,255,255],.12);
    return hex(color);
  }
  function atmosphere(node={}) {
    const p=node.properties || {}, current=String(p.weather || p.air || '').toLowerCase();
    if(/fog|mist/.test(current)) return 'mist';
    if(/rain|drizzle/.test(current)) return 'rain';
    if(/snow|frost|cold|cool/.test(current)) return 'cold';
    if(/storm|lightning|static/.test(current)) return 'electric';
    if(/heat|hot|warm/.test(current)) return 'heat';
    if(/smoke|dust|ash|pollen/.test(current)) return 'dust';
    return node.senses?.atmosphere || 'still';
  }
  function resolve(node={}) {
    const s=node.senses || {}, p=node.properties || {};
    const air={mist:'#a7cfce',cold:'#a2d3e9',rain:'#9acddd',dust:'#ddbb85',electric:'#b5b1ed',heat:'#ebb28c',still:s.light || '#c5d0d5'};
    const light=rgb(s.light,'#c5d0d5'), shadow=rgb(s.shadow);
    let pigment=mix(light,rgb(air[atmosphere(node)] || air.still),.28);
    const terrain={waterways:'#8bbbc7',overgrown:'#abc399',terraced:'#d1b68d'}[p.terrain];
    if(terrain) pigment=mix(pigment,rgb(terrain),.32);
    if(/branched/.test(p.geometry || '')) pigment=mix(pigment,rgb('#a5d7c0'),.25);
    // Polarity is a physical warm/cool shift, never success/failure or morality.
    if(s.echo || s.energy) pigment=mix(pigment,rgb(s.polarity<0?'#90c5ed':'#e8bd8b'),clamp(Math.abs(s.echo)/24+clamp(s.energy)*.2,0,.4));
    const lit = /bright|luminous|sunlit/i.test(s.lighting || p.lighting || '');
    let canvas=mix(shadow,[8,12,16],.35);
    // Even unusual/provider colors cannot erase the reading surface.
    while(luminance(canvas)>.035) canvas=mix(canvas,[0,0,0],.15);
    const surface=mix(canvas,pigment,lit?.12:.06), raised=mix(surface,pigment,.06);
    const accent=readable(pigment,raised,4.5);
    const line=readable(mix(surface,pigment,.56),raised,3);
    const angular=/crystalline|metallic|mineral/.test(s.texture || '') || /sheet/.test(s.geometry || '');
    return {
      '--canvas':hex(canvas),'--surface':hex(surface),'--raised':hex(raised),
      '--text':readable(mix(pigment,[255,255,255],.9),raised,7),
      '--muted':readable(mix(pigment,[218,223,225],.65),raised,4.5),
      '--accent':accent,'--link':readable(mix(pigment,[220,233,255],.35),raised,4.5),
      '--attention':readable(mix(pigment,rgb('#f2cf9c'),.45),raised,4.5),
      '--line':line,'--on-accent':hex(canvas),'--contour':angular?'4px':'12px',
      '--trace-style':s.woven?'double':p.fractured || s.scar?'dashed':'solid',
      '--trace-width':'4px',
      '--grain':p.surface==='engraved' || s.memory ? `repeating-linear-gradient(115deg,transparent 0 12px,${hex(mix(surface,pigment,.04))} 12px 13px)` : 'none',
      '--world-light':hex(pigment),'--world-shadow':hex(shadow),
    };
  }
  function apply(element,node) { Object.entries(resolve(node)).forEach(([k,v])=>element.style.setProperty(k,v)); }
  function cue(node={}) {
    const s=node.senses || {}, p=node.properties || {};
    return [s.material, `${atmosphere(node)} atmosphere`, p.surface,
      p.fractured?'open fracture':null,s.woven?'woven resonance':null,s.memory?'retained trace':null].filter(Boolean).join(' · ');
  }
  globalThis.EnfoldedInterface={resolve,apply,cue,contrast,atmosphere};
})();

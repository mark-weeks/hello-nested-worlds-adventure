import './interface.js';
// Shared scene renderer: property-driven weather and material, with persistent
// structures and remembered motifs. Media is never authoritative world state.
// Motion runs on a frame counter, never the wall clock: the same served node
// draws the same frame N everywhere, so screenshots follow the served state.
const FRAMES_PER_SECOND = 60;
export function startSensory(canvas, node, {transients = () => [], imageUrl} = {}) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return () => {};
  const tokens=globalThis.EnfoldedInterface.resolve(node);
  const s = {...node.senses, atmosphere:globalThis.EnfoldedInterface.atmosphere(node), light:tokens['--world-light'], shadow:tokens['--world-shadow']}, motion = matchMedia('(prefers-reduced-motion: reduce)');
  let stopped = false, raf, image, loaded = false, frame = 0;
  const seen = new WeakMap();  // transient -> the frame it first appeared on
  const url = imageUrl || s.plate;
  if (url) {
    image = new Image(); image.onload = () => { loaded = true; if (!stopped) draw(); };
    image.src = url;
  }
  function resize() {
    const box = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.max(1, Math.round(box.width * dpr));
    canvas.height = Math.max(1, Math.round(box.height * dpr));
    draw();
  }
  function draw() {
    if (stopped) return;
    const w = canvas.width, h = canvas.height, t = motion.matches ? 0 : frame / FRAMES_PER_SECOND;
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    const bg = ctx.createLinearGradient(0, 0, w, h); bg.addColorStop(0, s.shadow || '#091a20'); bg.addColorStop(1, '#03080c');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h);
    if (loaded) {
      const scale = Math.max(w / image.width, h / image.height) * 1.015;
      const dx = Math.sin(t / 19) * w * .004;
      ctx.drawImage(image, (w - image.width * scale) / 2 + dx, (h - image.height * scale) / 2, image.width * scale, image.height * scale);
      ctx.fillStyle = s.polarity < 0 ? 'rgba(4,20,39,.30)' : `rgba(30,10,0,${Math.min(.22, Math.max(0, s.echo || 0) / 50)})`;
      ctx.fillRect(0, 0, w, h);
      if(s.lighting==='bright') { ctx.fillStyle=s.light+'24';ctx.fillRect(0,0,w,h); }
      if(s.lighting==='dim') { ctx.fillStyle='#03080c60';ctx.fillRect(0,0,w,h); }
    } else {
      // Stratified material fields, not a generic planetary sketch. Geometry and
      // material choose the silhouette; stable phase gives each depth continuity.
      ctx.strokeStyle = s.light || '#beccbe';
      const helix = s.texture === 'helical' || s.texture === 'filament';
      for (let band = 0; band < 36; band++) {
        ctx.globalAlpha = .04 + band / 260; ctx.lineWidth = 1 + band / 20;
        ctx.beginPath();
        for (let x = 0; x <= w; x += 8) {
          const bend = helix ? Math.sin(x / w * 8 + band * .32) * h * .23 : Math.sin(x / w * 4 + band * .19) * h * .13;
          const y = h * .15 + band * h / 46 + bend;
          x ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.stroke();
      }
    }
    ctx.globalCompositeOperation = 'screen';
    const glow = ctx.createRadialGradient(w * .5, h * .45, 0, w * .5, h * .45, w * .55);
    glow.addColorStop(0, s.polarity < 0 ? '#153e6640' : '#dbb77325'); glow.addColorStop(1, '#00000000');
    ctx.globalAlpha = Math.min(1, .3 + (s.energy || 0)); ctx.fillStyle = glow; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = s.light || '#dfc292'; ctx.fillStyle = s.light || '#dfc292';
    const count = s.atmosphere === 'still' ? 15 : 64;
    for (let i = 0; i < count; i++) {
      const depth = .2 + (i % 7) / 9;
      const x = ((i * .6180339 + Math.sin(t * .06 + i) * .02) % 1) * w;
      const y = ((i * .381966 + t * (s.atmosphere === 'rain' ? .08 : .006) * depth) % 1) * h;
      ctx.globalAlpha = .07 + depth * .17;
      ctx.beginPath();
      if (s.atmosphere === 'rain') { ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 12 * depth); ctx.stroke(); }
      else { ctx.arc(x, y, 1 + depth * 2, 0, Math.PI * 2); ctx.fill(); }
    }
    if (s.woven) {
      ctx.save(); ctx.translate(w * .5, h * .52); ctx.rotate(t * .012 * (s.polarity || 1));
      for (let i = 0; i < 3; i++) {
        ctx.rotate(Math.PI / 3); ctx.globalAlpha = .3 + (s.energy || 0) * .4;
        ctx.lineWidth = 1.3; ctx.beginPath(); ctx.ellipse(0, 0, w * .16, h * .11, 0, 0, Math.PI * 2); ctx.stroke();
      }
      ctx.restore();
    }
    if (s.memory) {
      const motif = parseInt(s.memory.slice(0, 4), 16) || 1;
      ctx.globalAlpha = .36; ctx.lineWidth = 1.1; ctx.beginPath();
      for (let i = 0; i <= 120; i++) {
        const x = w * (.12 + i / 120 * .76), y = h * .72 + Math.sin(i / 9 + motif % 6) * h * .018 + Math.sin(i / 4) * h * .008;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      } ctx.stroke();
    }
    for (let i = 0; i < (s.scar || 0); i++) {
      ctx.globalAlpha = .25; ctx.beginPath(); ctx.moveTo(w * (.3 + i * .041), h * .28); ctx.lineTo(w * (.34 + i * .04), h * .62); ctx.stroke();
    }
    const waves = motion.matches ? [] : [...transients()];
    if (s.echo && !motion.matches) waves.push({phase: (t % 6) / 6, strength: Math.abs(s.echo) / 12});
    for (const event of waves) {
      if (event.phase == null && !seen.has(event)) seen.set(event, frame);
      const p = event.phase ?? (frame - seen.get(event)) / ((event.duration || 1500) / 1000 * FRAMES_PER_SECOND);
      if (p < 0 || p > 1) continue;
      ctx.globalAlpha = (1 - p) * .3 * (event.strength ?? 1); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(w * .5, h * .52, w * (.03 + p * .45), h * (.02 + p * .3), 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  }
  function loop() {
    if (!document.hidden) { frame++; draw(); }
    if (!motion.matches) raf = requestAnimationFrame(loop);
  }
  function motionChanged() { cancelAnimationFrame(raf); draw(); if (!motion.matches) raf = requestAnimationFrame(loop); }
  motion.addEventListener('change', motionChanged);
  const observer = new ResizeObserver(resize); observer.observe(canvas);
  resize(); if (!motion.matches) raf = requestAnimationFrame(loop);
  return () => { stopped = true; cancelAnimationFrame(raf); observer.disconnect(); motion.removeEventListener('change', motionChanged); if (image) image.onload = null; };
}

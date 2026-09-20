// Developer listening artifact; no game writes. Start a local preview first.
// node scripts/render_score_audition.mjs http://127.0.0.1:8201 /tmp/enfolded-audition
import {chromium} from '../frontend/node_modules/playwright-core/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const base=process.argv[2] || 'http://127.0.0.1:8201';
const out=path.resolve(process.argv[3] || '/tmp/enfolded-audition');
await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const metrics=[];
try {
  const page=await browser.newPage();await page.goto(base+'/guide');
  const levels=await page.evaluate(async()=>{
    // The guide has no game scripts; load the score's shared identity helper
    // explicitly so an audition does not need to join or mutate the world.
    await import('/clientlogic.js');
    return Object.keys((await import('/score.js')).SCORE_PROFILES);
  });
  for(const level of levels) {
    const result=await page.evaluate(async level=>{
      const {NodeAmbience,scoreDirection}=await import('/score.js');
      const rate=22050,seconds=16,offline=new OfflineAudioContext(2,rate*seconds,rate);let time=0;
      const context=new Proxy(offline,{get(target,key){
        if(key==='currentTime')return time;if(key==='state')return 'running';if(key==='resume')return ()=>Promise.resolve();
        const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
      }});
      const properties={material:'woven light',geometry:'helical',bond_count:3,reactive:true,
        lighting:'flickering',ceiling_m:38.4,danger_level:7,terrain:'overgrown',condition:'damaged',
        star_density:280,drift_kmps:320,planet_count:5,asteroid_belt:true,day_length_hours:24,
        ionized:false,resonance_nm:500,spin:'superposed',coherence:.6};
      const node={name:'Audition place',level,properties,senses:{family:1,tension:.4,energy:.2,atmosphere:'still'}};
      const score=new NodeAmbience();score.ctx=context;score.buffers=globalThis.auditionBuffers || {};
      score.enable(382,node);clearInterval(score.timer);await score.loading;globalThis.auditionBuffers=score.buffers;
      for(time=0;time<seconds-2;time+=.05)score.schedule();
      const rendered=await offline.startRendering(),left=rendered.getChannelData(0),right=rendered.getChannelData(1);
      const wav=new ArrayBuffer(44+left.length*4),view=new DataView(wav);
      const word=(offset,text)=>{for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i));};
      word(0,'RIFF');view.setUint32(4,wav.byteLength-8,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);
      view.setUint16(20,1,true);view.setUint16(22,2,true);view.setUint32(24,rate,true);view.setUint32(28,rate*4,true);
      view.setUint16(32,4,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,left.length*4,true);
      let peak=0,sum=0,crossings=0,quiet=0;
      for(let i=0;i<left.length;i++) {
        const x=left[i],y=right[i];peak=Math.max(peak,Math.abs(x),Math.abs(y));sum+=x*x+y*y;
        if(i && (x>=0)!==(left[i-1]>=0))crossings++;if(Math.abs(x)<.001 && Math.abs(y)<.001)quiet++;
        view.setInt16(44+i*4,Math.round(Math.max(-1,Math.min(1,x))*32767),true);view.setInt16(46+i*4,Math.round(Math.max(-1,Math.min(1,y))*32767),true);
      }
      let binary='';const bytes=new Uint8Array(wav);for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      return {audio:btoa(binary),metrics:{level,title:scoreDirection(node).title,peak,rms:Math.sqrt(sum/(left.length*2)),crossingsPerSecond:crossings/seconds,quietFraction:quiet/left.length}};
    },level);
    const file=level.replaceAll(' ','-').toLowerCase()+'.wav';await writeFile(path.join(out,file),Buffer.from(result.audio,'base64'));
    metrics.push({...result.metrics,file});
  }
  await writeFile(path.join(out,'metrics.json'),JSON.stringify(metrics,null,2)+'\n');
  const order=[6,2,9,4,8,0,7,10,3,5,1];
  await writeFile(path.join(out,'index.html'),`<!doctype html><meta charset="utf-8"><title>Enfolded · Scale listening</title><style>body{background:#10201e;color:#eee0c7;font:17px system-ui;max-width:760px;margin:40px auto;padding:20px}article{padding:20px 0;border-top:1px solid #536b61}audio{display:block;width:100%;margin:12px 0}summary{cursor:pointer;color:#adc9bb}</style><h1>Hear the scales</h1><p>Eleven sixteen-second excerpts. The same family, identity and recording level are used throughout. Listen before revealing each scale. Which can you recognize, and which still blur together?</p>${order.map((i,n)=>`<article><h2>Track ${String.fromCharCode(65+n)}</h2><audio controls preload="none" src="${metrics[i].file}"></audio><details><summary>Reveal the scale</summary><p>${metrics[i].level} · ${metrics[i].title}</p></details></article>`).join('')}`);
  console.log(JSON.stringify(metrics,null,2));
} finally {await browser.close();}

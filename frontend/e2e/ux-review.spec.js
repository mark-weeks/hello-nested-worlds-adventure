import {test,expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {serveUX,enterUX} from './ux-fixture.js';
import {disclose} from './disclosures.js';
const region='Emberlit Orchard Terraces-111111';
const act=page=>page.locator('enfolded-interventions');
const pace='The world keeps its own pace. Rest a moment, then return.';
async function capture(page,name,fullPage=true){const dir=path.join(tmpdir(),'enfolded-ux-review-evidence');await mkdir(dir,{recursive:true});await page.screenshot({path:path.join(dir,`${process.env.UX_REVIEW_PHASE || 'fixed'}-${name}.jpg`),type:'jpeg',quality:82,fullPage});}
async function start(page,route){const server=await serveUX();await page.setViewportSize({width:1440,height:900});await enterUX(page,server,route,region);await expect(page.locator('#node-name')).toHaveText('Emberlit Orchard Terraces');return server;}
async function ratio(locator){return locator.evaluate(el=>{const s=getComputedStyle(el),hex=v=>'#'+v.match(/[\d.]+/g).slice(0,3).map(x=>Math.round(Number(x)).toString(16).padStart(2,'0')).join('');return EnfoldedInterface.contrast(hex(s.color),hex(s.backgroundColor));});}

for(const route of ['/app','/']){
 const client=route==='/app'?'scene':'map';
 test(`${client} puzzle preserves an authored HTTP refusal and retries`,async({page})=>{
  const server=await start(page,route);try{
   await page.route('**/puzzle?*',r=>r.fulfill({status:429,json:{error:pace}}));
   await page.getByRole('button',{name:'Puzzle',exact:true}).click();
   await expect(page.getByText(pace,{exact:true}).first()).toBeVisible();
   await expect(page.getByRole('button',{name:'Retry question'})).toBeVisible();
   await page.unroute('**/puzzle?*');await page.getByRole('button',{name:'Retry question'}).click();
   await expect(page.getByRole('button',{name:'Submit',exact:true})).toBeVisible();
  }finally{await server.close();}
 });
 test(`${client} passage conditions update without depending on color`,async({page})=>{
  const server=await start(page,route);try{
   const nav=page.locator('enfolded-navigation');
   await nav.evaluate(el=>{const child={...el.ctx.node.children[0],properties:{...el.ctx.node.children[0].properties,danger_level:8,condition:'corrupted',disturbed:true,stabilized:true},ripple_score:.4};el.context={...el.ctx,node:{...el.ctx.node,children:[child]}};});
   for(const label of ['danger 8','corrupted','disturbed','stabilized','≈ pressure'])await expect(nav.getByText(label,{exact:false})).toBeVisible();
   await nav.evaluate(el=>{const child={...el.ctx.node.children[0],properties:{...el.ctx.node.children[0].properties,danger_level:9}};el.context={...el.ctx,node:{...el.ctx.node,children:[child]}};});
   await expect(nav.getByText('danger 9',{exact:false})).toBeVisible();
  }finally{await server.close();}
 });
 test(`${client} tall passage lists remain reachable before the end of a long sidebar`,async({page})=>{
  const server=await start(page,route);try{
   await page.setViewportSize({width:1440,height:600});
   await page.evaluate(()=>{document.documentElement.style.fontSize='32px';document.querySelector('.sidebar,.world-panel').style.minHeight='5000px';});
   const last=page.locator('enfolded-navigation .children button').last();
   const before=await last.boundingBox();await page.evaluate(y=>window.scrollTo(0,y),before.y-100);
   await capture(page,client+'-tall-passages',false);await expect(last).toBeInViewport({ratio:1});
   expect(await page.evaluate(()=>scrollY<document.documentElement.scrollHeight-innerHeight-500)).toBe(true);
  }finally{await server.close();}
 });
 test(`${client} observed-history travel retains keyboard location focus`,async({page})=>{
  const server=await start(page,route);try{
   await page.getByRole('button',{name:'Act',exact:true}).click();
   await act(page).getByRole('button',{name:'Channel',exact:true}).click();
   await expect(act(page).getByRole('status')).toContainText('attempts');
   await page.locator('enfolded-navigation').getByRole('button',{name:/Room ↘ Broken Ember Gallery/}).click();
   await expect(page.locator('#node-name')).toHaveText('Broken Ember Gallery');
   await disclose(page,'Actions still echoing');
   await act(page).getByRole('button',{name:'Observed · Emberlit Orchard Terraces',exact:true}).focus();await page.keyboard.press('Enter');
   await expect(page.locator('#node-name')).toHaveText('Emberlit Orchard Terraces');
   await expect(page.locator('#node-name')).toBeFocused();
  }finally{await server.close();}
 });
}

test('Wayback play and listen labels have readable rendered contrast',async({page})=>{
 const server=await start(page,'/app');try{
  await disclose(page,'History & journal');await page.getByRole('button',{name:'Replay History',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:/Replay History/});
  const play=dialog.getByRole('button',{name:'play evolution',exact:true}),listen=dialog.getByRole('button',{name:'listen to this moment',exact:true});
  await expect(play).toBeVisible();await capture(page,'wayback');
  expect(await ratio(play)).toBeGreaterThanOrEqual(4.5);expect(await ratio(listen)).toBeGreaterThanOrEqual(4.5);
 }finally{await server.close();}
});

test('map puzzle tab preserves a partial answer and reloads recorded completion',async({page})=>{
 const server=await start(page,'/');let reads=0,solved=false;
 try{
  await page.route('**/puzzle?*',r=>{reads++;return r.fulfill({json:{found:true,name:'Remembered question',kind:'RIDDLE',prompt:'A remembered question.',max_attempts:3,attempt:solved?2:1,solved,solver:solved?'Traveler':null,epoch:0}});});
  await page.route('**/puzzle/attempt*',r=>{solved=true;return r.fulfill({json:{correct:true,attempt:2,result:'SOLVED'}});});
  await page.getByRole('button',{name:'Puzzle',exact:true}).click();
  await expect(page.locator('#attempt-info')).toHaveText('2 attempts remaining');
  await page.locator('#puzzle-answer').fill('my half-written answer');
  await page.getByRole('button',{name:'Act',exact:true}).click();await page.getByRole('button',{name:'Puzzle',exact:true}).click();
  await expect(page.locator('#puzzle-answer')).toHaveValue('my half-written answer');expect(reads).toBe(1);
  await page.getByRole('button',{name:'Submit',exact:true}).click();
  await expect(page.locator('#puzzle-result')).toHaveText('Correct.');
  await page.reload();await page.getByRole('button',{name:'Puzzle',exact:true}).click();
  await expect(page.locator('#puzzle-result')).toContainText('Solved');await expect(page.locator('#puzzle-submit')).toBeDisabled();
  await expect(page.locator('#puzzle-answer')).toBeDisabled();
 }finally{await server.close();}
});

test('map presence has non-color distinctions and an observation meter has geometry',async({page})=>{
 const server=await start(page,'/');try{
  await expect.poll(()=>page.evaluate(()=>ws?.readyState)).toBe(1);
  await page.evaluate(()=>{handleWsMsg({type:'player_join',session_id:'other',name:'Fellow traveler'});handleWsMsg({type:'player_move',session_id:'other',node:selected.name});handleWsMsg({type:'agent_enter',name:'Tessera',persona:'curious'});handleWsMsg({type:'agent_move',name:'Tessera',node:selected.name});});
  await disclose(page,'Travelers & chat');await page.locator('#btn-observe').click();
  // The same public row payload the existing observer SSE renderer consumes.
  await page.evaluate(()=>appendObserveRow({kind:'ripple',node:selected.name,level:selected.level,strength:.6}));
  const fill=page.locator('.bar-fill').first();await expect(fill).toBeVisible();
  const box=await fill.boundingBox();expect(box.height).toBeGreaterThanOrEqual(4);expect(box.width).toBeGreaterThan(0);
  const styles=await page.locator('.presence-ring').evaluateAll(els=>els.map(el=>el.getAttribute('stroke-dasharray')));
  expect(new Set(styles).size).toBe(2);
  await page.evaluate(()=>selectNode({...selected},{refresh:true}));
  for(const fill of await page.locator('.presence-ring').evaluateAll(els=>els.map(el=>el.getAttribute('fill'))))expect(fill).toBe('none');
  await capture(page,'presence');
 }finally{await server.close();}
});

test('map resize preserves an in-view pan and zoom, and identifies the selected marker',async({page})=>{
 const server=await start(page,'/');try{
  await page.evaluate(()=>{const d=hierLayout.descendants().find(d=>d.data.name===selected.name);svg.interrupt().call(zoom.transform,d3.zoomIdentity.translate(300-d.y*.6,220-d.x*.6).scale(.6));});
  const prior=await page.locator('#graph > svg > g').getAttribute('transform');
  await page.setViewportSize({width:1480,height:940});
  await expect(page.locator('#graph > svg > g')).toHaveAttribute('transform',prior);
  await expect(page.locator('.node.selected text')).toHaveText('You are here');
  await expect(page.locator('.node.selected text')).toBeVisible();
 }finally{await server.close();}
});

test('map transport failures use authored status copy',async({page})=>{
 const server=await start(page,'/');try{
  await page.route('**/world?*',r=>r.abort('failed'));await page.evaluate(()=>loadWorld());
  await expect(page.locator('#status')).toHaveText('The world could not be reached. Try opening the view again.');
  await page.getByRole('button',{name:'Puzzle',exact:true}).click();await expect(page.locator('#puzzle-answer')).toBeVisible();
  await page.route('**/puzzle/attempt*',r=>r.abort('failed'));await page.locator('#puzzle-answer').fill('a guess');await page.locator('#puzzle-submit').click();
  await expect(page.locator('#puzzle-result')).toHaveText('Your answer could not be heard. Try again.');
 }finally{await server.close();}
});

// A probe on the exported resolver must see every resolution on the styling path,
// including the one apply() performs for a caller that did not resolve already.
test('applying interface tokens resolves through the observable reference',async({page})=>{
 const server=await start(page,'/');try{
  const counts=await page.evaluate(()=>{
   const original=EnfoldedInterface.resolve;let calls=0;
   EnfoldedInterface.resolve=node=>{calls++;return original(node);};
   const element=document.createElement('div');
   try{
    EnfoldedInterface.apply(element,selected);const resolving=calls;
    EnfoldedInterface.apply(element,selected,original(selected));
    return {resolving,reusing:calls-resolving,accent:element.style.getPropertyValue('--accent')};
   }finally{EnfoldedInterface.resolve=original;}
  });
  expect(counts.resolving).toBe(1);   // apply() without tokens is visible to the probe
  expect(counts.reusing).toBe(0);     // apply() with tokens does not resolve again
  expect(counts.accent).not.toBe(''); // and either way it still writes the tokens
 }finally{await server.close();}
});

// Counts resolver work on the real 4,208-node world, including selected refresh.
test('map resolves its evolving palette once per rendered node',async({page})=>{
 const server=await start(page,'/');try{
  const metrics=await page.evaluate(()=>{
   const original=EnfoldedInterface.resolve;let calls=0,milliseconds=0;
   EnfoldedInterface.resolve=node=>{const start=performance.now();const result=original(node);milliseconds+=performance.now()-start;calls++;return result;};
   const nodes=hierLayout.descendants().length;
   try{renderTree(hierLayout.data,{preservePresence:true});}finally{EnfoldedInterface.resolve=original;}
   return {nodes,calls,milliseconds};
  });
  console.log('Map palette work:',JSON.stringify(metrics));
  // Exact, not a bound: one resolution per rendered node, plus the selected
  // place (reused for its page tokens and marker) and the scene renderer.
  expect(metrics.nodes).toBe(4208);expect(metrics.calls).toBe(metrics.nodes+2);
 }finally{await server.close();}
});

// A retry control removed by a status change must not strand the keyboard.
// The navigation element is shared, so both clients are covered.
for(const route of ['/app','/'])
test(`${route==='/app'?'scene':'map'} navigation keeps the player located when a focused control disappears`,async({page})=>{
 const server=await start(page,route);try{
  const nav=page.locator('enfolded-navigation');
  await nav.evaluate(el=>{el.context={...el.ctx,status:'error',retry(){}};});
  const retry=nav.getByRole('button',{name:'Retry passages'});
  await expect(retry).toBeVisible();await retry.focus();
  await expect.poll(()=>nav.evaluate(el=>el.shadowRoot.activeElement?.dataset.target)).toBe('retry');
  await nav.evaluate(el=>{el.context={...el.ctx,status:'loading',retry(){}};});
  await expect(retry).toHaveCount(0);
  await expect(page.locator('#node-name')).toBeFocused();
  expect(await page.evaluate(()=>document.activeElement===document.body)).toBe(false);
 }finally{await server.close();}
});

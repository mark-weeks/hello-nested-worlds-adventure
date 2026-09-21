import {test,expect} from '@playwright/test';
import {mkdir,readFile} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {serveUX,enterUX,key} from './ux-fixture.js';
import {disclose} from './disclosures.js';
const evidence=path.join(tmpdir(),'enfolded-ux-evidence');
const samples=JSON.parse(await readFile(new URL('./fixtures/visual-language.json',import.meta.url),'utf8'));
const region=samples[0].before.name,room=samples[1].before.name,instrument=samples[2].before.name;
const phrase=n=>n.replace(/-\d+$/,'');
const act=page=>page.locator('enfolded-interventions');
async function capture(page,name){await mkdir(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name+'.jpg'),type:'jpeg',quality:82,fullPage:true});}
async function fits(page){expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}

for(const route of ['/app','/']){
  const client=route==='/app'?'scene':'map';
  test(`${client}: navigation, return, identity and 200% text at narrow and wide widths`,async({page})=>{
    const server=await serveUX();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    try{
      await page.setViewportSize({width:1440,height:960});await page.emulateMedia({reducedMotion:'reduce'});
      await enterUX(page,server,route,region);
      await expect(page.locator('#node-name')).toHaveText(phrase(region));
      await page.getByRole('button',{name:'Act',exact:true}).click();
      await expect(act(page).locator('.choices button')).toHaveCount(4);
      await expect(page.locator('.node-identity')).toHaveCount(1);
      await expect(page.getByRole('group',{name:'Interaction mode'}).getByRole('button')).toHaveCount(3);
      await fits(page);await capture(page,client+'-wide');
      if(client==='map'){
        const marker=page.locator('.node.selected .node-marker').first();
        const beforeColor=await marker.getAttribute('fill');
        await act(page).getByRole('button',{name:'Channel',exact:true}).click();
        await expect.poll(()=>marker.getAttribute('fill')).not.toBe(beforeColor);
      }
      const nav=page.locator('enfolded-navigation');
      await nav.getByRole('button',{name:'Room ↘ Broken Ember Gallery',exact:true}).focus();await page.keyboard.press('Enter');
      await expect(page.locator('#node-name')).toHaveText(phrase(room));
      await expect(page.locator('#node-name')).toBeFocused();
      await nav.locator('.top button').first().click();
      await nav.getByText('Return to a visited place',{exact:true}).click();
      await nav.getByRole('button',{name:'Room · Broken Ember Gallery',exact:true}).click();
      await expect(page.locator('#node-name')).toHaveText(phrase(room));
      await page.setViewportSize({width:390,height:844});
      await page.route('**/puzzle?*',r=>r.abort('failed'));
      await page.getByRole('button',{name:'Puzzle',exact:true}).click();
      await expect(page.getByRole('button',{name:'Retry question'})).toBeVisible();
      await page.unroute('**/puzzle?*');
      await page.getByRole('button',{name:'Retry question'}).click();
      await expect(page.getByRole('button',{name:'Submit',exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Act',exact:true}).click();
      await fits(page);await capture(page,client+'-narrow');
      await act(page).getByRole('button',{name:'Combine actions',exact:true}).focus();
      await page.keyboard.press('Enter');
      await expect(act(page).getByRole('button',{name:'Leave combination',exact:true})).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(act(page).getByRole('button',{name:'Combine actions',exact:true})).toBeFocused();
      await page.evaluate(()=>document.documentElement.style.fontSize='32px');
      await disclose(page,'Describe an intention');
      const input=act(page).getByRole('textbox',{name:'Your intention'});
      await input.fill('illuminate');await input.press('Tab');
      await expect(act(page).getByRole('button',{name:'Act on this intention'})).toBeFocused();
      await fits(page);
      if(client==='map'){
        const marker=await page.locator('.node.selected .node-marker').first().boundingBox();
        const graph=await page.locator('#graph').boundingBox();
        expect(marker.x).toBeGreaterThan(graph.x);expect(marker.x+marker.width).toBeLessThan(graph.x+graph.width);
        expect(marker.y).toBeGreaterThan(graph.y);expect(marker.y+marker.height).toBeLessThan(graph.y+graph.height);
      }
      await capture(page,client+'-text-zoom');
      expect(errors).toEqual([]);
    }finally{await server.close();}
  });

  test(`${client}: failed first read, unavailable actions, lost reply, focus and pending receipt`,async({page})=>{
    const server=await serveUX();let fail=true,dropped=false;
    try{
      await page.setViewportSize({width:390,height:844});
      await page.route('**/interventions?*',r=>fail?r.abort('failed'):r.continue());
      await enterUX(page,server,route,instrument);await page.getByRole('button',{name:'Act',exact:true}).click();
      await expect(act(page).getByRole('button',{name:'Listen again'})).toBeVisible();fail=false;
      await act(page).getByRole('button',{name:'Listen again'}).click();
      await expect(act(page).locator('.choices button')).toHaveCount(4);
      await page.route('**/interventions/commit',async r=>{if(!dropped){dropped=true;await r.fetch();await r.abort('failed');}else await r.continue();});
      await act(page).getByRole('button',{name:'Engrave',exact:true}).focus();await page.keyboard.press('Enter');
      const recover=act(page).getByRole('button',{name:'Recover earlier attempt'});
      await expect(recover).toBeVisible();
      await expect(act(page).getByRole('button',{name:'Engrave',exact:true})).toBeDisabled();
      await fits(page);await capture(page,client+'-recovery');
      await recover.focus();await page.keyboard.press('Enter');
      await expect(act(page).getByRole('status')).toContainText('Engrave');
      await expect(act(page).getByRole('button',{name:'Engrave',exact:true})).toBeEnabled();
      await disclose(page,'Actions still echoing');
      await expect(act(page)).toContainText('Consequences pending');
      await expect(act(page)).not.toContainText('Where the consequences may travel');
      await capture(page,client+'-pending');
      const receipt=await(await page.request.get(server.url+'/interventions?node='+instrument,{headers:{'X-Beta-Key':key}})).json();
      expect(receipt.recent.filter(r=>r.origin===instrument)).toHaveLength(1);
    }finally{await server.close();}
  });
}

test('scene: four scales, two objects and observed before/after states',async({page})=>{
  test.setTimeout(60000);
  const server=await serveUX();
  try{
    await page.setViewportSize({width:1440,height:960});await page.emulateMedia({reducedMotion:'reduce'});
    await enterUX(page,server,'/app',region);
    for(const [index,sample] of samples.entries()){
      await page.goto(server.url+'/app?node='+encodeURIComponent(sample.before.name));
      await expect(page.locator('#node-name')).toHaveText(phrase(sample.before.name));
      await page.getByRole('button',{name:'Act',exact:true}).click();
      const choice=act(page).getByRole('button',{name:sample.operation[0].toUpperCase()+sample.operation.slice(1),exact:true});
      await expect(choice).toBeEnabled();await page.waitForLoadState('networkidle');
      const before=await page.locator('.world-layout').getAttribute('style');
      const bounds=await choice.boundingBox();
      await capture(page,`comparison-${index}-before`);
      await choice.click();await expect(act(page).getByRole('status')).toContainText('attempts');
      await expect.poll(()=>page.locator('.world-layout').getAttribute('style')).not.toBe(before);
      await expect(page.locator('#node-description')).not.toHaveText(sample.before.senses.description);
      await expect(choice).toBeEnabled();
      const afterBounds=await choice.boundingBox();
      expect(afterBounds.width).toBe(bounds.width);expect(afterBounds.x).toBe(bounds.x);
      await page.waitForLoadState('networkidle');
      await capture(page,`comparison-${index}-after`);
    }
    // A bright and then shaded room use opaque navigation surfaces independent of art.
    await page.goto(server.url+'/app?node='+encodeURIComponent(room));await page.getByRole('button',{name:'Act',exact:true}).click();
    await act(page).getByRole('button',{name:'Shade',exact:true}).click();
    await expect(page.locator('#node-description')).toContainText('dim');await page.waitForLoadState('networkidle');await capture(page,'scene-dark-room');
    await page.route('**/media/places/*.png',r=>r.abort('failed'));await page.reload();
    await expect(page.locator('#node-name')).toHaveText(phrase(room));
    await page.getByRole('button',{name:'Act',exact:true}).click();await expect(act(page).locator('.choices button')).toHaveCount(4);
    await capture(page,'scene-missing-art');
    const pixels=await page.locator('canvas').evaluate(c=>c.getContext('2d').getImageData(0,0,1,1).data[3]);expect(pixels).toBe(255);
  }finally{await server.close();}
});

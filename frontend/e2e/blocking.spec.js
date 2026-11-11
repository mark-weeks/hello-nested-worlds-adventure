import {expect, test} from '@playwright/test';
import {spawn, spawnSync} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {serveBrowser} from './server.js';
import {disclose} from './disclosures.js';

const repo = path.resolve(import.meta.dirname, '../..');
const key = 'nw_' + 'a'.repeat(32);
const otherKey = 'nw_' + 'b'.repeat(32);

async function start() {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-blocking-'));
  const database = path.join(directory, 'worlds.db');
  const seeded = spawnSync(process.env.ENFOLDED_PYTHON || 'python', ['-c', `
from pathlib import Path
import sys
import persistence
persistence._DB_PATH=Path(sys.argv[1])
persistence.mint_invite_key('nw_'+'a'*32,'Ada')
persistence.mint_invite_key('nw_'+'b'*32,'Bea')
from multiverse import store
store.ensure_born(382)
`, database], {cwd:repo, encoding:'utf8'});
  if (seeded.status !== 0) throw new Error(seeded.stderr);
  const server = await serveBrowser({database});
  return {...server, close:async()=>{await server.close(); await rm(directory,{recursive:true,force:true});}};
}

async function enter(page, server, route, credential=key, name='Ada') {
  await page.addInitScript(({credential,name})=>{
    localStorage.setItem('nw_beta_key',credential);
    localStorage.setItem('nw_player_name',name);
    localStorage.setItem('nw_seen_intro','1');
    localStorage.setItem('nw_sound_preference','off');
  },{credential,name});
  await page.goto(server.url+route);
  await page.getByText('Travelers & chat',{exact:true}).click();
}

for (const route of ['/', '/app']) test(`${route}: block chat and presence across tabs, reload, and unblock an offline traveler`, async ({browser})=>{
  test.setTimeout(60_000);
  const server=await start();
  const owner=await browser.newContext();
  let other=await browser.newContext();
  try {
    const page=await owner.newPage();
    const sibling=await owner.newPage();
    const bea=await other.newPage();
    await enter(page,server,route);
    await enter(sibling,server,route==='/'?'/app':'/');
    await enter(bea,server,'/app',otherKey,'Bea');
    await expect(page.getByRole('button',{name:'Block Bea',exact:true})).toBeVisible();
    await expect(sibling.getByRole('button',{name:'Block Bea',exact:true})).toBeVisible();
    await bea.getByLabel('Message to travelers').fill('A live line before blocking');
    await bea.getByRole('button',{name:'Send',exact:true}).click();
    const feed=page.getByLabel('Recent events');
    await expect(feed).toContainText('A live line before blocking');
    // The roster and the buffered chat both offer the same private preference.
    await page.getByRole('button',{name:'Block Bea',exact:true}).first().click();
    await expect(page.getByRole('button',{name:'Block Bea',exact:true})).toHaveCount(0);
    await expect(sibling.getByRole('button',{name:'Block Bea',exact:true})).toHaveCount(0);
    await expect(feed).not.toContainText('A live line before blocking');
    // Blocking is one-way: Bea still sees Ada and receives Ada's chat.
    await expect(bea.getByRole('button',{name:'Block Ada',exact:true}).first()).toBeVisible();
    await bea.getByLabel('Message to travelers').fill('A live line after blocking');
    await bea.getByRole('button',{name:'Send',exact:true}).click();
    await expect(bea.getByLabel('Recent events')).toContainText('A live line after blocking');
    await expect(page.getByLabel('Recent events')).not.toContainText('A live line after blocking');
    await expect(sibling.getByLabel('Recent events')).not.toContainText('A live line after blocking');
    await other.close();
    await page.reload();
    await page.getByText('Travelers & chat',{exact:true}).click();
    await page.getByText('Blocked travelers (1)',{exact:true}).click();
    await expect(page.getByRole('button',{name:'Unblock Bea',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Unblock Bea',exact:true}).click();
    await expect(page.getByText('Blocked travelers (1)',{exact:true})).toHaveCount(0);
    other=await browser.newContext();
    const returned=await other.newPage();
    await enter(returned,server,'/app',otherKey,'Bea');
    await expect(page.getByRole('button',{name:'Block Bea',exact:true})).toBeVisible();
    await expect(sibling.getByRole('button',{name:'Block Bea',exact:true})).toBeVisible();
    // The first tab's old HTTP reply must not undo a later choice in another tab.
    let releaseResponse, committed;
    const heldResponse=new Promise(resolve=>{releaseResponse=resolve;});
    const committedResponse=new Promise(resolve=>{committed=resolve;});
    await page.route('**/blocks?*',async intercepted=>{
      const response=await intercepted.fetch();
      committed();
      await heldResponse;
      await intercepted.fulfill({response});
    },{times:1});
    await page.getByRole('button',{name:'Block Bea',exact:true}).click();
    await committedResponse;
    await sibling.getByText('Blocked travelers (1)',{exact:true}).click();
    await sibling.getByRole('button',{name:'Unblock Bea',exact:true}).click();
    await expect(page.getByRole('button',{name:'Block Bea',exact:true})).toBeVisible();
    releaseResponse();
    await expect(page.getByText('Unblocked.',{exact:true})).toBeVisible();
    await expect(page.getByText('Blocked travelers (1)',{exact:true})).toHaveCount(0);
    // A failed save leaves the traveler reachable and offers retry.
    await page.route('**/blocks?*', async intercepted=>{
      if (intercepted.request().method()==='POST') await intercepted.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Your choice could not be saved. Try again.'})});
      else await intercepted.continue();
    });
    await page.getByRole('button',{name:'Block Bea',exact:true}).click();
    await expect(page.getByText('Your choice could not be saved. Try again.',{exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Block Bea',exact:true})).toBeEnabled();
  } finally {
    await owner.close(); await other.close(); await server.close();
  }
});

// A pipe-controlled, model-free cast on a disposable real server. Commands
// enter through the fixture process, never a production control endpoint.
async function startCast() {
  const directory=await mkdtemp(path.join(tmpdir(),'enfolded-cast-blocking-'));
  const child=spawn(process.env.ENFOLDED_PYTHON || 'python',['-u','-c',`
import json, sys, threading
from pathlib import Path
import persistence
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
persistence.mint_invite_key('nw_'+'a'*32,'Ada')
from multiverse import store
from server import _Handler, _ThreadedServer
from server.rooms import get_room, agent_enter, agent_move, agent_leave, broadcast
root=store.world_tree(382)
room=get_room(382)
for name,persona in [('Tessera','tender'),('Vex','destabilizer')]:
    agent_enter(room,name,persona)
    agent_move(room,name,root.name)
persistence.record_mutation(382,root.name,'AGENT_TALK',None,{
    'a':'Tessera','b':'Vex','lines':[{'speaker':'Tessera','line':'A stored line before blocking.'}]})
server=_ThreadedServer(('127.0.0.1',0),_Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
print(server.server_address[1],flush=True)
for command in sys.stdin:
    command=command.strip()
    if command=='leave':
        agent_leave(room,'Tessera')
    elif command=='enter':
        agent_enter(room,'Tessera','tender')
        agent_move(room,'Tessera',root.name)
    else:
        lines=[{'speaker':'Tessera','line':'A live Tessera line '+command},
               {'speaker':'Vex','line':'A live Vex line '+command},
               {'speaker':None,'line':'A live meeting stage '+command}]
        broadcast(room,{'type':'agent_encounter','agent1':'Tessera','agent2':'Vex','node':root.name})
        broadcast(room,{'type':'agent_talk','a':'Tessera','b':'Vex','node':root.name,'lines':lines})
        broadcast(room,{'type':'agent_done','name':'Tessera','node':root.name,'nodes_visited':int(command)})
        broadcast(room,{'type':'intervention_changed','node':root.name,'flavor':'A shared change remains visible '+command})
    print(json.dumps({'ok':True}),flush=True)
`,directory],{cwd:repo,env:{...process.env,NESTED_WORLDS_CANONICAL_SEED:'382',NESTED_WORLDS_DISABLE_AI:'1',NESTED_WORLDS_DISABLE_IMAGES:'1'},stdio:['pipe','pipe','pipe']});
  let errors='';
  child.stderr.on('data',chunk=>{errors+=chunk;});
  const reader=createInterface({input:child.stdout});
  const lines=reader[Symbol.asyncIterator]();
  const read=async()=>{
    const {value,done}=await lines.next();
    if(done)throw new Error(errors || 'Cast fixture ended');
    return value;
  };
  const port=Number(await read());
  return {url:`http://127.0.0.1:${port}`,
    command:async command=>{child.stdin.write(command+'\n');return JSON.parse(await read());},
    close:async()=>{
      if(child.exitCode===null){const exited=once(child,'exit');child.kill('SIGKILL');await exited;}
      reader.close();await rm(directory,{recursive:true,force:true});
    }};
}

for(const route of ['/','/app'])test(`${route}: the same block controls hide an inhabitant's live speech and presence`,async({browser})=>{
  test.setTimeout(60_000);
  const server=await startCast();
  const owner=await browser.newContext();
  try {
    const page=await owner.newPage(),sibling=await owner.newPage();
    await enter(page,server,route);
    await enter(sibling,server,route==='/'?'/app':'/');
    await disclose(page,'History & journal');
    const feed=page.getByLabel('Recent events');
    await expect(page.getByRole('button',{name:'Block Tessera',exact:true})).toBeVisible();
    await server.command('1');
    await expect(feed).toContainText('A live Tessera line 1');
    await expect(feed).toContainText('A live meeting stage 1');
    // Block from the inhabitant's live speech, using the same control as chat.
    await feed.getByRole('button',{name:'Block Tessera',exact:true}).click();
    await expect(page.getByRole('button',{name:'Block Tessera',exact:true})).toHaveCount(0);
    await expect(sibling.getByRole('button',{name:'Block Tessera',exact:true})).toHaveCount(0);
    await expect(feed).not.toContainText('A live Tessera line 1');
    await expect(feed).not.toContainText('A live meeting stage 1');
    await expect(feed).not.toContainText('Tessera meets Vex');
    await expect(feed).toContainText('A live Vex line 1');
    await server.command('2');
    await expect(feed).toContainText('A live Vex line 2');
    await expect(feed).not.toContainText('A live Tessera line 2');
    await expect(feed).not.toContainText('A live meeting stage 2');
    await expect(feed).toContainText('A shared change remains visible 2');
    const history=await(await page.request.get(server.url+'/history?key='+key)).json();
    expect(history.mutations.some(m=>m.type==='AGENT_TALK' && m.data.lines.some(l=>l.line==='A stored line before blocking.'))).toBe(true);
    await server.command('leave');
    await page.reload();
    await disclose(page,'Travelers & chat');
    await disclose(page,'Blocked travelers (1)');
    await page.getByRole('button',{name:'Unblock Tessera',exact:true}).click();
    await server.command('enter');
    await expect(page.getByRole('button',{name:'Block Tessera',exact:true})).toBeVisible();
    await expect(sibling.getByRole('button',{name:'Block Tessera',exact:true})).toBeVisible();
    await server.command('3');
    await expect(page.getByLabel('Recent events')).toContainText('A live Tessera line 3');
  } finally {await owner.close();await server.close();}
});

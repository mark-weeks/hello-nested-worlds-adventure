import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
export const key='nw_'+'a'.repeat(32);
export async function serveUX() {
  const dir=await mkdtemp(path.join(tmpdir(),'enfolded-ux-test-'));
  const child=spawn(process.env.ENFOLDED_PYTHON || 'python',['-u','-c',`
import sys
from pathlib import Path
import persistence
persistence._DB_PATH=Path(sys.argv[1])/'worlds.db'
persistence.mint_invite_key('nw_'+'a'*32,'UX traveler')
from multiverse import store
store.ensure_born(382)
from server import _Handler,_ThreadedServer
server=_ThreadedServer(('127.0.0.1',0),_Handler)
print(server.server_address[1],flush=True)
server.serve_forever()
`,dir],{cwd:path.resolve(import.meta.dirname,'../..'),env:{...process.env,NESTED_WORLDS_CANONICAL_SEED:'382',NESTED_WORLDS_DISABLE_AI:'1',NESTED_WORLDS_DISABLE_IMAGES:'1',NESTED_WORLDS_MATURATION_SCALE:'0'},stdio:['ignore','pipe','pipe']});
  let errors='';child.stderr.on('data',s=>errors+=s);
  const port=await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error(errors || 'UX server did not start')),15000);
    const reader=createInterface({input:child.stdout});reader.once('line',line=>{clearTimeout(timeout);reader.close();resolve(Number(line));});
    child.once('exit',()=>{clearTimeout(timeout);reject(new Error(errors));});
  }).catch(e=>{child.kill('SIGKILL');throw e;});
  return {url:`http://127.0.0.1:${port}`,async close(){const done=once(child,'exit');child.kill('SIGKILL');await done;await rm(dir,{recursive:true,force:true});}};
}
export async function enterUX(page,server,route,node){
  await page.addInitScript(({key,node})=>{
    localStorage.setItem('nw_beta_key',key);localStorage.setItem('nw_seen_intro','1');localStorage.setItem('nw_player_name','UX traveler');localStorage.setItem('nw_last_node',node);localStorage.setItem('nw_view_depth','11');localStorage.setItem('nw_sound_preference','off');
  },{key,node});
  await page.goto(server.url+route);
}

// All browser fixtures use the same Python entry point and newline handshake.
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';

export async function serveBrowser({database,preseed,invite,player,pump=false,env={}}={}) {
  const directory=database ? null : await mkdtemp(path.join(tmpdir(),'enfolded-browser-'));
  const args=['-u','scripts/e2e_server.py','0','--database',database || path.join(directory,'worlds.db')];
  if(preseed!=null)args.push('--preseed',String(preseed));
  if(invite)args.push('--invite',invite,'--player',player || 'Browser traveler');
  if(pump)args.push('--pump');
  const child=spawn(process.env.ENFOLDED_PYTHON || 'python',args,{
    cwd:path.resolve(import.meta.dirname,'../..'),
    env:{...process.env,NESTED_WORLDS_CANONICAL_SEED:'382',NESTED_WORLDS_DISABLE_AI:'1',NESTED_WORLDS_DISABLE_IMAGES:'1',...env},
    stdio:['ignore','pipe','pipe'],
  });
  let errors='';child.stderr.on('data',s=>{errors=(errors+s).slice(-8000);});
  const close=async()=>{
    if(child.exitCode===null && child.signalCode===null && child.pid){const exited=once(child,'exit');child.kill('SIGKILL');await exited;}
    if(directory)await rm(directory,{recursive:true,force:true});
  };
  try {
    const port=await new Promise((resolve,reject)=>{
      const reader=createInterface({input:child.stdout});
      const finish=(error,port)=>{clearTimeout(timeout);reader.close();child.off('error',fail);child.off('exit',exit);error?reject(error):resolve(port);};
      const fail=e=>finish(e),exit=code=>finish(new Error(`Browser server ${code}: ${errors}`));
      const timeout=setTimeout(()=>finish(new Error(errors || 'Browser server did not start')),15000);
      child.once('error',fail);child.once('exit',exit);
      reader.once('line',line=>{const port=Number(line);finish(Number.isInteger(port)&&port>0&&port<65536 ? null : new Error(`Invalid server port: ${line}`),port);});
    });
    return {child,url:`http://127.0.0.1:${port}`,close};
  }catch(error){await close();throw error;}
}

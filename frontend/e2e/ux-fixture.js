import {serveBrowser} from './server.js';
export const key='nw_'+'a'.repeat(32);
export const serveUX=()=>serveBrowser({preseed:382,invite:key,player:'UX traveler',env:{NESTED_WORLDS_MATURATION_SCALE:'0'}});
export async function enterUX(page,server,route,node){
  await page.addInitScript(({key,node})=>{
    localStorage.setItem('nw_beta_key',key);localStorage.setItem('nw_seen_intro','1');localStorage.setItem('nw_player_name','UX traveler');localStorage.setItem('nw_last_node',node);localStorage.setItem('nw_view_depth','11');localStorage.setItem('nw_sound_preference','off');
  },{key,node});
  await page.goto(server.url+route);
}

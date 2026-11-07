import {describe, it, expect, vi} from 'vitest';
import '../../../static/clientlogic.js';

const {withoutBlockedLiveEvents, savePersonalBlock} = globalThis.EnfoldedClient;

describe('private blocking in both clients', () => {
  it('removes buffered live chat and presence by participant, preserving history and shared effects', () => {
    const history = {type:'history', text:'Ada passed into a room'};
    const effect = {type:'causal', participant_id:'ada', text:'A changed place'};
    const agent = {type:'chat', name:'Ada', text:'A different traveler'};
    const events = [
      {type:'chat', liveParticipant:'ada', text:'hide'},
      {type:'system', liveParticipant:'ada', text:'Ada joined'},
      {type:'chat', liveParticipant:'bea', text:'keep'},
      history, effect, agent,
    ];
    expect(withoutBlockedLiveEvents(events, [{id:'ada',name:'Old Ada'}]))
      .toEqual([events[2], history, effect, agent]);
    expect(withoutBlockedLiveEvents(events, [])).toEqual(events);
    expect(events).toHaveLength(6);
  });

  it('treats agent speech and shared live encounters like other travelers, without hiding their world effects', () => {
    const events = [
      {type:'chat', liveParticipant:'agent:Tessera', text:'a live line'},
      {type:'system', liveParticipants:['agent:Tessera','agent:Vex'], text:'a live meeting'},
      {kind:'encounter', liveParticipants:['agent:Tessera','agent:Vex']},
      {type:'chat', liveParticipant:'agent:Vex', text:'another speaker'},
      {type:'history', text:'Tessera spoke here earlier'},
      {type:'causal', actor:'Tessera', text:'a real world change'},
    ];
    expect(withoutBlockedLiveEvents(events,[{id:'agent:Tessera',name:'Tessera'}])).toEqual(events.slice(3));
  });

  it('sends only the stable target and requested preference, returning the persisted list', async () => {
    const blocks = [{id:'ada',name:'Ada'}];
    const request = vi.fn().mockResolvedValue({ok:true,json:async()=>({blocks})});
    expect(await savePersonalBlock('/blocks?key=personal', 'ada', true, request)).toEqual(blocks);
    expect(request).toHaveBeenCalledWith('/blocks?key=personal', {
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({participant:'ada',blocked:true}),
    });
    request.mockResolvedValue({ok:false,json:async()=>({error:'A current personal invite is required.'})});
    await expect(savePersonalBlock('/blocks','ada',false,request)).rejects.toThrow('A current personal invite is required.');
  });

  it.each([
    ['an offline browser', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['a proxy error page', async () => ({ok:false,json:async()=>{throw new SyntaxError('Unexpected token <');}})],
    ['an incomplete JSON reply', async () => ({ok:true,json:async()=>({})})],
  ])('offers an authored retry after %s', async (_description, request) => {
    await expect(savePersonalBlock('/blocks', 'ada', true, request))
      .rejects.toThrow('Your block could not be saved. Try again.');
  });
});

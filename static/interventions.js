// One accessible composer shared by the scene and map. All player/model text is
// inserted as textContent; only the fixed stylesheet below is parsed as markup.
const STYLE = `:host{display:block;color:#dfded0;font:13px/1.55 system-ui}*{box-sizing:border-box}section{padding:22px 18px;border-bottom:1px solid #344947;background:linear-gradient(135deg,#102725,#101c24)}h2{font:24px Georgia,serif;margin:0 0 8px}p{margin:8px 0;color:#bacec8}button,input,select,textarea{font:inherit;color:#eee4cd;background:#0a191d;border:1px solid #617974;border-radius:3px;padding:9px;max-width:100%}button{cursor:pointer;text-align:left;min-height:42px}button:hover{background:#254743}button:disabled{opacity:.5;cursor:wait}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:2px solid #e7c98e;outline-offset:2px}label{display:block;margin:12px 0 4px;font-size:12px}textarea{width:100%;min-height:68px}.row{display:flex;gap:6px;margin:7px 0;align-items:center}.row select{flex:1;min-width:0}.row button{flex:none}.examples{display:flex;flex-wrap:wrap;gap:7px;margin:13px 0}.examples button{font-size:12px;flex:1 1 120px}.primary{background:#d6bf8d;color:#0b2022;border-color:#e5ce9b;font-weight:600;width:100%;margin:10px 0}.primary:hover{background:#f3dcac}.caption{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#d6bf8d}.preview{border-left:2px solid #d6bf8d;padding:0 0 0 12px;margin:18px 0}.preview ol{padding-left:18px}.route{display:flex;flex-direction:column;gap:5px;margin:10px 0}.route button{font-size:12px;border:0;background:#16312e;padding:6px}.error{color:#f3b9a3}.recent{border-top:1px solid #46635b;margin-top:18px;padding-top:12px}.recent article{margin:12px 0;font-size:12px}.recent strong{color:#e5d5b4}summary{cursor:pointer;min-height:42px;padding:8px 0}.quiet{font-size:12px;color:#a9c0b9}`;
function el(tag, text, props = {}) { const n = document.createElement(tag); if (text != null) n.textContent = text; Object.assign(n, props); return n; }
const display = name => (name || '').replace(/-\d+$/, '');
class InterventionComposer extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this.steps = [{op:'charge',amount:2},{op:'release',amount:1}]; this.generation = 0; }
  set context(value) {
    const changed = this.ctx?.node?.name !== value.node.name || this.ctx?.seed !== value.seed || this.ctx?.key !== value.key;
    this.ctx = value;
    if (changed) {
      this.generation++; this.busy=false; this.data = null; this.preview = null; this.pending = null; this.message = ''; this.delegate = ''; this.intention = ''; this.restored = false;
      this.render(); this.load();
    } else if (this.revision !== value.node.senses?.revision) this.load();
    this.revision = value.node.senses?.revision;
  }
  disconnectedCallback() { this.generation++; clearTimeout(this.poll); }
  async request(path, body) {
    const ctx = this.ctx;
    const response = await fetch(path + (body ? '' : '?' + new URLSearchParams({seed:ctx.seed,node:ctx.node.name})), {
      method:body ? 'POST':'GET', cache:'no-store', headers:{'Content-Type':'application/json','X-Beta-Key':ctx.key || ''},
      ...(body ? {body:JSON.stringify({seed:ctx.seed,node:ctx.node.name,...body})} : {}),
    });
    const data = await response.json();
    if (!response.ok || data.error) { const error = new Error(data.error || 'The arrangement could not be heard.'); error.status = response.status; throw error; }
    return data;
  }
  async load() {
    if (!this.ctx.key) { this.message='Enter with an invite to compose lasting changes.'; this.render(); return; }
    const generation = this.generation;
    try {
      const data = await this.request('/interventions');
      if (generation !== this.generation || !this.isConnected) return;
      const had = this.data?.recent?.reduce((n,r) => n+r.pending,0);
      this.data = data;
      this.storageKey = `nw_arrangement:${data.participant}:${this.ctx.seed}:${this.ctx.node.name}`;
      if (!this.restored) {
        this.restored = true;
        try { const saved = JSON.parse(localStorage.getItem(this.storageKey)); if (saved) { this.preview=saved.preview; this.pending=saved.intent; this.steps=saved.preview.steps; this.delegate=saved.preview.delegate || ''; this.message='An earlier commitment still needs confirmation. Retry to recover its outcome safely.'; } } catch (_) { /* no stored draft */ }
      }
      // Poll outcomes without replacing focused controls or an in-progress draft.
      if (!this.shadowRoot.activeElement && !this.busy) this.render();
      else this.renderRecent();
      const pending = data.recent.reduce((n,r) => n+r.pending,0);
      if (had != null && had !== pending) this.ctx.changed?.();
      clearTimeout(this.poll);
      if (pending) this.poll=setTimeout(() => this.load(),4000);
    } catch (error) { if (generation === this.generation) { this.message=error.message; this.render(); } }
  }
  invalidate() { if (this.pending) return; this.preview=null; this.message=''; }
  async previewPlan(body) {
    if (this.busy || this.pending) return;
    const generation=this.generation; this.busy=true; this.message='Listening to the possible consequences…'; this.render();
    try {
      const preview = await this.request('/interventions/preview',{...body,delegate:this.delegate || null});
      if(generation!==this.generation) return;
      this.preview=preview; this.steps=preview.steps; this.message='';
    } catch(error) { if(generation===this.generation) this.message=error.message; }
    finally { if(generation===this.generation) { this.busy=false; this.render(); } }
  }
  async commit() {
    if(this.busy || !this.preview) return;
    const generation=this.generation, ctx=this.ctx, preview=this.preview, storage=this.storageKey;
    this.busy=true; this.message='Setting the arrangement in motion…'; this.render();
    try {
      if (!this.pending) await ctx.ensure?.(ctx.node.name);
      if(generation!==this.generation) return;
      const payload={steps:preview.steps,expected:preview.expected,delegate:preview.delegate || null};
      const intent=this.pending || await globalThis.EnfoldedIntents.begin('intervention',ctx.seed,{node:ctx.node.name,...payload},ctx.key);
      if(generation!==this.generation) return;
      if(!intent) throw new Error('Enter with your invite to leave a lasting intervention.');
      const saved=JSON.stringify({intent,preview});
      try {
        localStorage.setItem(storage,saved);
        if(localStorage.getItem(storage)!==saved) throw new Error('storage unavailable');
      } catch (_) { throw new Error('Your browser could not keep a recovery copy. Nothing was submitted. Allow local storage, then try again.'); }
      this.pending=intent;
      const result=await this.request('/interventions/commit',{...payload,request_id:intent.request_id});
      globalThis.EnfoldedIntents.finish(intent);
      try { localStorage.removeItem(storage); } catch (_) { /* unavailable storage */ }
      if(generation!==this.generation) return;
      this.pending=null; this.preview=null; this.message=result.flavor;
      ctx.changed?.(); await this.load();
    } catch(error) {
      if(generation!==this.generation) return;
      if(error.status===409 || error.status===403) {
        globalThis.EnfoldedIntents.finish(this.pending); this.pending=null; this.preview=null;
        try { localStorage.removeItem(storage); } catch (_) { /* unavailable storage */ }
      }
      this.message=error.message || 'The reply was lost. Retry this commitment to recover its outcome.';
    } finally { if(generation===this.generation) { this.busy=false; this.render(); } }
  }
  renderRecent() {
    const root=this.shadowRoot.querySelector('.recent'); if(!root) return;
    root.replaceChildren(el('span','YOUR THREADS THROUGH THE WORLD',{className:'caption'}));
    for(const r of this.data?.recent || []) {
      const item=el('article'); item.append(el('strong',`${r.performer} · ${r.summary}`),el('p',`${display(r.origin)} · ${r.pending ? `${r.pending} arrivals still travelling` : 'All consequences settled'}`));
      for(const a of r.arrivals) { const b=el('button',`${a.status==='completed'?'✓':'◌'} ${display(a.node)}`); b.onclick=()=>this.ctx.jump?.(a.node); item.append(b); }
      root.append(item);
    }
    if(!this.data?.recent?.length) root.append(el('p','What you set in motion will remain here when you return.'));
  }
  render() {
    const root=this.shadowRoot; root.replaceChildren(el('style',STYLE));
    const section=el('section'); section.setAttribute('aria-label','Shape this place'); root.append(section);
    section.append(el('span','COMPOSE A CONSEQUENCE',{className:'caption'}),el('h2','Shape this place'),el('p','Build something that can remember. Send a wave outward, turn it inward, or free what has been held.'));
    if(!this.data) { section.append(el('p',this.message || 'Listening to this place…')); return; }
    const state=this.data.state;
    section.append(el('p',`${state.woven?'Woven resonator':'Unbound energy'} · ${state.energy} pulses · ${state.polarity<0?'inward':'outward'} polarity`,{className:'quiet'}));
    const blocked=this.busy || !!this.pending;
    const examples=el('div',null,{className:'examples'});
    for(const idea of this.data.suggestions) { const b=el('button',idea.title,{disabled:blocked}); b.onclick=()=>{this.steps=idea.steps.map(s=>({...s}));this.invalidate();this.render();};examples.append(b); } section.append(examples);
    this.steps.forEach((step,i)=>{
      const row=el('div',null,{className:'row'});row.append(el('span',String(i+1)));
      const select=el('select',null,{disabled:blocked});select.setAttribute('aria-label',`Operation ${i+1}`);
      for(const [op,info] of Object.entries(this.data.operators)) select.append(el('option',info.label,{value:op,title:info.description}));
      select.value=step.op;select.onchange=()=>{this.steps[i]={op:select.value,amount:1};this.invalidate();this.render();};row.append(select);
      if(step.op==='charge') { const amount=el('select',null,{disabled:blocked}); amount.setAttribute('aria-label',`Pulses ${i+1}`);for(const n of [1,2,3]) amount.append(el('option',`${n} pulses`,{value:n}));amount.value=step.amount;amount.onchange=()=>{step.amount=Number(amount.value);this.invalidate();this.render();};row.append(amount); }
      const remove=el('button','×',{disabled:blocked || this.steps.length===1});remove.setAttribute('aria-label',`Remove operation ${i+1}`);remove.onclick=()=>{this.steps.splice(i,1);this.invalidate();this.render();};row.append(remove);section.append(row);
    });
    const add=el('button','+ Add operation',{disabled:blocked || this.steps.length>=4});add.onclick=()=>{this.steps.push({op:'charge',amount:1});this.invalidate();this.render();};section.append(add);
    const help=el('details'),summary=el('summary','What can these operations do?');help.append(summary);for(const info of Object.values(this.data.operators))help.append(el('p',`${info.label} — ${info.description}`));section.append(help);
    section.append(el('label','Who will enact this?',{htmlFor:'performer'}));
    const delegate=el('select',null,{id:'performer',disabled:blocked});delegate.append(el('option','I will',{value:''}));for(const name of this.data.agents) delegate.append(el('option',name,{value:name}));delegate.value=this.delegate;delegate.onchange=()=>{this.delegate=delegate.value;this.invalidate();this.render();};section.append(delegate);
    if(this.delegate) {const ask=el('button',`Ask ${this.delegate} for an approach`,{disabled:blocked});ask.onclick=()=>this.previewPlan({});section.append(ask);}
    const preview=el('button','Preview consequences',{className:'primary',disabled:blocked});preview.onclick=()=>this.previewPlan({steps:this.steps});section.append(preview);
    const natural=el('details');natural.append(el('summary','Describe your own intention'));
    const input=el('textarea',null,{value:this.intention,maxLength:600,placeholder:'Weave a resonator, gather two pulses, then release their memory.'});input.setAttribute('aria-label','Your intention');input.disabled=blocked;input.oninput=()=>this.intention=input.value;natural.append(input);
    const interpret=el('button','Find a dependable arrangement',{disabled:blocked});interpret.onclick=()=>this.previewPlan({intention:this.intention});natural.append(interpret,el('p','With a connected model, describe an intention in your own words. Explicit notation also works: weave, charge 2, release.',{className:'quiet'}));section.append(natural);
    if(this.preview) {
      const p=this.preview,box=el('div',null,{className:'preview'});box.append(el('strong',p.summary));const notes=el('ol');for(const note of p.notes)notes.append(el('li',note));box.append(notes,el('p',p.tradeoff));
      const route=el('div',null,{className:'route'});for(const r of p.route) {const b=el('button',`${r.in_seconds?`~${r.in_seconds}s`:'Here'} · ${display(r.node)} · ${r.level}`,{disabled:this.busy});b.onclick=()=>this.ctx.jump?.(r.node);route.append(b);} box.append(route);
      if(p.invitation) box.append(el('p',p.invitation));
      const commit=el('button',this.pending?'Confirm earlier commitment':p.delegate?`Entrust this to ${p.delegate}`:'Commit this arrangement',{className:'primary',disabled:this.busy});commit.onclick=()=>this.commit();box.append(commit);section.append(box);
    }
    const status=el('p',this.message,{className:'status'});status.setAttribute('role','status');status.setAttribute('aria-live','polite');section.append(status,el('div',null,{className:'recent'}));this.renderRecent();
  }
}
if(!customElements.get('enfolded-interventions')) customElements.define('enfolded-interventions',InterventionComposer);

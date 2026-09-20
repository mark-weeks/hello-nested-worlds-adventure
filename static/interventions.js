// One accessible composer shared by the scene and map. All player/model text is
// inserted as textContent; only the fixed stylesheet below is parsed as markup.
const STYLE = `:host{display:block;color:#dfded0;font:13px/1.55 system-ui}*{box-sizing:border-box}section{padding:8px 0}.choices{display:grid;grid-template-columns:1fr 1fr;gap:8px}.choices button{display:flex;flex-direction:column;gap:5px}.choices small{font-size:11px;color:#bacec8;font-weight:normal}.selected{border-color:#e7c98e;background:#254743}h2{font:24px Georgia,serif;margin:0 0 8px}p{margin:8px 0;color:#bacec8}button,input,select,textarea{font:inherit;color:#eee4cd;background:#0a191d;border:1px solid #617974;border-radius:3px;padding:9px;max-width:100%}button{cursor:pointer;text-align:left;min-height:42px}button:hover{background:#254743}button:disabled{opacity:.5;cursor:wait}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:2px solid #e7c98e;outline-offset:2px}label{display:block;margin:12px 0 4px;font-size:12px}textarea{width:100%;min-height:68px}.row{display:flex;gap:6px;margin:7px 0;align-items:center}.row select{flex:1;min-width:0}.row button{flex:none}.examples{display:flex;flex-wrap:wrap;gap:7px;margin:13px 0}.examples button{font-size:12px;flex:1 1 120px}.primary{background:#d6bf8d;color:#0b2022;border-color:#e5ce9b;font-weight:600;width:100%;margin:10px 0}.primary:hover{background:#f3dcac}.caption{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#d6bf8d}.preview{border-left:2px solid #d6bf8d;padding:0 0 0 12px;margin:18px 0}.preview ol{padding-left:18px}.route{display:flex;flex-direction:column;gap:5px;margin:10px 0}.route button{font-size:12px;border:0;background:#16312e;padding:6px}.error{color:#f3b9a3}.recent{border-top:1px solid #46635b;margin-top:18px;padding-top:12px}.recent article{margin:12px 0;font-size:12px}.recent strong{color:#e5d5b4}summary{cursor:pointer;min-height:42px;padding:8px 0}.quiet{font-size:12px;color:#a9c0b9}`;
function el(tag, text, props = {}) { const n = document.createElement(tag); if (text != null) n.textContent = text; Object.assign(n, props); return n; }
const display = name => globalThis.EnfoldedClient.displayName(name || '');
class InterventionComposer extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this.steps = []; this.generation = 0; this.loadSequence = 0; }
  set context(value) {
    const changed = this.ctx?.node?.name !== value.node.name || this.ctx?.seed !== value.seed || this.ctx?.key !== value.key;
    // Hosts hand over fresh node objects on every refresh; only a changed
    // served revision means the choices may differ. Outcomes are polled.
    const revised = this.revision !== value.node.senses?.revision;
    this.ctx = value;
    if (changed) {
      this.generation++; this.busy=false; this.data = null; this.preview = null; this.pending = null; this.message = ''; this.steps = []; this.compose = false; this.intention = ''; this.restored = false;
      this.render(); this.load();
    } else if (revised) this.load();
    this.renderPending();
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
  async load(fromPoll = false) {
    if (!this.ctx.key) { this.message='Enter with an invite to compose lasting changes.'; this.render(); return; }
    const generation = this.generation, sequence = ++this.loadSequence;
    // Outcome polling must survive a failed poll: keep the last known pending
    // count so the timer is re-armed from it, and slow down after a failure.
    let pending = this.data?.recent?.reduce((n,r) => n+r.pending,0) || 0, failed = false;
    try {
      const data = await this.request('/interventions');
      if (generation !== this.generation || sequence !== this.loadSequence || !this.isConnected) return;
      const had = this.data?.recent?.reduce((n,r) => n+r.pending,0);
      this.data = data;
      if (fromPoll && this.message && this.message === this.pollError) this.message = '';
      this.storageKey = `nw_arrangement:${data.participant}:${this.ctx.seed}:${this.ctx.node.name}`;
      if (!this.restored) {
        this.restored = true;
        try { const saved = JSON.parse(localStorage.getItem(this.storageKey)); if (saved) { this.preview=saved.preview; this.pending=saved.intent; this.steps=saved.preview.steps;  this.message='An earlier commitment still needs confirmation. Retry to recover its outcome safely.'; } } catch (_) { /* no stored draft */ }
      }
      // Poll outcomes without replacing focused controls or an in-progress draft.
      if (!this.shadowRoot.activeElement && !this.busy) this.render();
      else this.renderRecent();
      pending = data.recent.reduce((n,r) => n+r.pending,0);
      // A node-triggered read already has fresh properties; only polling must
      // request them when it discovers a missed outcome notification.
      if (fromPoll && had != null && had !== pending) this.ctx.changed?.();
    } catch (error) {
      failed = true;
      if (generation === this.generation && sequence === this.loadSequence) { this.message=this.pollError=error.message; this.render(); }
    } finally {
      if (generation === this.generation && sequence === this.loadSequence && this.isConnected) {
        clearTimeout(this.poll);
        if (pending) this.poll=setTimeout(() => this.load(true), failed ? 8000 : 4000);
      }
    }
  }
  invalidate() { if (this.pending) return; this.preview=null; this.message=''; }
  choose(choice) {
    if (this.busy || this.pending) return;
    if (!this.compose && choice.preview) {
      // A single action was previewed with the choices; no request is spent.
      this.steps=choice.preview.steps; this.preview=choice.preview; this.message='';
      this.render(); this.shadowRoot.querySelector('.preview')?.focus(); return;
    }
    this.steps=this.compose ? [...this.steps,{op:choice.op,amount:1}].slice(0,4) : [{op:choice.op,amount:1}];
    return this.previewPlan({steps:this.steps});
  }
  async previewPlan(body) {
    if (this.busy || this.pending) return;
    const generation=this.generation; this.busy=true; this.preview=null; this.message='Listening to the possible consequences…'; this.render();
    try {
      const preview = await this.request('/interventions/preview',body);
      if(generation!==this.generation) return;
      // A quiet reply (no steps) is the world's authored line, shown as status.
      if(!Array.isArray(preview.steps) || !preview.steps.length) { this.preview=null; this.message=preview.response || 'The intention has not settled into a dependable shape. Try the actions below.'; }
      else { this.preview=preview; this.steps=preview.steps; this.message=''; }
    } catch(error) { if(generation===this.generation) this.message=error.message; }
    finally { if(generation===this.generation) { this.busy=false; this.render(); this.shadowRoot.querySelector('.preview')?.focus(); } }
  }
  async commit() {
    if(this.busy || !this.preview) return;
    const generation=this.generation, ctx=this.ctx, preview=this.preview, storage=this.storageKey;
    this.busy=true; this.message='Setting the arrangement in motion…'; this.render();
    try {
      if (!this.pending) await ctx.ensure?.(ctx.node.name);
      if(generation!==this.generation) return;
      const payload={steps:preview.steps,expected:preview.expected,version:preview.version || 1,...(preview.delegate ? {delegate:preview.delegate} : {})};
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
      // The host's refresh carries the acceptance notice, so it coalesces with the broadcast.
      this.steps=[]; this.compose=false; ctx.changed?.(result); await this.load();
    } catch(error) {
      if(generation!==this.generation) return;
      if(error.status===409 || error.status===403) {
        globalThis.EnfoldedIntents.finish(this.pending); this.pending=null; this.preview=null;
        try { localStorage.removeItem(storage); } catch (_) { /* unavailable storage */ }
      }
      this.message=error.message || 'The reply was lost. Retry this commitment to recover its outcome.';
    } finally { if(generation===this.generation) { this.busy=false; this.render(); } }
  }
  renderPending() {
    const target=this.shadowRoot.querySelector('.pending');
    if(target) target.textContent=(this.ctx?.node?.pending_actions || []).map(p=>`${p.count} ${p.verb} ${p.count===1?'change is':'changes are'} still traveling.`).join(' ');
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
    const section=el('section'); section.setAttribute('aria-label','Act here'); root.append(section);
    section.append(el('p',null,{className:'pending quiet'}));this.renderPending();
    if(!this.data) { section.append(el('p',this.message || 'Listening to this place…')); return; }
    const blocked=this.busy || !!this.pending;
    section.append(el('p','What would you change here?'));
    const choices=el('div',null,{className:'choices'});
    for(const choice of this.data.choices) {
      const chosen=this.steps.some(s=>s.op===choice.op);
      const button=el('button',null,{disabled:blocked || (this.compose && this.steps.length>=4) || (!this.compose && !choice.available),className:chosen?'selected':''});
      button.setAttribute('aria-label',choice.label);
      button.title=choice.reason || choice.description;
      button.append(el('strong',choice.label),el('small',choice.description));
      if(!choice.available && !this.compose) button.append(el('small','Already as it would be.'));
      button.onclick=()=>this.choose(choice); choices.append(button);
    }
    section.append(choices);
    if(this.steps.length && !this.pending) {
      const row=el('div',null,{className:'row'});
      const combine=el('button',this.compose?'Choose the next action above':'Combine with another action',{disabled:blocked || this.steps.length>=4});
      combine.onclick=()=>{this.compose=true;this.render();};
      const reset=el('button','Start over',{disabled:blocked});reset.onclick=()=>{this.steps=[];this.compose=false;this.preview=null;this.message='';this.render();};
      row.append(combine,reset);section.append(row);
    }
    const natural=el('details');natural.append(el('summary','Describe an intention'));
    const input=el('textarea',null,{value:this.intention,maxLength:600,placeholder:'What would you like to change here?'});input.setAttribute('aria-label','Your intention');input.disabled=blocked;input.oninput=()=>this.intention=input.value;natural.append(input);
    const interpret=el('button','Explore this intention',{disabled:blocked});interpret.onclick=()=>this.previewPlan({intention:this.intention});
    natural.append(interpret,el('p','Name actions in order to combine them. With a connected model, you can also describe your purpose in your own words. You will preview it before acting.',{className:'quiet'}));section.append(natural);
    if(this.preview) {
      const p=this.preview,box=el('div',null,{className:'preview'});box.append(el('strong',p.summary));box.tabIndex=-1;
      const changes=el('ul');for(const [key,value] of Object.entries(p.changed || {})) {
        if(key==='resonance') continue;
        changes.append(el('li',`${key.replaceAll('_',' ')} → ${String(value)}`));
      }box.append(changes,el('p',p.tradeoff));
      const route=el('details');route.append(el('summary','Where the consequences may travel'));
      route.append(el('p','Timing is approximate. Each receiving place responds to its conditions at arrival.',{className:'quiet'}));
      for(const r of p.route) route.append(el('p',`${r.in_seconds?`~${r.in_seconds}s`:'Here'} · ${display(r.node)}`));box.append(route);
      const commit=el('button',this.pending?'Confirm earlier action':'Act: '+p.summary,{className:'primary',disabled:this.busy});commit.onclick=()=>this.commit();box.append(commit);section.append(box);
    }
    const status=el('p',this.message,{className:'status'});status.setAttribute('role','status');status.setAttribute('aria-live','polite');section.append(status);
    if(this.data.recent?.length) {
      const history=el('details');history.append(el('summary','Actions still echoing'),el('div',null,{className:'recent'}));section.append(history);this.renderRecent();
    }
  }
}
if(!customElements.get('enfolded-interventions')) customElements.define('enfolded-interventions',InterventionComposer);

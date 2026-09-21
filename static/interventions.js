// One accessible composer shared by the scene and map. All player/model text is
// inserted as textContent; only the fixed stylesheet below is parsed as markup.
const STYLE = `:host{display:block;color:#dfded0;font:13px/1.55 system-ui}*{box-sizing:border-box}section{padding:8px 0}.choices{display:grid;grid-template-columns:1fr 1fr;gap:8px}.choices button{display:flex;flex-direction:column;gap:5px}.choices small{font-size:11px;color:#bacec8;font-weight:normal}.selected{border-color:#e7c98e;background:#254743}h2{font:24px Georgia,serif;margin:0 0 8px}p{margin:8px 0;color:#bacec8}button,input,select,textarea{font:inherit;color:#eee4cd;background:#0a191d;border:1px solid #617974;border-radius:3px;padding:9px;max-width:100%}button{cursor:pointer;text-align:left;min-height:42px}button:hover{background:#254743}button:disabled{opacity:.5;cursor:wait}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:2px solid #e7c98e;outline-offset:2px}label{display:block;margin:12px 0 4px;font-size:12px}textarea{width:100%;min-height:68px}.row{display:flex;gap:6px;margin:7px 0;align-items:center}.row select{flex:1;min-width:0}.row button{flex:none}.examples{display:flex;flex-wrap:wrap;gap:7px;margin:13px 0}.examples button{font-size:12px;flex:1 1 120px}.primary{background:#d6bf8d;color:#0b2022;border-color:#e5ce9b;font-weight:600;width:100%;margin:10px 0}.primary:hover{background:#f3dcac}.caption{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#d6bf8d}.error{color:#f3b9a3}.recent{border-top:1px solid #46635b;margin-top:18px;padding-top:12px}.recent article{margin:12px 0;font-size:12px}.recent strong{color:#e5d5b4}summary{cursor:pointer;min-height:42px;padding:8px 0}.quiet{font-size:12px;color:#a9c0b9}`;
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
      this.generation++; this.busy=false; this.data = null; this.submission = null; this.pending = null; this.message = ''; this.steps = []; this.compose = false; this.intention = ''; this.intentionOpen = false; this.restored = false;
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
      const observed = recent => JSON.stringify((recent || []).map(r=>[r.event_id,(r.arrivals || []).map(a=>a.event_id)]));
      const priorObserved = observed(this.data?.recent);
      this.data = data;
      if (fromPoll && this.message && this.message === this.pollError) this.message = '';
      this.storageKey = `nw_arrangement:${data.participant}:${this.ctx.seed}:${this.ctx.node.name}`;
      if (!this.restored) {
        this.restored = true;
        try { const saved = JSON.parse(localStorage.getItem(this.storageKey)); if (saved) { this.submission=saved.payload || {steps:saved.preview.steps,expected:saved.preview.expected,version:saved.preview.version || 1,...(saved.preview.delegate ? {delegate:saved.preview.delegate} : {})}; this.pending=saved.intent; this.steps=this.submission.steps || []; this.intention=this.submission.intention || ''; this.message='An earlier attempt is awaiting its receipt. Recover it safely before acting again.'; } } catch (_) { /* no stored draft */ }
      }
      // Poll outcomes without replacing focused controls or an in-progress draft.
      if (!this.shadowRoot.activeElement && !this.busy) this.render();
      else this.renderRecent();
      pending = data.recent.reduce((n,r) => n+r.pending,0);
      // A node-triggered read already has fresh properties; only polling must
      // request them when it discovers a missed outcome notification.
      if (fromPoll && had != null && (had !== pending || priorObserved !== observed(data.recent))) this.ctx.changed?.();
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
  retry() { this.message=''; this.render(); return this.load(); }
  choose(choice) {
    if (this.busy || this.pending) return;
    if (this.compose) {
      this.steps=[...this.steps,{op:choice.op,amount:1}].slice(0,4); this.render(); return;
    }
    return this.commit({steps:[{op:choice.op,amount:1}],version:3});
  }
  async commit(submission) {
    if(this.busy || (!submission && !this.pending)) return;
    if(!this.pending && submission?.intention != null && !submission.intention.trim()) return;
    const generation=this.generation, ctx=this.ctx, storage=this.storageKey;
    const payload=this.pending ? this.submission : submission;
    this.busy=true; this.message='Setting your attempt in motion…'; this.render();
    try {
      if (!this.pending) await ctx.ensure?.(ctx.node.name);
      if(generation!==this.generation) return;
      const intent=this.pending || await globalThis.EnfoldedIntents.begin('intervention',ctx.seed,{node:ctx.node.name,...payload},ctx.key);
      if(generation!==this.generation) return;
      if(!intent) throw new Error('Enter with your invite to leave a lasting intervention.');
      const saved=JSON.stringify({intent,payload});
      try {
        localStorage.setItem(storage,saved);
        if(localStorage.getItem(storage)!==saved) throw new Error('storage unavailable');
      } catch (_) { throw new Error('Your browser could not keep a recovery copy. Nothing was submitted. Allow local storage, then try again.'); }
      this.pending=intent; this.submission=payload;
      const result=await this.request('/interventions/commit',{...payload,request_id:intent.request_id});
      globalThis.EnfoldedIntents.finish(intent);
      try { localStorage.removeItem(storage); } catch (_) { /* unavailable storage */ }
      if(generation!==this.generation) return;
      this.pending=null; this.submission=null; this.message=result.flavor || result.response;
      if(result.accepted) {
        this.steps=[]; this.compose=false; this.intention='';
        ctx.changed?.(result); await this.load();
      } else this.intentionOpen=true;
    } catch(error) {
      if(generation!==this.generation) return;
      if([400,409,403].includes(error.status)) {
        globalThis.EnfoldedIntents.finish(this.pending); this.pending=null; this.submission=null;
        try { localStorage.removeItem(storage); } catch (_) { /* unavailable storage */ }
      }
      this.message=this.pending && !error.status ? 'The reply was lost. Recover this attempt to learn whether it was accepted.' : error.message;
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
      const item=el('article'); item.append(el('strong',`${r.performer} · ${r.summary}`),el('p',`${display(r.origin)} · Attempt accepted. ${r.pending ? 'Consequences pending' : 'All consequences settled'}`));
      for(const a of r.arrivals) { const b=el('button',`Observed · ${display(a.node)}`); b.onclick=()=>this.ctx.jump?.(a.node); item.append(b,el('p',a.flavor || 'A consequence was observed.')); }
      root.append(item);
    }
    if(!this.data?.recent?.length) root.append(el('p','What you set in motion will remain here when you return.'));
  }
  render() {
    const root=this.shadowRoot; root.replaceChildren(el('style',STYLE));
    const section=el('section'); section.setAttribute('aria-label','Act here'); root.append(section);
    section.append(el('p',null,{className:'pending quiet'}));this.renderPending();
    if(!this.data) {
      section.append(el('p',this.message || 'Listening to this place…'));
      // A failed first read must not close the Act surface for the visit.
      if(this.message && this.ctx?.key) { const again=el('button','Listen again'); again.onclick=()=>this.retry(); section.append(again); }
      return;
    }
    const blocked=this.busy || !!this.pending;
    section.append(el('p','Choose an action to attempt it. Discover what follows.'));
    const combine=el('button',this.compose?'Leave combination':'Combine actions',{disabled:blocked});
    combine.onclick=()=>{this.compose=!this.compose;this.steps=[];this.render();};
    section.append(combine);
    const choices=el('div',null,{className:'choices'});
    for(const choice of this.data.choices) {
      const chosen=this.steps.some(s=>s.op===choice.op);
      const button=el('button',null,{disabled:blocked || (this.compose && this.steps.length>=4),className:chosen?'selected':''});
      button.setAttribute('aria-label',choice.label);
      button.append(el('strong',choice.label),el('small',choice.description));
      button.onclick=()=>this.choose(choice); choices.append(button);
    }
    section.append(choices);
    if(this.compose && this.steps.length) {
      section.append(el('p',this.steps.map(s=>this.data.operators[s.op]?.label || s.op).join(' → ')));
      const act=el('button','Attempt combination',{disabled:blocked,className:'primary'});
      act.onclick=()=>this.commit({steps:this.steps,version:3});
      const reset=el('button','Start over',{disabled:blocked});reset.onclick=()=>{this.steps=[];this.render();};
      section.append(act,reset);
    }
    const natural=el('details',null,{open:!!this.intentionOpen});natural.append(el('summary','Describe an intention'));
    natural.ontoggle=()=>this.intentionOpen=natural.open;
    const input=el('textarea',null,{value:this.intention,maxLength:600,placeholder:'What do you want to attempt here?'});input.setAttribute('aria-label','Your intention');input.disabled=blocked;input.oninput=()=>{this.intention=input.value;act.disabled=blocked || !this.intention.trim();};natural.append(input);
    const act=el('button','Act on this intention',{disabled:blocked || !this.intention?.trim()});act.onclick=()=>this.commit({intention:this.intention,version:3});
    natural.append(act,el('p','Submitting authorizes the attempt. Name actions in order, or describe your purpose with a connected model. If the action, target, scope or order is unclear, you can revise it here.',{className:'quiet'}));section.append(natural);
    if(this.pending) {
      const recover=el('button','Recover earlier attempt',{className:'primary',disabled:this.busy});
      recover.onclick=()=>this.commit();section.append(recover);
    }
    const status=el('p',this.message,{className:'status'});status.setAttribute('role','status');status.setAttribute('aria-live','polite');section.append(status);
    if(this.data.recent?.length) {
      const history=el('details');history.append(el('summary','Actions still echoing'),el('div',null,{className:'recent'}));section.append(history);this.renderRecent();
    }
  }
}
if(!customElements.get('enfolded-interventions')) customElements.define('enfolded-interventions',InterventionComposer);

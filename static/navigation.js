// A single passage surface in each client, also the map's keyboard alternative.
// The return trail is navigation convenience in this tab, never world history.
(() => {
  const conditions = node => globalThis.EnfoldedClient.passageBadges(node).filter(b=>b.key!=='locked').map(b=>b.label);
  const text = name => globalThis.EnfoldedClient.displayName(name || '');
  const el = (tag, content) => { const e=document.createElement(tag); if(content)e.textContent=content; return e; };
  const style = `:host{display:block;color:var(--text);font:1rem/1.5 system-ui}*{box-sizing:border-box;overflow-wrap:anywhere}nav{background:var(--surface);padding:16px;border-top:1px solid var(--line)}button,a,summary{font:inherit;color:var(--text);min-height:44px;padding:10px 12px;border-radius:var(--contour)}button,a{background:var(--raised);border:1px solid var(--line);text-decoration:none;cursor:pointer;text-align:left}button:hover,a:hover{background:var(--canvas)}:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.top,.children{display:flex;gap:8px;flex-wrap:wrap}.top{align-items:center}.children{margin-top:8px}.children button{flex:1 1 10rem;min-width:0}small,strong{display:block}strong{font:normal 1.125rem/1.3 Georgia;margin:4px 0}small,p{font-size:.875rem;color:var(--muted)}p{margin:12px 0 4px}summary{cursor:pointer;padding-left:0}details button{display:block;margin:8px 0;width:100%}`;
  class Navigation extends HTMLElement {
    constructor(){super();this.attachShadow({mode:'open'});this.trail=[];}
    set context(ctx){
      const signature=JSON.stringify([ctx.seed,ctx.node.name,ctx.parent?.name,ctx.node.children?.map(n=>[n.name,n.level,n.properties?.locked,conditions(n)]),ctx.wrap,ctx.status,!!ctx.deepen,ctx.view,ctx.href]);
      // Roster notices and refreshed callbacks must not replace a button between
      // pointerdown and click, or take focus from a player reading its label.
      if(signature===this.signature){this.ctx=ctx;return;}
      this.signature=signature;
      const changed=this.ctx?.node.name!==ctx.node.name;
      if(this.ctx?.seed!==ctx.seed)this.trail=[];
      if(changed && this.ctx && this.ctx.seed===ctx.seed) this.trail=[this.ctx.node,...this.trail.filter(n=>n.name!==this.ctx.node.name)].slice(0,8);
      const focus=this.shadowRoot.activeElement?.dataset.target;
      const wasOpen=this.shadowRoot.querySelector('details')?.open;
      this.ctx=ctx;this.render(wasOpen);
      if(focus && !changed) [...this.shadowRoot.querySelectorAll('button,a,summary')].find(e=>e.dataset.target===focus)?.focus();
      if(changed && focus) document.getElementById('node-name')?.focus();
    }
    render(open){
      const {node,parent,wrap,status,retry,deepen,view,href}=this.ctx;
      const root=this.shadowRoot;root.replaceChildren(el('style',style));
      const nav=el('nav');nav.setAttribute('aria-label','Explore places');root.append(nav);
      const button=(label,target,act)=>{const b=el('button',label);b.dataset.target=target;b.onclick=act;return b;};
      const row=el('div');row.className='top';nav.append(row);
      if(parent) row.append(button(`↑ ${text(parent.name)}`,parent.name,()=>this.ctx.jump(parent.name)));
      if(wrap){const b=button(wrap.direction==='inward'?'Descend into the whole ↓':'Ascend beyond ↑',wrap.target,()=>this.ctx.cross(wrap));b.id=wrap.direction==='inward'?'btn-wrap-down':'btn-wrap-up';row.append(b);}
      const link=el('a',view);link.href=href;link.dataset.target='view';row.append(link);
      if(status==='loading') {const p=el('p','Opening the passages within…');p.setAttribute('role','status');nav.append(p);}
      if(status==='error')nav.append(button('Retry passages','retry',retry));
      if(deepen){const b=button('Look within ↓','deepen',deepen);b.id='btn-deepen';nav.append(b);}
      if(node.children?.length){
        nav.append(el('p','Within this place'));
        const children=el('div');children.className='children';nav.append(children);
        for(const child of node.children){
          const b=button('',child.name,()=>this.ctx.jump(child.name));
          b.append(el('small',child.level+' ↘'),el('strong',text(child.name)));
          if(child.properties?.locked)b.append(el('small','Sealed · puzzle at the threshold'));
          const cues=conditions(child);
          if(cues.length)b.append(el('small',cues.join(' · ')));
          children.append(b);
        }
      }
      const prior=this.trail.filter(n=>n.name!==node.name && n.name!==parent?.name);
      if(prior.length){const details=el('details');details.open=!!open;const summary=el('summary','Return to a visited place');summary.dataset.target='trail';details.append(summary);
        for(const n of prior)details.append(button(`${n.level} · ${text(n.name)}`,n.name,()=>this.ctx.jump(n.name)));
        nav.append(details);
      }
    }
  }
  if(!customElements.get('enfolded-navigation'))customElements.define('enfolded-navigation',Navigation);
})();

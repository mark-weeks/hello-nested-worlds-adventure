// One test-world notice for both clients and their public entry pages.
// Acceptance belongs to the server's participant identity, never to a browser
// onboarding flag. Nothing here stores acceptance or infers a deployment mode.
(function () {
  'use strict';
  if (globalThis.EnfoldedParticipation) return;

  const UNREACHED = 'The test notice could not be reached. Try loading it again.';
  const INCOMPLETE = 'This test is not ready for visitors. Ask the person who invited you to finish its participation notice.';
  let pending;
  let rechecking;

  function key() {
    const supplied = new URLSearchParams(location.search).get('key');
    if (supplied) return supplied;
    try { return localStorage.getItem('nw_beta_key') || ''; }
    catch { return ''; }
  }

  async function request(body, anonymous = false, timeoutMs = 10000) {
    const credential = anonymous ? '' : key();
    const headers = credential ? { 'X-Beta-Key': credential } : {};
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      if (body) headers['Content-Type'] = 'application/json';
      const response = await fetch('/participation', {
        method: body ? 'POST' : 'GET', headers,
        ...(body ? { body: JSON.stringify(body) } : {}),
        cache: 'no-store', signal: controller.signal,
      });
      if (response.status === 403) return { refused: true };
      const data = await response.json();
      if (!response.ok) {
        // A changed revision is read again before offering fresh checkboxes.
        if (body && (response.status === 409 || response.status === 503)) return { changed: true };
        throw new Error(UNREACHED);
      }
      if (typeof data.required !== 'boolean' || (data.required && (
        typeof data.ready !== 'boolean' || !Array.isArray(data.paragraphs) ||
        data.paragraphs.some(line => typeof line !== 'string') ||
        typeof data.title !== 'string' || typeof data.accepted !== 'boolean' ||
        (data.ready && (typeof data.revision !== 'string' || !data.revision ||
          !Number.isInteger(data.minimum_age)))
      ))) throw new Error(UNREACHED);
      return data;
    } finally { clearTimeout(timeout); }
  }

  async function currentNotice(timeoutMs = 10000) {
    // Local position-only credentials are valid on an open development world,
    // but are not personal invitations. Read public mode metadata first so an
    // inactive test notice never causes an unrelated credential validation.
    const started = performance.now();
    const notice = await request(undefined, true, timeoutMs);
    if (!notice.required || !key()) return notice;
    const remaining = timeoutMs - (performance.now() - started);
    if (remaining <= 0) throw new Error(UNREACHED);
    return request(undefined, false, remaining);
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function noticeContents(container, notice) {
    container.replaceChildren();
    container.append(element('h2', notice.title, 'participation-title'));
    for (const line of notice.paragraphs) container.append(element('p', line));
    if (!notice.ready) container.append(element('p', INCOMPLETE, 'participation-status'));
  }

  async function decorate() {
    const slots = [...document.querySelectorAll('[data-participation-notice]')];
    if (!slots.length) return;
    try {
      const notice = await request(undefined, true);
      for (const slot of slots) {
        slot.hidden = !notice.required;
        if (notice.required) noticeContents(slot, notice);
      }
    } catch {
      for (const slot of slots) {
        slot.hidden = false;
        slot.replaceChildren(element('p', UNREACHED));
        const retry = element('button', 'Load the notice again');
        retry.type = 'button';
        retry.addEventListener('click', decorate);
        slot.append(retry);
      }
    }
  }

  function gate() {
    const overlay = element('section', '', 'participation-gate');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'participation-title');
    const card = element('div', '', 'participation-card');
    overlay.append(card);
    const siblings = [...document.body.children].map(node => [node, node.inert]);
    for (const [node] of siblings) node.inert = true;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.body.append(overlay);
    overlay.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const focusable = [...overlay.querySelectorAll('button,input,a[href]')].filter(node => !node.disabled);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });
    return {
      card,
      close() {
        overlay.remove();
        for (const [node, inert] of siblings) node.inert = inert;
        document.body.style.overflow = overflow;
      },
    };
  }

  async function enter(firstNotice) {
    let view;
    return new Promise(resolve => {
      const finish = (acceptedNew = false) => { view?.close(); resolve(acceptedNew); };
      const display = async () => {
        let notice;
        try {
          notice = firstNotice || await currentNotice();
          firstNotice = null;
        }
        catch {
          if (!view) view = gate();
          view.card.replaceChildren();
          const title = element('h1', 'Before you enter', 'participation-title');
          title.id = 'participation-title';
          view.card.append(title, element('p', UNREACHED, 'participation-status'));
          const retry = element('button', 'Load the notice again');
          retry.type = 'button';
          retry.addEventListener('click', () => { retry.disabled = true; display(); });
          view.card.append(retry);
          retry.focus();
          return;
        }
        // Missing or invalid invitations keep the clients' existing return
        // guidance. Their /world request still meets the server's invite gate.
        if (notice.refused || !notice.required || (notice.ready && notice.accepted) || !key()) {
          finish();
          return;
        }
        if (!view) view = gate();
        const { card } = view;
        noticeContents(card, notice);
        card.querySelector('h2').id = 'participation-title';
        if (!notice.ready) {
          const retry = element('button', 'Load the notice again');
          retry.type = 'button';
          retry.addEventListener('click', () => { retry.disabled = true; display(); });
          card.append(retry);
          retry.focus();
          return;
        }
        const form = element('form');
        const age = element('input');
        age.type = 'checkbox'; age.id = 'participation-age';
        const ageLabel = element('label', '', 'participation-choice');
        ageLabel.append(age, element('span', `I am at least ${notice.minimum_age} years old.`));
        const agree = element('input');
        agree.type = 'checkbox'; agree.id = 'participation-agree';
        const agreeLabel = element('label', '', 'participation-choice');
        agreeLabel.append(agree, element('span', 'I have read this notice and agree to take part in this temporary test.'));
        const status = element('p', '', 'participation-status');
        status.setAttribute('role', 'status');
        const submit = element('button', 'Agree and continue');
        submit.type = 'submit'; submit.disabled = true;
        const enable = () => { submit.disabled = !(age.checked && agree.checked); };
        age.addEventListener('change', enable);
        agree.addEventListener('change', enable);
        form.append(ageLabel, agreeLabel, element('p', 'You can leave this page without agreeing.'), status, submit);
        form.addEventListener('submit', async event => {
          event.preventDefault();
          if (!age.checked || !agree.checked || submit.disabled) return;
          submit.disabled = true;
          age.disabled = agree.disabled = true;
          status.textContent = 'Saving your choice…';
          try {
            const result = await request({ accepted: true, revision: notice.revision });
            if (result.refused) { finish(); return; }
            if (result.changed) { await display(); return; }
            if (result.accepted && result.revision === notice.revision) { finish(true); return; }
            throw new Error(UNREACHED);
          } catch {
            status.textContent = 'Your choice could not be saved. Try again.';
            age.disabled = agree.disabled = false;
            enable();
          }
        });
        card.append(form);
        age.focus();
      };
      display();
    });
  }

  globalThis.EnfoldedParticipation = {
    ensure() { return pending || (pending = enter()); },
    // A closed socket may mean a new test notice after a deployment, an
    // ordinary revoked key, or a network interruption.
    // Only a newly acknowledged notice reloads the view. No earlier request,
    // message or mutation is replayed; callers retain their normal reconnect
    // behavior when the notice is already accepted or the invite is refused.
    recheck() {
      if (rechecking) return rechecking;
      rechecking = (async () => {
        let notice;
        try { notice = await currentNotice(2000); }
        // During a restart there may be no server to answer yet. Keep the
        // clients' ordinary backoff; their next failed connection checks again.
        catch { return false; }
        if (notice && (notice.refused || !notice.required ||
            (notice.ready && notice.accepted) || !key())) return false;
        const acknowledged = await enter(notice);
        if (acknowledged) location.reload();
        return acknowledged;
      })().finally(() => { rechecking = null; });
      return rechecking;
    },
    decorate,
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorate, { once: true });
  else decorate();
})();

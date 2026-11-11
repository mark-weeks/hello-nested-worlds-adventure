// One test-world notice for both clients and their public entry pages.
// Acceptance belongs to the server's participant identity, never to a browser
// onboarding flag. Nothing here stores acceptance or infers a deployment mode.
(function () {
  'use strict';
  if (globalThis.EnfoldedParticipation) return;

  const UNREACHED = 'Participation information could not be reached. Try loading it again.';
  const INCOMPLETE = 'This test is not ready for visitors. Ask the person who invited you to finish its participation notice.';
  let pending;
  let rechecking;
  let testWorldSeen = false;
  let requiredReview = false;

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
          typeof data.agreement !== 'string' || !data.agreement.trim() ||
          !Number.isInteger(data.minimum_age)))
      ))) throw new Error(UNREACHED);
      if (data.required) testWorldSeen = true;
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

  const ordinaryCopy = new WeakMap();
  const temporaryText = {
    'register-intro': 'You have been invited to a temporary test world. Choose the name your words, solved puzzles and actions will be recorded under. Read the notice below before playing; this test world may be reset or removed.',
    'guide-intro': 'You are an explorer in a temporary test world. Your words, actions and solved puzzles become part of its shared history while the test exists. Its records follow the participation notice below; progress is not promised to persist.',
    'guide-puzzles': 'Puzzles compose the way the world does. Constellations complete when every system of a galaxy, or every room of a region, is resolved. Completion is recorded and credited in this test world. Co-op attempts pool, so travelers can light a constellation together. Lineage sigils use three marks from three enclosing scales; bonds ask for the atom puzzle in the lattice that holds it.',
    'guide-sealed': 'Some rooms are sealed until their lock is answered. The key is a truth about the place that holds the room, readable one scale up. Speak the key from the threshold and the way opens for everyone, until the world\'s slow entropy re-arms the room.',
    'guide-history-title': 'Reading this test world\'s history',
    'guide-history': 'This temporary world and its records follow the participation notice above. It may be reset or removed. While it exists, saved positions, conversations and marks can help you return. Open the Chronicle to read its recorded past, or Replay History (Wayback on the map) to inspect earlier state through today\'s art and sound. Looking leaves no new trace.',
  };
  function temporaryCopy(required) {
    for (const node of document.querySelectorAll('[data-participation-copy]')) {
      if (!ordinaryCopy.has(node)) ordinaryCopy.set(node, [...node.childNodes].map(child => child.cloneNode(true)));
      if (required) node.textContent = temporaryText[node.dataset.participationCopy];
      else node.replaceChildren(...ordinaryCopy.get(node).map(child => child.cloneNode(true)));
    }
  }

  async function decorate() {
    const slots = [...document.querySelectorAll('[data-participation-notice]')];
    if (!slots.length) return;
    try {
      const notice = await request(undefined, true);
      temporaryCopy(notice.required);
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
    // A native modal joins the top layer above an already-open Chronicle or
    // Ideas confirmation. Its previous modal remains open beneath this one.
    const overlay = element('dialog', '', 'participation-gate');
    overlay.setAttribute('aria-labelledby', 'participation-title');
    const card = element('div', '', 'participation-card');
    overlay.append(card);
    const previousFocus = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.body.append(overlay);
    overlay.showModal();
    overlay.addEventListener('cancel', event => { event.preventDefault(); event.stopPropagation(); });
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
        overlay.close();
        overlay.remove();
        document.body.style.overflow = overflow;
        if (previousFocus?.isConnected) previousFocus.focus();
      },
    };
  }

  async function enter(firstNotice, allowUnknownFailure = false) {
    let view;
    return new Promise(resolve => {
      const finish = (acceptedNew = false) => { view?.close(); resolve(acceptedNew); };
      const display = async () => {
        let notice;
        try {
          notice = firstNotice || await currentNotice(2000);
          firstNotice = null;
        }
        catch {
          // The server still gates data if an unknown world needs consent.
          if (allowUnknownFailure && !testWorldSeen) { finish(); return; }
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
        const agree = element('input');
        agree.type = 'checkbox'; agree.id = 'participation-agree';
        const agreeLabel = element('label', '', 'participation-choice');
        agreeLabel.append(agree, element('span', notice.agreement));
        const status = element('p', '', 'participation-status');
        status.setAttribute('role', 'status');
        const submit = element('button', 'Agree and continue');
        submit.type = 'submit'; submit.disabled = true;
        const enable = () => { submit.disabled = !agree.checked; };
        agree.addEventListener('change', enable);
        form.append(agreeLabel, element('p', 'You can leave this page without agreeing.'), status, submit);
        form.addEventListener('submit', async event => {
          event.preventDefault();
          if (!agree.checked || submit.disabled) return;
          submit.disabled = true;
          agree.disabled = true;
          status.textContent = 'Saving your choice…';
          try {
            const result = await request({ accepted: true, revision: notice.revision });
            if (result.refused) { finish(); return; }
            if (result.changed) { await display(); return; }
            if (result.accepted && result.revision === notice.revision) { finish(true); return; }
            throw new Error(UNREACHED);
          } catch {
            status.textContent = 'Your choice could not be saved. Try again.';
            agree.disabled = false;
            enable();
          }
        });
        card.append(form);
        agree.focus();
      };
      display();
    });
  }

  function review(force = false) {
    requiredReview ||= force;
    if (rechecking) return rechecking;
    rechecking = (async () => {
      let notice;
      try { notice = await currentNotice(2000); }
      catch {
        // During a restart there may be no server to answer. Actual consent
        // refusals, however, must still supply a deliberate recovery path.
        if (!requiredReview) return false;
      }
      if (notice?.refused || !key()) return false;
      if (notice && (!notice.required || (notice.ready && notice.accepted))) return true;
      return enter(notice);
    })().finally(() => { rechecking = null; requiredReview = false; });
    return rechecking;
  }

  globalThis.EnfoldedParticipation = {
    ensure() { return pending || (pending = enter(undefined, true)); },
    // A closed socket may mean a new test notice after a deployment, an
    // ordinary revoked key, or a network interruption.
    // Resume the current view and its dialogs after acknowledgement. The
    // caller reconnects normally; an earlier user action is never replayed.
    async recheck() { await review(); },
    async recover(response, data) {
      if (response.status !== 428 && response.status !== 503) return false;
      if (response.status === 503) {
        try { data ||= await response.clone().json(); } catch { return false; }
        if (!data.participation_required) return false;
      }
      testWorldSeen = true;
      return review(true);
    },
    decorate,
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorate, { once: true });
  else decorate();
})();

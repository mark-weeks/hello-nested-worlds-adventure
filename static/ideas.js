/* Shared board: text-only rendering, same-origin header credentials, no telemetry. */
(() => {
  const $ = id => document.getElementById(id);
  const element = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const storage = {
    get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, value); return true; } catch { return false; } },
    remove(key) { try { sessionStorage.removeItem(key); } catch { /* In-memory draft remains. */ } },
  };
  // Bind this tab to its opening credential. A replaced credential requires reload,
  // so a different account cannot accidentally submit this participant's draft.
  const credential = (() => { try { return localStorage.getItem('nw_beta_key') || ''; } catch { return ''; } })();
  const key = () => credential;
  let sort = 'recent', query = '', next = null, generation = 0, detailGeneration = 0;
  let owner = '', draftKey = '', requestId = crypto.randomUUID(), pending = null, selected = null;
  let relatedGeneration = 0, relatedTimer;
  function message(value, error = false) { $('message').textContent = value; $('message').className = error ? 'error' : ''; }
  async function api(path, body) {
    let response, data;
    try {
      response = await fetch(path, {method: body === undefined ? 'GET' : 'POST',
        headers: {'X-Beta-Key': key(), 'Content-Type': 'application/json'},
        ...(body === undefined ? {} : {body: JSON.stringify(body)}), cache: 'no-store', referrerPolicy: 'no-referrer'});
      data = await response.json();
    } catch {
      throw new Error('The connection did not finish. Please retry. Your draft is still here.');
    }
    if (!response.ok) {
      const error = new Error(data.error || 'Ideas could not complete that request. Please retry.');
      error.status = response.status;
      if (response.status === 403) {
        // Never leave previously fetched private content visible after a rejected credential.
        $('results').replaceChildren(); $('detail').hidden = true; $('board').hidden = true; $('notice').hidden = false;
      }
      throw error;
    }
    return data;
  }
  function draft() { return {title: $('title').value, description: $('description').value,
    public_credit: $('credit').checked, request_id: requestId}; }
  function saveDraft() {
    if (draftKey && !storage.set(draftKey, JSON.stringify({draft: draft(), pending})))
      $('draft-state').textContent = 'Browser storage is unavailable. Keep this tab open to retain your draft.';
  }
  function freezeDraft(frozen) {
    for (const id of ['title','description','credit']) $(id).disabled = frozen;
    $('submit-button').textContent = frozen ? 'Retry submission to confirm' : 'Submit idea';
  }
  function restoreDraft(viewer) {
    if (owner === viewer.id) return;
    owner = viewer.id; draftKey = 'nw_ideas_draft_' + owner;
    let saved;
    try { saved = JSON.parse(storage.get(draftKey)); } catch { saved = null; }
    requestId = saved?.draft?.request_id || crypto.randomUUID();
    for (const field of ['title','description']) $(field).value = typeof saved?.draft?.[field] === 'string' ? saved.draft[field] : '';
    $('credit').checked = saved?.draft?.public_credit === true;
    pending = saved?.pending || null;
    freezeDraft(!!pending);
    if (pending) $('draft-state').textContent = 'A submission may have arrived. Retry to confirm it before editing.';
  }
  function ideaLink(idea) {
    const link = element('a', idea.title);
    link.href = '/ideas?id=' + encodeURIComponent(idea.id);
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault(); openDetail(idea.id);
    });
    return link;
  }
  function supportLabel(idea) { return idea.supported ? 'Undo support' : 'Support idea'; }
  function card(idea) {
    const article = element('article', undefined, 'card');
    const heading = element('h3'); heading.append(ideaLink(idea));
    const meta = element('p', undefined, 'meta');
    meta.append(element('span', idea.status_label, 'badge'), element('span', `${idea.votes} support${idea.votes === 1 ? '' : 's'}`),
      element('span', idea.supported ? 'You support this' : 'Not yet supported by you'), element('span', 'By ' + idea.author));
    article.append(heading, meta); return article;
  }
  async function load(cursor = '') {
    const current = ++generation;
    if (!owner) message('Loading ideas…');
    $('results').setAttribute('aria-busy', 'true');
    $('result-status').textContent = 'Loading ideas…'; $('more').hidden = true; $('retry').hidden = true;
    try {
      const data = await api('/ideas/search', {sort, q: query, limit: 20, cursor});
      if (current !== generation) return;
      if (!owner) message('');
      restoreDraft(data.viewer);
      $('board').hidden = false; $('notice').hidden = true;
      $('attribution').textContent = `Your registered game name, ${data.viewer.name}, and this idea will be visible to active invited players. Voters remain private.`;
      $('results').replaceChildren(...data.ideas.map(card));
      $('result-status').textContent = data.ideas.length ? `${data.ideas.length} idea${data.ideas.length === 1 ? '' : 's'} on this page` : query ? 'No matching ideas. You can share a distinct report.' : sort === 'own' ? 'You have not shared an idea yet.' : 'No ideas yet. Share the first observation.';
      next = data.next_cursor; $('more').hidden = !next; $('first').hidden = !cursor;
      if (cursor) { $('browse-title').tabIndex = -1; $('browse-title').focus(); }
    } catch (error) {
      if (current !== generation) return;
      $('results').replaceChildren(); $('result-status').textContent = 'Ideas could not load.';
      message(error.message, true); $('retry').hidden = false;
    } finally { if (current === generation) $('results').setAttribute('aria-busy', 'false'); }
  }
  async function openDetail(id, focus = true) {
    const current = ++detailGeneration;
    selected = id;
    $('detail').hidden = false; $('detail').replaceChildren(element('p', 'Loading idea…'));
    history.replaceState(null, '', '/ideas?id=' + encodeURIComponent(id));
    try {
      const data = await api('/ideas/detail?id=' + encodeURIComponent(id));
      if (current !== detailGeneration) return;
      renderDetail(data.idea);
      if (focus) { $('detail-title').focus(); $('detail').scrollIntoView({block: 'start'}); }
    } catch (error) {
      if (current !== detailGeneration) return;
      $('detail').replaceChildren(element('p', error.message));
      const retry = element('button', 'Retry this idea'); retry.onclick = () => openDetail(id); $('detail').append(retry);
    }
  }
  function renderDetail(idea) {
    const panel = $('detail'); panel.replaceChildren(); panel.hidden = false;
    const close = element('button', 'Close idea'); close.onclick = () => {
      ++detailGeneration; selected = null; panel.hidden = true; history.replaceState(null, '', '/ideas'); $('search').focus();
    };
    const title = element('h2', idea.title); title.id = 'detail-title'; title.tabIndex = -1;
    panel.append(title, element('p', idea.status_label, 'badge'), element('p', 'By ' + idea.author, 'muted'), element('p', idea.description, 'copy'));
    const actions = element('div', undefined, 'actions');
    const count = element('span', `${idea.votes} support${idea.votes === 1 ? '' : 's'}`);
    const vote = element('button', supportLabel(idea)); vote.setAttribute('aria-pressed', String(idea.supported));
    vote.onclick = async () => {
      vote.disabled = true; const current = detailGeneration;
      try {
        const data = await api('/ideas/vote', {id: idea.id, supported: !idea.supported});
        if (current !== detailGeneration) return;
        Object.assign(idea, data.idea); count.textContent = `${idea.votes} support${idea.votes === 1 ? '' : 's'}`;
        vote.textContent = supportLabel(idea); vote.setAttribute('aria-pressed', String(idea.supported));
        message(idea.supported ? 'Your support is recorded.' : 'Your support was removed.'); await load();
      } catch (error) { message(error.message, true); } finally { vote.disabled = false; }
    };
    const permalink = element('a', 'Stable idea link'); permalink.href = '/ideas?id=' + encodeURIComponent(idea.id);
    actions.append(vote, count, permalink, close); panel.append(actions);
    if (idea.duplicate_id) { const duplicate = ideaLink({id: idea.duplicate_id, title: 'Follow the surviving idea'}); panel.append(duplicate, element('p', 'Support votes stay on their original idea; they are not transferred.', 'muted')); }
    if (idea.issue_url) {
      const issue = element('a', 'Follow the GitHub issue ↗'); issue.href = idea.issue_url; issue.target = '_blank'; issue.rel = 'noopener noreferrer'; panel.append(issue);
    }
    if (idea.availability) panel.append(element('p', 'Verified availability: ' + idea.availability, 'copy'));
    if (idea.decisions.length) {
      panel.append(element('h3', 'Maintainer decisions'));
      for (const decision of idea.decisions) panel.append(element('p', decision.explanation, 'copy decision'));
    } else panel.append(element('p', 'A maintainer has not recorded a decision yet.', 'muted'));
    if (idea.own) {
      const withdraw = element('button', 'Withdraw my idea');
      withdraw.onclick = () => { $('withdraw-error').textContent = ''; $('withdraw-dialog').showModal(); };
      panel.append(withdraw);
    }
  }
  $('cancel-withdraw').onclick = () => $('withdraw-dialog').close();
  $('confirm-withdraw').onclick = async () => {
    const id = selected; $('confirm-withdraw').disabled = true;
    try {
      await api('/ideas/withdraw', {id}); ++detailGeneration; selected = null;
      $('withdraw-dialog').close(); $('detail').hidden = true; history.replaceState(null, '', '/ideas');
      message('Your idea was withdrawn and its original text removed. Published issues may remain public.');
      await load(); $('search').focus();
    } catch (error) { $('withdraw-error').textContent = error.message; }
    finally { $('confirm-withdraw').disabled = false; }
  };
  for (const button of document.querySelectorAll('[data-sort]')) button.onclick = () => {
    sort = button.dataset.sort;
    for (const tab of document.querySelectorAll('[data-sort]')) tab.setAttribute('aria-pressed', String(tab === button));
    load();
  };
  $('search-form').onsubmit = event => { event.preventDefault(); query = $('search').value.trim(); load(); };
  $('more').onclick = () => load(next); $('first').onclick = () => load(); $('retry').onclick = () => load();
  for (const id of ['title','description','credit']) $(id).addEventListener('input', saveDraft);
  $('title').addEventListener('input', () => {
    clearTimeout(relatedTimer); const current = ++relatedGeneration;
    const q = $('title').value.trim(); $('related').replaceChildren();
    if (q.length < 3) return;
    relatedTimer = setTimeout(async () => {
      try {
        const data = await api('/ideas/search', {q, limit: 5});
        if (current !== relatedGeneration) return;
        $('related').append(element('p', data.ideas.length ? 'Related titles — your report can still be distinct:' : 'No related titles found.'));
        for (const idea of data.ideas) $('related').append(ideaLink(idea));
      } catch { if (current === relatedGeneration) $('related').textContent = 'Related ideas could not load. You can still submit.'; }
    }, 350);
  });
  $('idea-form').onsubmit = async event => {
    event.preventDefault();
    if (!pending && !$('idea-form').reportValidity()) return;
    if (!pending) {
      if (!$('title').value.trim() || !$('description').value.trim()) { message('Add a title and your experience before submitting.', true); (!$('title').value.trim() ? $('title') : $('description')).focus(); return; }
      pending = draft(); saveDraft();
    }
    freezeDraft(true); $('submit-button').disabled = true; message('Submitting your idea…');
    try {
      const data = await api('/ideas/submit', pending);
      pending = null; storage.remove(draftKey); requestId = crypto.randomUUID();
      $('idea-form').reset(); $('draft-state').textContent = ''; $('related').replaceChildren(); freezeDraft(false);
      message('Idea submitted. ');
      const link = element('a', 'Your stable idea link'); link.href = '/ideas?id=' + encodeURIComponent(data.id); $('message').append(link); link.focus();
      await load();
    } catch (error) {
      if (error.status && error.status < 500 && error.status !== 403) {
        pending = null; freezeDraft(false);
        if (error.status === 409) requestId = crypto.randomUUID();
      } else $('draft-state').textContent = 'Your submission may have arrived. Retry to confirm it before editing; the same retry cannot create a second idea.';
      saveDraft(); message(error.message, true);
    } finally { $('submit-button').disabled = false; }
  };
  const initial = new URLSearchParams(location.search).get('id');
  // Strip accidental credential query strings rather than retaining/copying them.
  history.replaceState(null, '', '/ideas' + (initial && /^[a-f0-9]{32}$/.test(initial) ? '?id=' + initial : ''));
  load().then(() => { if (initial && !$('board').hidden) openDetail(initial); });
})();

(() => {
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const key = localStorage.getItem('nw_beta_key') || '';
  const seed = params.get('seed') || '';
  let noteId = crypto.randomUUID();
  let profileLoaded = false;
  const status = text => { $('status').textContent = text; };
  async function api(path, body) {
    const response = await fetch(path, {method: body ? 'POST' : 'GET',
      headers: {'X-Beta-Key': key, 'Content-Type': 'application/json'},
      ...(body ? {body: JSON.stringify({...body, seed})} : {}), cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Please try again.');
    return data;
  }
  function link(node) {
    const a = document.createElement('a');
    a.textContent = node.replace(/-\d+$/, '');
    a.href = '/app?node=' + encodeURIComponent(node);
    return a;
  }
  async function load() {
    const data = await api('/journal/data?seed=' + encodeURIComponent(seed));
    $('journal').hidden = false;
    const profile = data.profile;
    if (!profileLoaded) {
      for (const id of ['bio', 'goals', 'avatar']) $(id).value = profile[id];
      $('published').checked = profile.published; profileLoaded = true;
    }
    $('home-label').textContent = profile.home ? 'Home bookmark: ' + profile.home.node.replace(/-\d+$/, '') : 'No home bookmark chosen.';
    $('profile-link').textContent = profile.published ? 'Published as ' + profile.name + '. Your notes remain private.' : 'Your profile is unpublished.';
    if (profile.published) {
      const share = document.createElement('a'); share.textContent = ' View and share your profile';
      share.href = '/journal?participant=' + encodeURIComponent(profile.id); $('profile-link').append(share);
    }
    $('notes').replaceChildren();
    for (const note of data.notes) {
      const card = document.createElement('article'); card.className = 'note';
      card.append(link(note.node));
      const text = document.createElement('p'); text.textContent = note.text; card.append(text);
      const edit = document.createElement('button'); edit.textContent = 'Edit note';
      edit.onclick = () => { noteId = note.id; $('place').value = note.node; $('note').value = note.text; $('note').focus(); };
      const remove = document.createElement('button'); remove.textContent = 'Delete note';
      remove.onclick = async () => { try { await api('/journal/note', {...note, text: ''}); await load(); status('Private note deleted.'); } catch (e) { status(e.message); } };
      card.append(edit, ' ', remove); $('notes').append(card);
    }
    if (!data.notes.length) $('notes').textContent = 'Your first question can begin here.';
    $('recap').replaceChildren();
    for (const change of data.recap) {
      const row = document.createElement('p'); row.append(link(change.node), ' — ' + change.text + ' ');
      const evidence = document.createElement('a'); evidence.textContent = 'Recorded event #' + change.event_id;
      evidence.href = '/app?node=' + encodeURIComponent(change.node); row.append(evidence); $('recap').append(row);
    }
    if (!data.recap.length) $('recap').textContent = 'No material changes recorded at your saved places or investigations yet.';
  }
  $('place').value = params.get('node') || localStorage.getItem('nw_last_node') || '';
  $('note-form').onsubmit = async event => {
    event.preventDefault(); const button = event.submitter; button.disabled = true;
    try { await api('/journal/note', {id: noteId, node: $('place').value, text: $('note').value});
      noteId = crypto.randomUUID(); $('note').value = ''; await load(); status('Private note saved.');
    } catch (e) { status(e.message); } finally { button.disabled = false; }
  };
  $('profile-form').onsubmit = async event => {
    event.preventDefault(); const button = event.submitter; button.disabled = true;
    try { await api('/profile/save', {bio: $('bio').value, goals: $('goals').value, avatar: $('avatar').value, published: $('published').checked});
      await load(); status('Profile saved.');
    } catch (e) { status(e.message); } finally { button.disabled = false; }
  };
  $('home').onclick = async () => {
    try { await api('/profile/home', {node: $('place').value}); await load(); status('Private home bookmark saved.'); }
    catch (e) { status(e.message); }
  };
  $('clear-home').onclick = async () => {
    try { await api('/profile/home', {node: ''}); await load(); status('Home bookmark removed.'); }
    catch (e) { status(e.message); }
  };
  async function publicProfile() {
    const data = await api('/profile?participant=' + encodeURIComponent(params.get('participant')));
    const p = data.profile;
    document.querySelector('h1').textContent = p.name;
    document.querySelector('h1 + p').textContent = 'A traveler in the shared world.';
    const section = document.createElement('section');
    if (p.published) {
      const avatar = document.createElement('p');
      avatar.textContent = ({lantern: '🏮', leaf: '🍃', star: '✦', river: '≋'})[p.avatar] + ' ' + p.avatar;
      avatar.setAttribute('aria-label', p.avatar + ' avatar'); section.append(avatar);
      for (const [title, value] of [['Bio', p.bio], ['Goals', p.goals]]) {
        const heading = document.createElement('h2'); heading.textContent = title;
        const text = document.createElement('p'); text.textContent = value; section.append(heading, text);
      }
      status('Published profile');
    } else status('This traveler has not published a profile.');
    document.body.append(section);
  }
  (params.has('participant') ? publicProfile() : load().then(() => status('Your journal is private.')))
    .catch(e => status(e.message));
})();

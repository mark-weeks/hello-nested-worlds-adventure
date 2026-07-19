// Registration page logic. Lives in its own file — never inline — because
// every HTML page is served under Content-Security-Policy `script-src 'self'`
// (no `unsafe-inline`, no nonce), which blocks inline <script> blocks
// entirely. This shipped inline once and the whole self-service invite flow
// silently did nothing in CSP-enforcing browsers (2026-07-19 ensemble
// evaluation); the Playwright smoke test now drives this page for real.
var invite = new URLSearchParams(location.search).get('invite') || '';
if (!invite) {
  document.getElementById('register').classList.add('hidden');
  document.getElementById('no-invite').classList.remove('hidden');
}
document.getElementById('form').addEventListener('submit', function (e) {
  e.preventDefault();
  var name = document.getElementById('name').value.trim();
  var errEl = document.getElementById('error');
  var btn = document.getElementById('go');
  errEl.textContent = '';
  if (!name) { errEl.textContent = 'A name is required.'; return; }
  btn.disabled = true;
  fetch('/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invite: invite, name: name }),
  }).then(function (res) {
    return res.json().then(function (data) {
      if (res.ok && data.url) {
        // The explorer reads ?key= from its own URL and stashes it;
        // from here on this player is a named, keyed account.
        location.href = data.url;
      } else {
        // 409 name-taken / 403 bad-or-spent invite / 400 validation —
        // the server's message is already player-facing ("…the name is
        // taken — choose another"). The token survives a 409, so the
        // player just tries a different name.
        errEl.textContent = (data && data.error) ||
          'Something went wrong — try again.';
        btn.disabled = false;
      }
    });
  }).catch(function () {
    errEl.textContent = 'Could not reach the worlds — try again.';
    btn.disabled = false;
  });
});

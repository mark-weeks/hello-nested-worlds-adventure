// Retry identity survives navigation, reload, and invite rotation. No world event
// is emitted for these local receipts; the server remains the commit authority.
(() => {
  const memory = new Map();
  async function begin(operation, seed, payload, credential) {
    if (!credential) return null; // Legacy/keyless local play retains its contract.
    const response = await fetch('/me', {headers: {'X-Beta-Key': credential}, cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Your invite could not be read.');
    const bytes = new TextEncoder().encode(JSON.stringify(payload));
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
      .map(value => value.toString(16).padStart(2, '0')).join('');
    const key = `nw_intent:${data.participant.id}:${seed}:${operation}:${digest}`;
    let id = memory.get(key);
    try { id = localStorage.getItem(key) || id; } catch (_) { /* Memory-only fallback. */ }
    if (!id) id = crypto.randomUUID();
    memory.set(key, id);
    try { localStorage.setItem(key, id); } catch (_) { /* Memory-only fallback. */ }
    return {key, request_id: id};
  }
  function finish(intent) {
    if (!intent) return;
    if (memory.get(intent.key) === intent.request_id) memory.delete(intent.key);
    try {
      if (localStorage.getItem(intent.key) === intent.request_id) localStorage.removeItem(intent.key);
    } catch (_) { /* Memory-only fallback. */ }
  }
  globalThis.EnfoldedIntents = Object.freeze({begin, finish});
})();

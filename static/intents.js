// Retry identity survives navigation, reload, and invite rotation. No world event
// is emitted for these local receipts; the server remains the commit authority.
(() => {
  const memory = new Map();
  async function digest(value) {
    const bytes = new TextEncoder().encode(value);
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
      .map(value => value.toString(16).padStart(2, '0')).join('');
  }
  async function participant(credential) {
    const cacheKey = `nw_participant:${await digest(credential)}`;
    let owner = memory.get(cacheKey);
    try { owner = localStorage.getItem(cacheKey) || owner; } catch (_) { /* Memory-only fallback. */ }
    if (/^[a-f0-9]{32}$/.test(owner || '')) return owner;
    const response = await fetch('/me', {headers: {'X-Beta-Key': credential}, cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Your invite could not be read.');
    owner = data.participant.id;
    memory.set(cacheKey, owner);
    try { localStorage.setItem(cacheKey, owner); } catch (_) { /* Memory-only fallback. */ }
    return owner;
  }
  async function begin(operation, seed, payload, credential) {
    if (!credential) return null; // Legacy/keyless local play retains its contract.
    // Cache only the stable namespace. Every submitted action is still
    // authenticated by the server; this never authorizes a revoked credential.
    const owner = await participant(credential);
    const fingerprint = await digest(JSON.stringify(payload));
    const key = `nw_intent:${owner}:${seed}:${operation}:${fingerprint}`;
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

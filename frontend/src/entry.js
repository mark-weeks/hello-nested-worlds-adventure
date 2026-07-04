// Entry-point resolution for the browser clients.
//
// Traversal is non-linear and there is no "start at the root": a first-time
// player is dropped in at a node somewhere in the middle of the world — one
// with places to go both up and down — and a returning player resumes wherever
// they left off. Both are deterministic. The drop-in is seeded from the
// player's name, so a given player has a stable arrival point; resume is keyed
// on the last node they stood on. Pure functions, so they're unit-testable.

// The path root → node (inclusive) as an array, or null if `name` isn't found.
// The React client uses this array directly as its navigation stack, so the
// "back" button walks the real ancestry.
export function findPath(root, name) {
  if (!root) return null;
  if (root.name === name) return [root];
  for (const child of root.children || []) {
    const sub = findPath(child, name);
    if (sub) return [root, ...sub];
  }
  return null;
}

function _hash(str) {
  // Deterministic 32-bit FNV-1a — same value in every browser and in tests.
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Candidate nodes to drop a first-time player into: those with both a parent
// (not the root) AND children, so there's somewhere to go in either direction.
// Falls back to any non-root node, then to the root, for shallow worlds.
function _dropInCandidates(root) {
  const mids = [];
  const nonRoot = [];
  (function walk(node, depth) {
    if (depth > 0) {
      nonRoot.push(node);
      if (node.children && node.children.length) mids.push(node);
    }
    for (const c of node.children || []) walk(c, depth + 1);
  })(root, 0);
  return mids.length ? mids : (nonRoot.length ? nonRoot : [root]);
}

// A stable drop-in node for `key` (the player's name).
export function dropInNode(root, key) {
  const pool = _dropInCandidates(root);
  return pool[_hash(key || "anon") % pool.length];
}

// The path (root → entry node) the client should open on: resume the saved node
// if it still exists in this world, otherwise a deterministic first-time
// drop-in. Never returns null — worst case, the root alone.
export function entryPath(root, savedNodeName, playerKey) {
  if (savedNodeName) {
    const resumed = findPath(root, savedNodeName);
    if (resumed) return resumed;
  }
  const target = dropInNode(root, playerKey);
  return findPath(root, target.name) || [root];
}

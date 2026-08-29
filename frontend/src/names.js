// Display names — one canonical rule from static/clientlogic.js: show the
// readable phrase, keep the address (the path-digit suffix) one gesture
// away. Canonical full names remain the identity everywhere data is keyed.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export function displayName(name) {
  return shared.displayName(name);
}

export function nodeAddress(name) {
  return shared.nodeAddress(name);
}

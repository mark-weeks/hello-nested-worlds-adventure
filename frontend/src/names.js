// Names, addresses and keys: one canonical rule from static/clientlogic.js.
// A place's name is shown as it reads. Its address and its identity key are
// fields the server sends with the node; neither is worked out of a name.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export function displayName(name) {
  return shared.displayName(name);
}

export function nodeAddress(node) {
  return shared.nodeAddress(node);
}

export function nodeKey(node) {
  return shared.nodeKey(node);
}

export function causalFeedLine(kind, node, strength) {
  return shared.causalFeedLine(kind, node, strength);
}

export function observationRow(event) {
  return shared.observationRow(event);
}

// The wrap passage (ADR-008) — one canonical affordance rule for both
// browser clients, from static/clientlogic.js.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export function wrapAffordance(node, wrapInfo) {
  return shared.wrapAffordance(node, wrapInfo);
}

export function firstWrapCrossing(direction, storage) {
  return shared.firstWrapCrossing(direction, storage);
}

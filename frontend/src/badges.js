// Passage affordance rules shared with the no-build explorer.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export const BADGE_RULES = shared.BADGE_RULES;

export function passageBadges(node) {
  return shared.passageBadges(node);
}

export function nodeMark(node) {
  return shared.nodeMark(node);
}

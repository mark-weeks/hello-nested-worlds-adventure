// Passage affordances: which of a child node's traits are worth signaling
// BEFORE the player commits to entering it. This is what turns "undifferentiated
// clicking" into discovery — danger to brave, damage to witness, pressure
// marking where the world has been busy.
//
// Ubiquitous traits are deliberately NOT badged: every node has a puzzle, so
// a puzzle badge would say nothing. An affordance that is always on is no
// affordance at all.

export const BADGE_RULES = [
  { key: "danger",     color: 0xf05a5a, css: "#f05a5a" },
  { key: "corrupted",  color: 0xc88af0, css: "#c88af0" },
  { key: "disturbed",  color: 0xff8a4a, css: "#ff8a4a" },
  { key: "stabilized", color: 0x4af0c8, css: "#4af0c8" },
  { key: "pressure",   color: 0xa078ff, css: "#a078ff" },
  { key: "locked",     color: 0x8a93b0, css: "#8a93b0" },
];

const _COLORS = Object.fromEntries(BADGE_RULES.map(r => [r.key, r]));

export function passageBadges(node) {
  const p = (node && node.properties) || {};
  const out = [];
  const push = (key, label) =>
    out.push({ key, label, color: _COLORS[key].color, css: _COLORS[key].css });

  if (typeof p.danger_level === "number" && p.danger_level >= 7) {
    push("danger", `danger ${p.danger_level}`);
  }
  if (p.condition === "corrupted") push("corrupted", "corrupted");
  if (p.disturbed) push("disturbed", "disturbed");
  if (p.stabilized) push("stabilized", "stabilized");
  if ((node && node.ripple_score) >= 0.3) push("pressure", "≈ pressure");
  if (p.locked) push("locked", "locked");
  return out;
}

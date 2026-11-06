// What the app shows before the scene, and the shared rule for a world read
// that did not open (static/clientlogic.js, also used by the D3 explorer).
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;
export const openWorld = shared.openWorld;
export const SPEAK_UNREACHED_LINE = shared.SPEAK_UNREACHED_LINE;

// One of "gate", "intro", "name", "retry", "loading" or "scene".
//
// A refusal from the invite gate comes before onboarding. A browser without
// a live invitation cannot enter under any name it chooses, and the
// introduction is still unseen when the player opens the invite link. Any
// other failure waits behind onboarding like the loading shell does. The
// loading shell stays for a read in flight. A failed reload with a place
// already in hand keeps the scene.
export function arrivalScreen({ loading, hasNode, unopened, introSeen, named }) {
  const settled = !loading && !hasNode && unopened ? unopened : null;
  if (settled && settled.kind !== "retry") return "gate";
  if (!introSeen) return "intro";
  if (!named) return "name";
  if (settled) return "retry";
  if (loading || !hasNode) return "loading";
  return "scene";
}

// What the app shows before the scene, and the shared rule for a world read
// that did not open (static/clientlogic.js, also used by the D3 explorer).
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;
export const openWorld = shared.openWorld;
export const WORLD_UNREACHED_LINE = shared.WORLD_UNREACHED_LINE;

// One of "gate", "intro", "name", "retry", "loading" or "scene".
//
// A refusal from the invite gate comes before onboarding. A browser without
// a live invitation cannot enter under any name it chooses, and the
// introduction is still unseen when the player opens the invite link. So a
// browser that holds no key waits on the loading shell for the gate's answer
// before it is shown the introduction or asked for a name, and a read that
// fails without that answer (a 502 during a deploy, a dropped connection)
// shows the retry line there too, since asking again may still meet the
// gate. A browser with a key reads the introduction while its world loads,
// and any other failure waits behind its onboarding like the loading shell
// does. The loading shell stays for a read in flight. A failed reload with a
// place already in hand keeps the scene.
export function arrivalScreen({ loading, hasNode, unopened, introSeen, named, hasKey }) {
  const settled = !loading && !hasNode && unopened ? unopened : null;
  if (settled && settled.kind !== "retry") return "gate";
  if (!hasKey && !hasNode) return settled ? "retry" : "loading";
  if (!introSeen) return "intro";
  if (!named) return "name";
  if (settled) return "retry";
  if (loading || !hasNode) return "loading";
  return "scene";
}

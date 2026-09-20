// Module shim for the no-build D3 explorer: exposes the shared per-node
// generative art module as window.NodeArt. ES modules load deferred, so the
// explorer's *initial* node selection can run before this executes — the
// ready event lets it redraw the sigil the moment the art is available.
import * as NodeArt from "/nodeart.js";
import * as NodeSound from "/score.js";
window.NodeArt = NodeArt;
window.NodeSound = NodeSound;
window.dispatchEvent(new Event("nodeart-ready"));

import { startSensory } from "/sensory.js";
import "/interventions.js";
window.startSensory = startSensory;
window.dispatchEvent(new Event("senses-ready"));

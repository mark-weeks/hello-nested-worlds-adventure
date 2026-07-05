// Module shim for the no-build D3 explorer: exposes the shared per-node
// generative art module as window.NodeArt. ES modules load deferred, so the
// explorer's *initial* node selection can run before this executes — the
// ready event lets it redraw the sigil the moment the art is available.
import * as NodeArt from "/nodeart.js";
window.NodeArt = NodeArt;
window.dispatchEvent(new Event("nodeart-ready"));

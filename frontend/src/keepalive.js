// One keepalive implementation for both browser clients. The no-build
// explorer calls EnfoldedClient.createSocketKeepalive directly.
import "../../static/clientlogic.js";

export const KEEPALIVE_INTERVAL_MS = globalThis.EnfoldedClient.KEEPALIVE_INTERVAL_MS;
export const createSocketKeepalive = globalThis.EnfoldedClient.createSocketKeepalive;

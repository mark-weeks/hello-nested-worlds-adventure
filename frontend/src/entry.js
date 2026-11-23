// The no-build explorer and Vite app consume one canonical implementation.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export function findPath(root, name) {
  return shared.findPath(root, name);
}

export function findNodeByName(root, name) {
  return shared.findNodeByName(root, name);
}

export function dropInNode(root, key) {
  return shared.dropInNode(root, key);
}

export function entryPath(root, savedNodeName, playerKey) {
  return shared.entryPath(root, savedNodeName, playerKey);
}

export function resumeDepth(savedDepth, savedAddress, minDepth, maxDepth) {
  return shared.resumeDepth(savedDepth, savedAddress, minDepth, maxDepth);
}

// A place known only by its name: `{ status: "resolved", address }`,
// `{ status: "missing" }` or `{ status: "retry" }` (static/clientlogic.js).
export function lookupNodeAddress(read, url) {
  return shared.lookupNodeAddress(read, url);
}

export function findNodeAddress(read, url, options) {
  return shared.findNodeAddress(read, url, options);
}

export function destinationAddress(name, knownAddress, find) {
  return shared.destinationAddress(name, knownAddress, find);
}

export function placeUnreachedLine(name) {
  return shared.placeUnreachedLine(name);
}

export function rememberAddress(storage, name, address) {
  return shared.rememberAddress(storage, name, address);
}

export function savedAddress(storage) {
  return shared.savedAddress(storage);
}

export function addressDepth(address) {
  return shared.addressDepth(address);
}

export function addressPath(root, address) {
  return shared.addressPath(root, address);
}

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

export function readNodeAddress(read, url) {
  return shared.readNodeAddress(read, url);
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

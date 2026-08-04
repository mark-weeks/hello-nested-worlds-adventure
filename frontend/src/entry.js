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

export function resumeDepth(savedDepth, savedNodeName, minDepth, maxDepth) {
  return shared.resumeDepth(savedDepth, savedNodeName, minDepth, maxDepth);
}

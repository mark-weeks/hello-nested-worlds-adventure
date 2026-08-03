// Chronicle/history narration shared with the no-build explorer.
import "../../static/clientlogic.js";

const shared = globalThis.EnfoldedClient;

export function mutationLine(mutation) {
  return shared.mutationLine(mutation);
}

export function describeMutation(mutation) {
  return shared.describeMutation(mutation);
}

export function describeChronicleEntry(mutation) {
  return shared.describeChronicleEntry(mutation);
}

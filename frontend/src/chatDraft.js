// One chat-draft rule for both browser clients. The no-build explorer calls
// EnfoldedClient.createChatDraft and restoreChatInput directly.
import "../../static/clientlogic.js";

export const createChatDraft = globalThis.EnfoldedClient.createChatDraft;
export const restoreChatInput = globalThis.EnfoldedClient.restoreChatInput;

// /app only: the chat input lives in TextPanel, which unmounts while the
// loading shell shows (a jump toward a traveler below the fetched horizon).
// The socket stays open, so a held or declined line can come back then. It
// is kept for the input that mounts next, instead of being dropped.
export function createChatRestore() {
  let fill = null;
  let held = null;
  return {
    // A line from createChatDraft().declined(); null is ignored.
    deliver(line) {
      if (!line) return;
      if (fill) fill(line);
      else held = line;
    },
    // Register the mounted input's refill; returns the cleanup.
    attach(next) {
      fill = next;
      if (held !== null) {
        const line = held;
        held = null;
        next(line);
      }
      return () => { if (fill === next) fill = null; };
    },
  };
}

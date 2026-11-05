// One chat-draft rule for both browser clients. The no-build explorer calls
// EnfoldedClient.createChatDraft and restoreChatInput directly.
import "../../static/clientlogic.js";

export const createChatDraft = globalThis.EnfoldedClient.createChatDraft;
export const restoreChatInput = globalThis.EnfoldedClient.restoreChatInput;

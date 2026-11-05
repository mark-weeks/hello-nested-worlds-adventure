// A chat line the moderation screen holds or declines reached nobody. Both
// clients give the player's own words back to the chat input so they can be
// resent or revised, through one rule in static/clientlogic.js. These tests
// drive that rule the way both clients do: send a line (input cleared, frame
// carries a ref), receive the server's reply through the real dispatcher,
// refill the input. Browser coverage of both clients is in
// e2e/chat-restore.spec.js.
import { beforeEach, describe, expect, it } from "vitest";
import { createChatDraft, restoreChatInput } from "../chatDraft.js";
import { dispatchMessage } from "../dispatch.js";

// The authored lines from server/moderation.py: a hold and a decline.
const HOLD_LINE = "The worlds hold those words for now. They are not shared. "
  + "Say it another way, or try again later.";
const DECLINE_LINE = "The worlds decline to carry those words. Say it another way.";

// A chat input wired as both clients wire it.
function chatClient() {
  const draft = createChatDraft();
  const client = { input: "", frames: [], feed: [] };
  const handlers = {
    onChatDeclined(msg) {
      client.feed.push(`✕ ${msg.text}`);
      const line = draft.declined(msg);
      client.input = restoreChatInput(client.input, line);
    },
  };
  client.type = (text) => { client.input = text; };
  client.send = () => {
    const text = client.input.trim();
    const frame = { type: "chat", text, ref: draft.sent(text) };
    client.frames.push(frame);
    client.input = "";
    return frame;
  };
  client.receive = (msg) => dispatchMessage(msg, handlers);
  return client;
}

describe("a held or declined chat line", () => {
  let client;
  beforeEach(() => { client = chatClient(); });

  for (const [verdict, line] of [["held", HOLD_LINE], ["declined", DECLINE_LINE]]) {
    it(`comes back to the empty input when it is ${verdict}, ready to resend`, () => {
      client.type("  meet me at the third gate  ");
      const frame = client.send();
      expect(frame.text).toBe("meet me at the third gate");
      expect(client.input).toBe("");

      client.receive({ type: "chat_declined", text: line, ref: frame.ref });

      expect(client.input).toBe("meet me at the third gate");
      // The world's authored line is still what the player reads.
      expect(client.feed).toEqual([`✕ ${line}`]);
      // Resending is an ordinary send with its own ref.
      const again = client.send();
      expect(again.text).toBe("meet me at the third gate");
      expect(again.ref).not.toBe(frame.ref);
    });
  }

  it("never replaces what the player has typed since sending", () => {
    client.type("meet me at the third gate");
    const frame = client.send();
    client.type("never mind, the second");

    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: frame.ref });

    expect(client.input).toBe("never mind, the second");
    expect(client.feed).toEqual([`✕ ${HOLD_LINE}`]);
  });

  it("treats whitespace typed since sending as the player's text", () => {
    client.type("meet me at the third gate");
    const frame = client.send();
    client.type(" ");
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: frame.ref });
    expect(client.input).toBe(" ");
  });

  it("comes back at most once, even after the player clears the input", () => {
    client.type("meet me at the third gate");
    const frame = client.send();
    client.type("x");
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: frame.ref });
    client.type("");
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: frame.ref });
    expect(client.input).toBe("");
  });

  it("is restored only when it is the player's most recent line", () => {
    client.type("first line");
    const first = client.send();
    client.type("second line");
    const second = client.send();

    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: first.ref });
    expect(client.input).toBe("");

    client.receive({ type: "chat_declined", text: DECLINE_LINE, ref: second.ref });
    expect(client.input).toBe("second line");
  });

  it("restores nothing for a reply without the frame's ref", () => {
    client.type("meet me at the third gate");
    const frame = client.send();
    client.receive({ type: "chat_declined", text: HOLD_LINE });
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: "c999" });
    expect(client.input).toBe("");
    // The real reply still restores after those strays.
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: frame.ref });
    expect(client.input).toBe("meet me at the third gate");
  });

  it("restores nothing when no line was sent", () => {
    client.receive({ type: "chat_declined", text: HOLD_LINE, ref: "c1" });
    expect(client.input).toBe("");
    expect(client.feed).toEqual([`✕ ${HOLD_LINE}`]);
  });
});

describe("chat refs", () => {
  it("are distinct short strings the server echoes", () => {
    const draft = createChatDraft();
    const refs = Array.from({ length: 50 }, (_, i) => draft.sent(`line ${i}`));
    expect(new Set(refs).size).toBe(refs.length);
    for (const ref of refs) {
      expect(typeof ref).toBe("string");
      // server/websocket.py echoes a ref of 1 to 64 characters.
      expect(ref.length).toBeGreaterThan(0);
      expect(ref.length).toBeLessThanOrEqual(64);
    }
  });
});

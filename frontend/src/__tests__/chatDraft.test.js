// A chat line the moderation screen holds or declines reached nobody. Both
// clients give the player's own words back to the chat input so they can be
// resent or revised, through one rule in static/clientlogic.js. These tests
// drive that rule the way both clients do: send a line (input cleared, frame
// carries a ref), receive the server's reply through the real dispatcher,
// refill the input. Browser coverage of both clients is in
// e2e/chat-restore.spec.js.
import { beforeEach, describe, expect, it } from "vitest";
import { createChatDraft, createChatRestore, restoreChatInput } from "../chatDraft.js";
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

// /app's TextPanel unmounts while the loading shell shows (a jump toward a
// traveler below the fetched horizon); the socket does not. A line that
// comes back then waits for the input that mounts next.
describe("a line that comes back while the /app input is unmounted", () => {
  function mountedInput(restore, initial = "") {
    const input = { value: initial };
    input.detach = restore.attach(line => { input.value = restoreChatInput(input.value, line); });
    return input;
  }

  it("fills the input at once while it is mounted", () => {
    const restore = createChatRestore();
    const input = mountedInput(restore);
    restore.deliver("meet me at the third gate");
    expect(input.value).toBe("meet me at the third gate");
  });

  it("waits for the next input when it arrives during the loading shell", () => {
    const draft = createChatDraft();
    const restore = createChatRestore();
    const before = mountedInput(restore);
    const ref = draft.sent("meet me at the third gate");
    before.detach();                       // the loading shell replaces the panel

    restore.deliver(draft.declined({ type: "chat_declined", text: HOLD_LINE, ref }));
    expect(before.value).toBe("");          // the unmounted input is not written

    const after = mountedInput(restore);    // the panel mounts again
    expect(after.value).toBe("meet me at the third gate");
    // Given back once: a later mount does not receive it again.
    after.detach();
    expect(mountedInput(restore).value).toBe("");
  });

  it("fills once across StrictMode's attach, detach, attach of one input", () => {
    // StrictMode re-runs the effect on the same component and state.
    const restore = createChatRestore();
    restore.deliver("meet me at the third gate");
    const input = { value: "" };
    let fills = 0;
    const fill = line => { fills += 1; input.value = restoreChatInput(input.value, line); };
    restore.attach(fill)();
    restore.attach(fill);
    expect(fills).toBe(1);
    expect(input.value).toBe("meet me at the third gate");
    // Still attached: the next line arrives at once and keeps what is there.
    restore.deliver("second line");
    expect(fills).toBe(2);
    expect(input.value).toBe("meet me at the third gate");
  });

  it("ignores a verdict that returns no line, and a stale detach", () => {
    const restore = createChatRestore();
    const old = mountedInput(restore);
    const current = mountedInput(restore);
    old.detach();                          // must not unhook the newer input
    restore.deliver(null);
    restore.deliver("meet me at the third gate");
    expect(current.value).toBe("meet me at the third gate");
  });
});

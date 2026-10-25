// Idle players were dropped because the server closes a socket that receives
// nothing for 60s, and neither browser client sent the application ping that
// handler already answers. These tests own the timer: one interval, replaced
// on reconnect, cleared on the effect cleanup (unmount).
import { afterEach, describe, expect, it, vi } from "vitest";
import { createSocketKeepalive, KEEPALIVE_INTERVAL_MS } from "../keepalive.js";
import { attachWorldSocket } from "../ws.js";

const OPEN = typeof WebSocket === "function" ? WebSocket.OPEN : 1;
const PING = JSON.stringify({ type: "ping" });

function openSocket() {
  return { readyState: OPEN, sent: [] };
}

describe("socket keepalive", () => {
  afterEach(() => {
    vi.useRealTimers();
    delete globalThis.document;
  });

  it("ticks well under the server's 60s idle deadline", () => {
    expect(KEEPALIVE_INTERVAL_MS).toBe(20_000);
    expect(KEEPALIVE_INTERVAL_MS).toBeLessThan(60_000 / 2);
  });

  it("sends one application ping per interval while the socket is open", () => {
    vi.useFakeTimers();
    const socket = openSocket();
    const keepalive = createSocketKeepalive((s) => s.sent.push(PING));
    keepalive.arm(socket);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS - 1);
    expect(socket.sent).toEqual([]);
    vi.advanceTimersByTime(1);
    expect(socket.sent).toEqual([PING]);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(socket.sent).toEqual([PING, PING]);
    expect(vi.getTimerCount()).toBe(1);
    keepalive.stop();
  });

  it("does not send before the socket is open, and a failed write does not drop the timer", () => {
    vi.useFakeTimers();
    const socket = { readyState: 0, sent: [] };
    let calls = 0;
    const keepalive = createSocketKeepalive(() => {
      calls += 1;
      if (calls === 1) throw new Error("socket closing");
      socket.sent.push(PING);
    });
    keepalive.arm(socket);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(calls).toBe(0);
    socket.readyState = OPEN;
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(calls).toBe(1);
    expect(socket.sent).toEqual([]);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(socket.sent).toEqual([PING]);
    expect(vi.getTimerCount()).toBe(1);
    keepalive.stop();
  });

  it("replaces its interval when armed again, so reconnects cannot stack", () => {
    vi.useFakeTimers();
    const first = openSocket();
    const second = openSocket();
    const keepalive = createSocketKeepalive((s) => s.sent.push(PING));
    keepalive.arm(first);
    keepalive.arm(second);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(first.sent).toEqual([]);
    expect(second.sent).toEqual([PING]);
    keepalive.stop();
    expect(vi.getTimerCount()).toBe(0);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS * 3);
    expect(second.sent).toEqual([PING]);
  });

  it("keeps pinging while the document is hidden", () => {
    vi.useFakeTimers();
    globalThis.document = { hidden: true };
    const socket = openSocket();
    const keepalive = createSocketKeepalive((s) => s.sent.push(PING));
    keepalive.arm(socket);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(socket.sent).toEqual([PING]);
    keepalive.stop();
  });
});

describe("world socket subscription", () => {
  afterEach(() => vi.useRealTimers());

  function harness() {
    vi.useFakeTimers();
    const sockets = [];
    class FakeSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 0;
        this.sent = [];
        sockets.push(this);
      }
      send(data) { this.sent.push(data); }
      close() {
        if (this.readyState === 3) return;
        this.readyState = 3;
        this.onclose?.();
      }
    }
    const wsRef = { current: null };
    const setConnected = vi.fn();
    const cleanup = attachWorldSocket({
      seed: 7,
      playerName: "Ada",
      setConnected,
      handlersRef: { current: {} },
      wsRef,
      location: { protocol: "http:", host: "players.test" },
      WebSocketImpl: FakeSocket,
      random: () => 0,
    });
    return { sockets, wsRef, setConnected, cleanup };
  }

  function open(socket) {
    socket.readyState = OPEN;
    socket.onopen();
  }

  it("sends a ping on the open socket and no second interval after reconnect", () => {
    const { sockets } = harness();
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe("ws://players.test/ws?seed=7&name=Ada");
    open(sockets[0]);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(sockets[0].sent).toEqual([PING]);

    sockets[0].close();
    expect(vi.getTimerCount()).toBe(1); // the reconnect timeout, not a second ping
    vi.advanceTimersByTime(750);
    expect(sockets).toHaveLength(2);
    expect(vi.getTimerCount()).toBe(0);
    open(sockets[1]);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(sockets[0].sent).toEqual([PING]);
    expect(sockets[1].sent).toEqual([PING]);
  });

  it("clears the keepalive and does not reconnect when the effect cleans up", () => {
    const { sockets, cleanup } = harness();
    open(sockets[0]);
    expect(vi.getTimerCount()).toBe(1);
    cleanup();
    expect(sockets[0].readyState).toBe(3);
    expect(vi.getTimerCount()).toBe(0);
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(1);
    expect(sockets[0].sent).toEqual([]);

    const again = harness();
    open(again.sockets[0]);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(KEEPALIVE_INTERVAL_MS);
    expect(again.sockets[0].sent).toEqual([PING]);
    expect(sockets[0].sent).toEqual([]);
    again.cleanup();
    expect(vi.getTimerCount()).toBe(0);
  });
});

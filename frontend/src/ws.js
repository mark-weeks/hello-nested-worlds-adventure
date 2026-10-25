import { useEffect, useRef, useState, useCallback } from "react";
import { withKey } from "./auth.js";
import { dispatchMessage } from "./dispatch.js";
import { createSocketKeepalive } from "./keepalive.js";

// Reconnect with exponential backoff + jitter: a flapping network or a
// deploying server gets a fast first retry, but repeated failures back off
// to ~30s instead of hammering every 3s forever. A successful connection
// resets the ladder.
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

// The effect body, returned cleanup included. One keepalive lives for the
// whole subscription: arm() on open replaces its interval, stop() runs on
// close and on the cleanup the hook returns (unmount or a new seed/name).
export function attachWorldSocket({
  seed,
  playerName,
  setConnected,
  handlersRef,
  wsRef,
  location,
  WebSocketImpl = WebSocket,
  random = Math.random,
}) {
  let active = true;
  let timeout;
  let attempts = 0;
  const keepalive = createSocketKeepalive((socket) => {
    socket.send(JSON.stringify({ type: "ping" }));
  });

  function connect() {
    if (!active) return;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocketImpl(withKey(
      `${protocol}//${location.host}/ws?seed=${seed}&name=${encodeURIComponent(playerName)}`));
    wsRef.current = ws;

    ws.onopen = () => {
      attempts = 0;
      setConnected(true);
      keepalive.arm(ws);
    };
    ws.onclose = () => {
      keepalive.stop();
      setConnected(false);
      if (!active) return;
      attempts += 1;
      const backoff = Math.min(RECONNECT_MAX_MS,
        RECONNECT_BASE_MS * 2 ** Math.min(attempts - 1, 5));
      const jitter = backoff * (0.75 + random() * 0.5);
      timeout = setTimeout(connect, jitter);
    };
    ws.onerror = () => ws.close();

    ws.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      dispatchMessage(msg, handlersRef.current);
    };
  }

  connect();
  return () => {
    active = false;
    keepalive.stop();
    clearTimeout(timeout);
    wsRef.current?.close();
  };
}

export default function useWorldSocket(seed, playerName, handlers) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!playerName || !Number.isFinite(seed)) {
      setConnected(false);
      return;
    }
    return attachWorldSocket({
      seed, playerName, setConnected, handlersRef, wsRef, location,
    });
  }, [seed, playerName]);

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, sendMessage };
}

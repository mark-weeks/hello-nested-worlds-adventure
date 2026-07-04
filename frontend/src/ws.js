import { useEffect, useRef, useState, useCallback } from "react";
import { withKey } from "./auth.js";
import { dispatchMessage } from "./dispatch.js";

const RECONNECT_DELAY = 3000;

export default function useWorldSocket(seed, playerName, handlers) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!playerName) {
      setConnected(false);
      return;
    }
    let active = true;
    let timeout;

    function connect() {
      if (!active) return;
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(withKey(`${protocol}//${location.host}/ws?seed=${seed}&name=${encodeURIComponent(playerName)}`));
      wsRef.current = ws;

      ws.onopen  = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (active) timeout = setTimeout(connect, RECONNECT_DELAY); };
      ws.onerror = () => ws.close();

      ws.onmessage = (e) => {
        let msg;
        try { msg = JSON.parse(e.data); } catch { return; }
        dispatchMessage(msg, handlersRef.current);
      };
    }

    connect();
    return () => { active = false; clearTimeout(timeout); wsRef.current?.close(); };
  }, [seed, playerName]);

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, sendMessage };
}

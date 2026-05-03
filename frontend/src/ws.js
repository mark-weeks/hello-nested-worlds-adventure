import { useEffect, useRef, useState, useCallback } from "react";

const RECONNECT_DELAY = 3000;

export default function useWorldSocket(seed, playerName, handlers) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let active = true;
    let timeout;

    function connect() {
      if (!active) return;
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${location.host}/ws?seed=${seed}&name=${encodeURIComponent(playerName)}`);
      wsRef.current = ws;

      ws.onopen  = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (active) timeout = setTimeout(connect, RECONNECT_DELAY); };
      ws.onerror = () => ws.close();

      ws.onmessage = (e) => {
        let msg;
        try { msg = JSON.parse(e.data); } catch { return; }
        const h = handlersRef.current;
        if (msg.type === "player_join"  && h.onPlayerJoin)  h.onPlayerJoin(msg);
        if (msg.type === "player_leave" && h.onPlayerLeave) h.onPlayerLeave(msg);
        if (msg.type === "player_move"  && h.onPlayerMove)  h.onPlayerMove(msg);
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

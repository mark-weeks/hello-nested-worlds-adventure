import { useCallback, useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import { displayName } from "../names.js";
import { waybackMomentLine, waybackNode } from "../wayback.js";
import { drawNodeArt } from "../../../static/nodeart.js";

const REDUCED_MOTION = typeof window !== "undefined" && window.matchMedia
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Wayback({ seed, node, onClose, onListen }) {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [listening, setListening] = useState(false);
  const canvasRef = useRef(null);
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const requestRef = useRef(null);
  const listenedSnapshotRef = useRef(null);
  const listeningRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const onListenRef = useRef(onListen);
  onCloseRef.current = onClose;
  onListenRef.current = onListen;

  const close = useCallback(() => {
    setPlaying(false);
    if (listeningRef.current) {
      listeningRef.current = false;
      setListening(false);
      listenedSnapshotRef.current = null;
      onListenRef.current?.(null);
    }
    onCloseRef.current();
  }, []);

  const loadStep = useCallback(async (at = null) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const cursor = at === null ? "" : `&at=${at}`;
      const url = `/wayback?seed=${seed}&node_name=${encodeURIComponent(node.name)}${cursor}`;
      const response = await fetch(withKey(url), { signal: controller.signal });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || "archive unavailable");
      setSnapshot(data);
    } catch (err) {
      if (err?.name !== "AbortError") {
        setError("The archive is unreadable right now.");
        setPlaying(false);
      }
    } finally {
      if (requestRef.current === controller) setLoading(false);
    }
  }, [node.name, seed]);

  useEffect(() => {
    setSnapshot(null);
    setError("");
    setPlaying(false);
    if (listeningRef.current) {
      listeningRef.current = false;
      setListening(false);
      listenedSnapshotRef.current = null;
      onListenRef.current?.(null);
    }
    loadStep(null);
    return () => requestRef.current?.abort();
  }, [loadStep]);

  useEffect(() => {
    const returnFocus = document.activeElement;
    closeButtonRef.current?.focus();

    const handleKeyDown = event => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...dialogRef.current.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )].filter(element => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!dialogRef.current.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (listeningRef.current) {
        listeningRef.current = false;
        onListenRef.current?.(null);
      }
      if (returnFocus?.isConnected) returnFocus.focus();
    };
  }, [close]);

  useEffect(() => {
    if (!snapshot || !canvasRef.current) return;
    const historical = waybackNode(node, snapshot.node);
    drawNodeArt(canvasRef.current, seed, historical);
  }, [node, seed, snapshot]);

  // Once a player chooses to hear the archive, each scrubbed state retunes the
  // existing deterministic ambience graph. Sound never auto-starts: the click
  // is the browser-required activation gesture.
  useEffect(() => {
    if (listening && snapshot && listenedSnapshotRef.current !== snapshot) {
      listenedSnapshotRef.current = snapshot;
      onListenRef.current?.(waybackNode(node, snapshot.node));
    }
  }, [listening, node, snapshot]);

  useEffect(() => {
    if (!playing || !snapshot || REDUCED_MOTION) return undefined;
    const { step, total } = snapshot.timeline;
    if (total === 0) {
      setPlaying(false);
      return undefined;
    }
    const timer = setTimeout(() => loadStep(step >= total ? 0 : step + 1), 850);
    return () => clearTimeout(timer);
  }, [loadStep, playing, snapshot]);

  const toggleListen = () => {
    if (listening) {
      setListening(false);
      listeningRef.current = false;
      listenedSnapshotRef.current = null;
      onListenRef.current?.(null);
    } else if (snapshot) {
      // Retune inside the click itself so browsers treat AudioContext startup
      // as a user gesture. The effect above handles later scrubbed snapshots.
      listenedSnapshotRef.current = snapshot;
      listeningRef.current = true;
      setListening(true);
      onListenRef.current?.(waybackNode(node, snapshot.node));
    }
  };

  const timeline = snapshot?.timeline;
  const historical = snapshot ? waybackNode(node, snapshot.node) : null;
  const stepLabel = !timeline ? "opening…" : timeline.step === 0
    ? "birth"
    : timeline.present ? "present" : `trace ${timeline.step} of ${timeline.total}`;
  const firstWitness = timeline?.first_witness?.at
    ? `first witnessed ${timeline.first_witness.at.slice(0, 10)}`
    : "not yet witnessed";

  return (
    <div style={w.overlay} onClick={event => {
      if (event.target === event.currentTarget) close();
    }}>
      <div
        ref={dialogRef}
        style={w.box}
        role="dialog"
        aria-modal="true"
        aria-labelledby="wayback-title-react"
        tabIndex={-1}
      >
        <div style={w.headingRow}>
          <div>
            <div id="wayback-title-react" style={w.title}>Wayback · {displayName(node.name)}</div>
            <div style={w.meta}>{firstWitness} · {stepLabel}</div>
          </div>
          <button ref={closeButtonRef} style={w.close} onClick={close} aria-label="Close wayback">×</button>
        </div>

        <canvas
          ref={canvasRef}
          width="640"
          height="300"
          role="img"
          aria-label={`${displayName(node.name)} at ${stepLabel}`}
          style={w.canvas}
        />

        {error ? <div style={w.error}>{error}</div> : snapshot ? (
          <>
            <div style={w.lens}>{snapshot.lens}</div>
            <div style={w.moment}>{waybackMomentLine(timeline)}</div>
            <input
              type="range"
              min="0"
              max={timeline.total}
              value={timeline.step}
              disabled={loading || timeline.total === 0}
              onChange={event => loadStep(Number(event.target.value))}
              aria-label="Wayback time"
              style={w.range}
            />
            <div style={w.rangeLabels}><span>birth</span><span>present</span></div>
            <div style={w.properties}>
              {Object.entries(historical.properties || {}).map(([key, value]) => (
                <div key={key} style={w.property}>
                  <span style={w.propertyKey}>{key.replace(/_/g, " ")}</span>
                  <span style={w.propertyValue}>{String(value)}</span>
                </div>
              ))}
              <div style={w.property}>
                <span style={w.propertyKey}>causal pressure</span>
                <span style={w.propertyValue}>{historical.ripple_score.toFixed(2)}</span>
              </div>
              <div style={w.property}>
                <span style={w.propertyKey}>recorded traces</span>
                <span style={w.propertyValue}>{historical.activity}</span>
              </div>
            </div>
          </>
        ) : <div style={w.empty}>Opening the remembered fold…</div>}

        <div style={w.buttons}>
          {!REDUCED_MOTION && timeline?.total > 0 && (
            <button style={w.button} onClick={() => {
              if (!playing && timeline.present) loadStep(0);
              setPlaying(value => !value);
            }}>{playing ? "pause" : "play evolution"}</button>
          )}
          <button style={w.button} disabled={!snapshot} onClick={toggleListen}>
            {listening ? "return to present sound" : "listen to this moment"}
          </button>
        </div>
      </div>
    </div>
  );
}

const w = {
  overlay: { position: "fixed", inset: 0, zIndex: 110, background: "rgba(7,8,15,0.9)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  box: { width: "min(720px, calc(100vw - 32px))", maxHeight: "88vh", overflowY: "auto", background: "#0b0d1a", border: "1px solid #5268a8", padding: "22px 24px", display: "flex", flexDirection: "column", gap: 10, fontFamily: "Courier New, monospace" },
  headingRow: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 },
  title: { color: "#9aaee8", fontSize: 13, letterSpacing: 2, textTransform: "uppercase" },
  meta: { color: "#4a6080", fontSize: 10, marginTop: 4 },
  close: { color: "#5268a8", border: 0, background: "none", fontSize: 20, cursor: "pointer" },
  canvas: { display: "block", width: "100%", aspectRatio: "16 / 7.5", minHeight: 180, background: "#07080f", border: "1px solid #1a2038" },
  lens: { color: "#56628a", fontSize: 10, fontStyle: "italic" },
  moment: { color: "#8aaccc", fontSize: 12, minHeight: 18 },
  range: { width: "100%", accentColor: "#6f88d8" },
  rangeLabels: { display: "flex", justifyContent: "space-between", color: "#3a5070", fontSize: 9, textTransform: "uppercase", letterSpacing: 1 },
  properties: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "2px 14px", maxHeight: 150, overflowY: "auto" },
  property: { display: "flex", justifyContent: "space-between", gap: 8, borderBottom: "1px solid #111828", padding: "2px 0", fontSize: 10 },
  propertyKey: { color: "#4a6080" },
  propertyValue: { color: "#8aaccc", textAlign: "right", overflowWrap: "anywhere" },
  buttons: { display: "flex", gap: 8, flexWrap: "wrap" },
  button: { background: "#111a30", border: "1px solid #5268a8", color: "#9aaee8", padding: "6px 10px", cursor: "pointer", fontFamily: "inherit", fontSize: 10, letterSpacing: 1, textTransform: "uppercase" },
  error: { color: "#7a9ab8", fontSize: 11, fontStyle: "italic" },
  empty: { color: "#4a6080", fontSize: 11 },
};

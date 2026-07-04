import { useCallback, useEffect, useState } from "react";
import { withKey } from "../auth.js";

// Node interaction panel: the two core-loop mechanics the /app client was
// missing — talk to a node (/speak, Claude-voiced) and solve its puzzle
// (/puzzle + /puzzle/attempt). Kept in its own component so TextPanel stays
// small; mirrors the request shapes the D3 explorer already uses.

export default function Interact({ node, seed, depth, playerName }) {
  const [tab, setTab] = useState("speak");

  // Reset both sub-panels whenever the player moves to a different node.
  const nodeKey = node?.name;

  return (
    <div style={s.wrap}>
      <div style={s.tabs}>
        <button
          style={tab === "speak" ? s.tabActive : s.tab}
          onClick={() => setTab("speak")}
        >Speak</button>
        <button
          style={tab === "puzzle" ? s.tabActive : s.tab}
          onClick={() => setTab("puzzle")}
        >Puzzle</button>
      </div>
      {tab === "speak"
        ? <Speak key={`sp-${nodeKey}`} node={node} seed={seed} playerName={playerName} />
        : <Puzzle key={`pz-${nodeKey}`} node={node} seed={seed} depth={depth} playerName={playerName} />}
    </div>
  );
}

// ── Speak to node (POST /speak) ─────────────────────────────────────────────

function Speak({ node, seed, playerName }) {
  const [message, setMessage] = useState("Describe yourself to a traveler who has just arrived.");
  const [response, setResponse] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | ok | error
  // Who can be addressed here: the place itself, plus any agents whose
  // traces are in this node's history — the presences you found evidence of.
  const [target, setTarget] = useState("node");
  const [presences, setPresences] = useState([]);

  useEffect(() => {
    setTarget("node");
    setPresences([]);
    fetch(withKey(`/history?seed=${seed ?? 0}&node_name=${encodeURIComponent(node.name)}`))
      .then(r => r.json())
      .then(d => {
        const seen = new Map();
        for (const m of d.mutations || []) {
          const a = m.data?.agent;
          if (a && !seen.has(a)) seen.set(a, m.data?.persona || "");
        }
        setPresences([...seen].slice(0, 4).map(([name, persona]) => ({ name, persona })));
      })
      .catch(() => {});
  }, [node?.name, seed]);

  const send = useCallback(async () => {
    const text = message.trim();
    if (!text || state === "loading") return;
    setState("loading");
    setResponse("…");
    try {
      const addressingAgent = target !== "node";
      const r = await fetch(withKey(addressingAgent ? "/agent/voice" : "/speak"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(addressingAgent ? {
          agent_name: target,
          node_name: node.name,
          message: text,
          seed: seed ?? 0,
        } : {
          node_name: node.name,
          message: text,
          seed: seed ?? 0,
          player_name: playerName || undefined,
        }),
      });
      const data = await r.json();
      setResponse(data.error || data.response || "(no response)");
      setState(data.error ? "error" : "ok");
    } catch (e) {
      setResponse("Network error: " + e.message);
      setState("error");
    }
  }, [message, node, seed, playerName, state, target]);

  return (
    <div style={s.panel}>
      <div style={s.hint}>Speak to {node.level} · {node.name}</div>
      {presences.length > 0 && (
        <div style={s.targetRow}>
          <button
            style={target === "node" ? s.targetActive : s.target}
            onClick={() => setTarget("node")}
          >the place</button>
          {presences.map(p => (
            <button
              key={p.name}
              style={target === p.name ? s.targetActive : s.target}
              title={p.persona ? `a ${p.persona} whose traces are here` : "traces found here"}
              onClick={() => setTarget(p.name)}
            >{p.name}{p.persona ? ` · ${p.persona}` : ""}</button>
          ))}
        </div>
      )}
      <textarea
        style={s.textarea}
        maxLength={1024}
        value={message}
        onChange={e => setMessage(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }}
        placeholder="What do you want to say?"
      />
      <button style={s.btn} onClick={send} disabled={state === "loading"}>
        {state === "loading" ? "…" : (target === "node" ? "Speak to node" : `Speak to ${target}`)}
      </button>
      {response && (
        <div style={state === "error" ? s.respError : s.resp}>{response}</div>
      )}
    </div>
  );
}

// ── Puzzle (GET /puzzle, POST /puzzle/attempt) ──────────────────────────────

function Puzzle({ node, seed, depth, playerName }) {
  const [puzzle, setPuzzle] = useState(null);
  const [status, setStatus] = useState("");
  const [answer, setAnswer] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null); // {correct,result,hint,correct_answer,solver}
  const [busy, setBusy] = useState(false);

  useEffect(() => { setPuzzle(null); setStatus(""); setResult(null); setAnswer(""); setAttempt(0); }, [node?.name]);

  const find = useCallback(async () => {
    setStatus("Searching…"); setResult(null); setPuzzle(null);
    try {
      const url = `/puzzle?seed=${seed}&depth=${depth}&node_name=${encodeURIComponent(node.name)}`;
      const r = await fetch(withKey(url));
      const data = await r.json();
      if (!data.found) { setStatus("No puzzle at this node."); return; }
      setPuzzle(data); setStatus("");
    } catch (e) { setStatus("Error: " + e.message); }
  }, [node, seed, depth]);

  const submit = useCallback(async () => {
    const a = answer.trim();
    if (!a || busy || (result && (result.correct || result.result === "FAILED"))) return;
    setBusy(true);
    try {
      const r = await fetch(withKey("/puzzle/attempt"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seed, depth, node_name: node.name, answer: a,
          player_name: playerName || undefined,
        }),
      });
      const data = await r.json();
      setResult(data);
      setAttempt(data.attempt ?? attempt + 1);
    } catch (e) {
      setStatus("Error: " + e.message);
    } finally {
      setBusy(false);
    }
  }, [answer, busy, result, seed, depth, node, playerName, attempt]);

  if (!puzzle) {
    return (
      <div style={s.panel}>
        <button style={s.btn} onClick={find}>Find puzzle here</button>
        {status && <div style={s.hint}>{status}</div>}
      </div>
    );
  }

  const done = result && (result.correct || result.result === "FAILED");
  const remaining = puzzle.max_attempts - attempt;
  return (
    <div style={s.panel}>
      <div style={s.pKind}>
        {puzzle.kind.replace(/_/g, " ")}
        <span style={s.pDiff} title={`difficulty ${puzzle.difficulty ?? 2}/4`}>
          {" "}{"★".repeat(Math.min(4, Math.max(1, puzzle.difficulty ?? 2)))}
          {"☆".repeat(4 - Math.min(4, Math.max(1, puzzle.difficulty ?? 2)))}
        </span>
      </div>
      <div style={s.pName}>{puzzle.name}</div>
      <div style={s.pPrompt}>{puzzle.prompt}</div>
      <input
        style={s.input}
        value={answer}
        maxLength={128}
        disabled={done}
        placeholder="Your answer…"
        onChange={e => setAnswer(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") submit(); }}
      />
      {!done && <button style={s.btn} onClick={submit} disabled={busy}>Submit</button>}
      {result && result.correct && (
        <div style={s.correct}>
          Correct{result.solver ? ` — solved by ${result.solver}` : ""}.
        </div>
      )}
      {result && !result.correct && result.result === "FAILED" && (
        <div style={s.failed}>Failed. The answer was: {result.correct_answer}</div>
      )}
      {result && !result.correct && result.result === "UNSOLVED" && (
        <div style={s.wrong}>
          Wrong. {remaining} attempt{remaining !== 1 ? "s" : ""} left.
          {result.hint ? <div style={s.pHint}>Hint: {result.hint}</div> : null}
        </div>
      )}
    </div>
  );
}

const s = {
  wrap:     { display: "flex", flexDirection: "column", gap: "6px", flexShrink: 0, borderTop: "1px solid #1e2235", paddingTop: "10px" },
  tabs:     { display: "flex", gap: "6px" },
  tab:      { flex: 1, background: "#0b0f1a", border: "1px solid #1e2235", color: "#5a6a90", padding: "4px 0", cursor: "pointer", fontFamily: "inherit", fontSize: "11px" },
  tabActive:{ flex: 1, background: "#10131f", border: "1px solid #3a8eff", color: "#3a8eff", padding: "4px 0", cursor: "pointer", fontFamily: "inherit", fontSize: "11px" },
  panel:    { display: "flex", flexDirection: "column", gap: "6px" },
  hint:     { fontSize: "10px", color: "#4a5580" },
  targetRow:    { display: "flex", gap: "4px", flexWrap: "wrap" },
  target:       { background: "#0b0f1a", border: "1px solid #1e2235", color: "#5a6a90", padding: "2px 8px", cursor: "pointer", fontFamily: "inherit", fontSize: "10px" },
  targetActive: { background: "#10131f", border: "1px solid #4af0c8", color: "#4af0c8", padding: "2px 8px", cursor: "pointer", fontFamily: "inherit", fontSize: "10px" },
  textarea: { background: "#10131f", border: "1px solid #2a3050", color: "#b0bcd0", padding: "6px", fontFamily: "inherit", fontSize: "12px", resize: "none", height: "48px", lineHeight: 1.4 },
  input:    { background: "#10131f", border: "1px solid #2a3050", color: "#b0bcd0", padding: "5px 6px", fontFamily: "inherit", fontSize: "12px" },
  btn:      { background: "#0e1828", border: "1px solid #2a4060", color: "#3a8eff", padding: "5px 10px", cursor: "pointer", fontFamily: "inherit", fontSize: "11px" },
  resp:     { fontSize: "12px", color: "#7a9ab8", fontStyle: "italic", lineHeight: 1.6, whiteSpace: "pre-wrap", borderLeft: "2px solid #2a4060", paddingLeft: "8px" },
  respError:{ fontSize: "12px", color: "#a05555", lineHeight: 1.6, whiteSpace: "pre-wrap" },
  pKind:    { fontSize: "9px", letterSpacing: "0.12em", textTransform: "uppercase", color: "#4a6080" },
  pDiff:    { color: "#c8a13a", letterSpacing: "1px" },
  pName:    { fontSize: "13px", fontWeight: "bold", color: "#c0d0e8" },
  pPrompt:  { fontSize: "12px", color: "#8aaccc", lineHeight: 1.5 },
  pHint:    { fontSize: "11px", color: "#4a8080", fontStyle: "italic", marginTop: "4px" },
  correct:  { fontSize: "12px", color: "#44cc88" },
  failed:   { fontSize: "12px", color: "#cc4444" },
  wrong:    { fontSize: "12px", color: "#cc8844" },
};

import { useCallback, useEffect, useState } from "react";
import "../../../static/intents.js";
import { withKey } from "../auth.js";
import Interventions from "./Interventions.jsx";

// Node interaction panel: the two core-loop mechanics the /app client was
// missing — talk to a node (/speak, Claude-voiced) and solve its puzzle
// (/puzzle + /puzzle/attempt). Kept in its own component so TextPanel stays
// small; mirrors the request shapes the D3 explorer already uses.

export default function Interact({ node, seed, depth, playerName, onSolved, onNodeChanged, onJump, onEnsurePosition }) {
  const [tab, setTab] = useState("speak");

  // Reset the sub-panels whenever the player moves to a different node.
  const nodeKey = node?.name;
  const verb = node?.verb; // the scale-native act, from /world

  return (
    <section id="interactions" aria-label="Interact here" tabIndex={-1} style={s.wrap}>
      <div className="interface-tabs" role="group" aria-label="Interaction mode">
        <button
          aria-pressed={tab === "speak"}
          onClick={() => setTab("speak")}
        >Speak</button>
        <button
          aria-pressed={tab === "puzzle"}
          onClick={() => setTab("puzzle")}
        >Puzzle</button>
        {verb && (
          <button
            aria-pressed={tab === "act"}
            onClick={() => setTab("act")}
          >Act</button>
        )}
      </div>
      {tab === "speak" &&
        <Speak key={`sp-${nodeKey}`} node={node} seed={seed} playerName={playerName} />}
      {tab === "puzzle" &&
        <Puzzle key={`pz-${nodeKey}`} node={node} seed={seed} depth={depth} playerName={playerName} onSolved={onSolved} />}
      {tab === "act" && verb &&
        <Interventions key={`act-${nodeKey}`} node={node} seed={seed} onJump={onJump} onNodeChanged={() => onNodeChanged?.(node.name, {})} onEnsurePosition={onEnsurePosition} />}
    </section>
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
          player_name: playerName || undefined,
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
      setResponse("Your words did not reach this place. Try speaking again.");
      setState("error");
    }
  }, [message, node, seed, playerName, state, target]);

  return (
    <div style={s.panel}>
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
        aria-label="Message to this place"
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

function Puzzle({ node, seed, depth, playerName, onSolved }) {
  const nodeName = node?.name;
  const [puzzle, setPuzzle] = useState(null);
  const [status, setStatus] = useState("");
  const [answer, setAnswer] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null); // {correct,result,hint,correct_answer,solver}
  const [busy, setBusy] = useState(false);
  const [retryable, setRetryable] = useState(false);

  const find = useCallback(async () => {
    setStatus("Searching…"); setResult(null); setPuzzle(null); setRetryable(false);
    try {
      const url = `/puzzle?seed=${seed}&depth=${depth}&node_name=${encodeURIComponent(nodeName)}`;
      const r = await fetch(withKey(url));
      const data = await r.json();
      if (!r.ok || data.error) { setStatus(data.error || "The question could not be reached. Try again."); setRetryable(true); return; }
      if (!data.found) { setStatus("No puzzle at this node."); return; }
      setPuzzle(data);
      setAttempt(data.attempt ?? 0);
      setResult(data.solved ? {
        correct: true,
        result: "SOLVED",
        solver: data.solver,
        contributors: data.contributors,
        changed: null,
        persisted: true,
      } : null);
      setStatus("");
    } catch (e) { setStatus("The question could not be reached. Try again."); setRetryable(true); }
  }, [nodeName, seed, depth]);

  // The Puzzle tab is itself the player's request to see the puzzle. Because
  // this component mounts only while that tab is active, loading on mount
  // removes the redundant "Find puzzle here" gate.
  useEffect(() => { find(); }, [find]);

  const submit = useCallback(async () => {
    const a = answer.trim();
    if (!a || busy || (result && (result.correct || result.result === "FAILED"))) return;
    setBusy(true);
    try {
      const r = await fetch(withKey("/puzzle/attempt"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seed, depth, node_name: node.name, answer: a, puzzle_name: puzzle.name,
          player_name: playerName || undefined,
        }),
      });
      const data = await r.json();
      if (!r.ok || data.error) { setStatus(data.error || "The question has changed. Reopen it."); return; }
      setStatus("");
      setResult(data);
      setAttempt(data.attempt ?? attempt + 1);
      // If this node was sealed, the solve IS the key: tell App to walk
      // through the now-open door off the HTTP response itself — the same
      // trigger the D3 explorer uses — instead of relying only on the WS
      // puzzle_solved broadcast, which an evicted or reconnecting socket
      // can miss. (A harmless re-move anywhere else.)
      if (data.correct) onSolved?.(node.name, data.changed);
    } catch (e) {
      setStatus("The question could not be reached. Try again.");
    } finally {
      setBusy(false);
    }
  }, [answer, busy, result, seed, depth, node, playerName, attempt, onSolved, puzzle]);

  if (!puzzle) {
    return (
      <div style={s.panel}>
        <div style={s.hint} role="status">{status || "Searching…"}</div>
        {retryable && <button onClick={find}>Retry question</button>}
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
      <a style={{color: "var(--link)", fontSize: ".875rem"}} href={withKey(`/puzzle/evidence?seed=${seed}&epoch=${puzzle.epoch}&node_name=${encodeURIComponent(node.name)}`)} target="_blank" rel="noopener">Conditions when this question opened ↗</a>
      {status && <div role="status">{status} <button onClick={find}>Reopen question</button></div>}
      <input
        aria-label="Puzzle answer"
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
          {result.persisted ? "Already resolved" : "Correct"}
          {result.solver ? ` — solved by ${result.solver}` : ""}.
          <div style={s.reward}>
            {result.changed && Object.keys(result.changed).length
              ? `Reward: ${Object.entries(result.changed).map(([k, v]) => `${k.replace(/_/g, " ")} → ${v}`).join(" · ")}`
              : "Its change remains part of this world."}
          </div>
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
  wrap: { display:"flex", flexDirection:"column", gap:16 },
  panel: { display:"flex", flexDirection:"column", gap:12 },
  hint: { fontSize:".875rem", color:"var(--muted)" },
  targetRow: { display:"flex", gap:8, flexWrap:"wrap" },
  target: { fontSize:".875rem" },
  targetActive: { color:"var(--accent)", borderColor:"var(--accent)", fontWeight:650 },
  textarea: { width:"100%" },
  btn: { width:"100%" },
  resp: { color:"var(--text)", whiteSpace:"pre-wrap", lineHeight:1.6 },
  respError: { color:"var(--attention)", whiteSpace:"pre-wrap" },
  pKind: { fontSize:".875rem", color:"var(--muted)" },
  pDiff: { marginLeft:8, color:"var(--accent)" },
  pName: { font:"1.25rem/1.3 Georgia,serif" },
  pPrompt: { lineHeight:1.6 },
  attempts: { fontSize:".875rem", color:"var(--muted)" },
  input: { width:"100%" },
  correct: { color:"var(--text)" },
  failed: { color:"var(--attention)" },
  wrong: { color:"var(--attention)" },
  pHint: { color:"var(--muted)", marginTop:8 },
  reward: { color:"var(--muted)", marginTop:8 },
};

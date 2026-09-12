import "../../../static/intents.js";
import { useCallback, useEffect, useRef, useState } from "react";
import { betaKey } from "../auth.js";
import { displayName } from "../names.js";

export default function Investigation({ node, seed, onJump, onNodeChanged }) {
  const [situation, setSituation] = useState(null);
  const [clue, setClue] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("What will each signal route cost the gallery?");
  const [failure, setFailure] = useState(false);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const api = useCallback(async (path, body) => {
    const response = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: {"X-Beta-Key": betaKey(), "Content-Type": "application/json"},
      ...(body ? {body: JSON.stringify({...body, seed})} : {})});
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "The signal is quiet. Try again.");
    return data;
  }, [seed]);
  const refresh = useCallback(async () => {
    const data = await api(`/situation?seed=${seed}`);
    if (active.current) { setSituation(data.situation); setFailure(false); }
  }, [api, seed]);
  useEffect(() => {
    let here = true;
    refresh().catch(() => { if (here) setFailure(true); });
    return () => { here = false; };
  }, [refresh]);
  useEffect(() => {
    if (!["investigate", "decision", "pending"].includes(situation?.phase)) return;
    const timer = setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 5000);
    return () => clearInterval(timer);
  }, [refresh, situation?.phase]);
  useEffect(() => { setClue(""); setMessage(""); }, [node.name]);
  async function act(path, payload, consequential = false) {
    if (busy) return;
    const place = node.name;
    setBusy(true); setMessage("");
    let intent;
    try {
      if (consequential) intent = await globalThis.EnfoldedIntents.begin(path, seed, payload, betaKey());
      const data = await api(path, {...payload, ...(intent ? {request_id: intent.request_id} : {})});
      globalThis.EnfoldedIntents.finish(intent);
      if (!active.current) return;
      if (data.clue) setClue(data.clue);
      if (data.response) setClue(data.response);
      setMessage(data.message || (data.clue ? "The clue is saved with this investigation." : ""));
      await refresh();
      onNodeChanged?.(place, data);
    } catch (e) { if (active.current) setMessage(e.message); }
    finally { if (active.current) setBusy(false); }
  }
  if (failure) return <div style={styles.box}><button onClick={() => refresh().catch(() => {})}>Retry investigation</button></div>;
  if (!situation) return null;
  const role = Object.entries(situation.nodes).find(([, name]) => name === node.name)?.[0];
  const ready = [situation.nodes.instrument, situation.nodes.regulator].every(name => situation.discoveries.includes(name));
  const choosing = ["investigate", "decision"].includes(situation.phase);
  return <section aria-label="Investigation" style={styles.box}>
    <div style={styles.eyebrow}>AN INVESTIGATION · {situation.phase === "aftermath" ? "THE AFTERMATH" : "A SHARED WORLD"}</div>
    <h2 style={styles.title}>{situation.title}</h2>
    <p>Who should control the signal, and who should get to hear it?</p>
    {situation.phase === "pending" && <p role="status">The choice is made. Its consequences are traveling outward. {situation.pending_steps} changes remain.</p>}
    {situation.phase === "aftermath" && <p>The world chose to {situation.branch === "preserve" ? "keep the signal enclosed" : "release the signal"}. Tessera’s lasting mark is waiting in the Fold.</p>}
    <p style={styles.quiet}>{situation.phase === "aftermath" ? "Tessera’s promise is fulfilled. The Fold preserves the signal’s route." : situation.promise}</p>
    <div style={styles.links}>
      {["instrument", "regulator", "fold", "region"].map(key => <button style={styles.link} key={key} onClick={() => onJump(situation.nodes[key])}>{displayName(situation.nodes[key])}</button>)}
    </div>
    {role && <button disabled={busy || !betaKey()} style={styles.button} onClick={() => act("/situation/discover", {node: node.name})}>Read the clue here</button>}
    <label style={{display: "block", marginTop: 12}}>Ask Tessera about the signal
      <input value={question} onChange={event => setQuestion(event.target.value)} maxLength={1024} style={{display: "block", boxSizing: "border-box", width: "100%", margin: "8px 0", padding: 8, background: "#142425", color: "#dce9e5", border: "1px solid #617e82"}} />
    </label>
    <button style={styles.button} disabled={busy || !question.trim()} onClick={() => act("/agent/voice", {agent_name: situation.keeper, node_name: node.name, message: question})}>Ask Tessera</button>
    {clue && <blockquote style={styles.clue}>{clue}</blockquote>}
    {!betaKey() && <p>Use your personal invite to save clues or join the decision.</p>}
    {choosing && <>
      <p style={styles.quiet}>Read the instrument and regulator, then record your preference. Each invited participant has one changeable choice. A tie keeps the decision open.</p>
      {situation.deadline && <p>Decision window ends at {new Date(situation.deadline.replace(" ", "T") + "Z").toLocaleTimeString()}. Votes: keep {situation.counts.preserve || 0}, release {situation.counts.release || 0}.</p>}
      {Object.entries(situation.branches).map(([branch, option]) => <div key={branch} style={styles.option}>
        <strong>{option.label}</strong><p>{option.benefit} {option.cost}</p>
        <button style={styles.button} disabled={busy || !ready} onClick={() => act("/situation/choose", {branch}, true)}>{situation.choice === branch ? "Your current preference" : "Choose this route"}</button>
      </div>)}
    </>}
    {situation.phase === "aftermath" && <>
      <button style={styles.link} onClick={() => onJump(situation.nodes.fold)}>Visit the lasting mark</button>
      <p>Read the Fold and the chain to compare the echo, then leave a reference marker for later travelers.</p>
      <button style={styles.link} onClick={() => onJump(situation.nodes.chain)}>Visit the chain</button>
      <button style={styles.button} disabled={busy || situation.followed_up || ![situation.nodes.fold, situation.nodes.chain].every(name => situation.discoveries.includes(name))} onClick={() => act("/situation/follow-up", {}, true)}>{situation.followed_up ? "Your reference marker remains" : "Set a reference marker"}</button>
    </>}
    <p role="status" aria-live="polite">{message}</p>
    <a style={styles.anchor} href={`/journal?seed=${seed}&node=${encodeURIComponent(node.name)}`} target="_blank" rel="noopener">Keep a private question in your journal ↗</a>
  </section>;
}
const styles = {
  box: {padding: "18px 16px", borderBottom: "1px solid #34474f", background: "linear-gradient(130deg,#172c30,#101825)", color: "#dce9e5", lineHeight: 1.5, fontSize: 13},
  eyebrow: {fontSize: 10, color: "#b6cfa7", letterSpacing: ".12em"},
  title: {fontSize: 21, margin: "8px 0", fontWeight: 500}, quiet: {color: "#b6c7c4"},
  links: {display: "flex", gap: 6, flexWrap: "wrap"},
  link: {background: "transparent", border: "1px solid #617e82", color: "#bce5dc", padding: "8px", cursor: "pointer", font: "inherit", marginBottom: 6},
  button: {background: "#294540", color: "#e3f1e7", border: "1px solid #85a492", padding: "9px 12px", cursor: "pointer", font: "inherit", borderRadius: 3},
  option: {borderTop: "1px solid #49615d", marginTop: 14, paddingTop: 12},
  clue: {margin: "14px 0", padding: "12px", borderLeft: "2px solid #c7be8c", background: "#152425"},
  anchor: {color: "#bce5dc"},
};

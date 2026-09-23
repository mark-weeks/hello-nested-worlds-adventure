import { useCallback, useEffect, useRef, useState } from "react";
import { withKey } from "../auth.js";
import { mutationLine } from "../mutations.js";

// The world chronicle: the permanent record of everything every player and
// agent has done in this world, paginated backward in time and grouped into
// deterministically named eras (GET /chronicle). This is how a new arrival
// perceives the history they are building on. Rows render through the
// shared mutations.js (the date is shown in its own column here).

export default function Chronicle({ seed, onClose }) {
  const [entries, setEntries] = useState([]);
  const [meta, setMeta] = useState("");
  const [cursor, setCursor] = useState(null);
  const [done, setDone] = useState(false);
  const loading = useRef(false);
  const dialog=useRef(null);
  useEffect(()=>{
    const focus=document.activeElement;
    const modal=dialog.current;
    if(!modal.open)modal.showModal();
    return ()=>{
      // Release modal focus before restoring the opener, including effect replay.
      if(modal.open)modal.close();
      if(focus?.isConnected)focus.focus();
    };
  },[]);

  const loadPage = useCallback(async (before) => {
    if (loading.current) return;
    loading.current = true;
    try {
      const q = before ? `&before=${before}` : "";
      const r = await fetch(withKey(`/chronicle?seed=${seed}&limit=40${q}`));
      const data = await r.json();
      setMeta(`${data.total} recorded events` +
        (data.began ? ` since ${data.began.slice(0, 10)}` : "") +
        ` · now: ${data.era_now}`);
      setEntries(prev => before ? [...prev, ...(data.entries || [])] : (data.entries || []));
      setCursor(data.next_before);
      setDone(!data.next_before);
    } catch {
      setMeta("The chronicle is unreadable right now.");
    } finally {
      loading.current = false;
    }
  }, [seed]);

  useEffect(() => { loadPage(null); }, [loadPage]);

  // Group entries under era headers as we render.
  let lastEra = null;
  const rows = [];
  for (const e of entries) {
    if (e.era && e.era !== lastEra) {
      lastEra = e.era;
      rows.push(<div key={`era-${e.id}`} style={c.era}>{e.era}</div>);
    }
    rows.push(
      <div key={e.id} style={c.row}>
        <span style={c.when}>{(e.at || "").slice(5, 16)}</span> {mutationLine(e)}
      </div>
    );
  }

  return (
    <dialog ref={dialog} className="world-dialog" aria-label="World Chronicle" style={c.box} onCancel={onClose}>
        <div style={c.title}>World Chronicle</div>
        <div style={c.meta}>{meta}</div>
        <div style={c.list}>
          {rows.length ? rows
            : <div style={c.empty}>Nothing has happened here yet. You would be first.</div>}
        </div>
        <div style={c.btnRow}>
          {!done && <button style={c.btn} onClick={() => loadPage(cursor)}>further back</button>}
          <button style={c.btn} onClick={onClose}>close</button>
        </div>
    </dialog>
  );
}

const c = {
  box:     { margin:"auto", color:"var(--text)", background: "var(--surface)", border: "1px solid var(--line)", padding: "28px 32px", width: "min(520px, calc(100vw - 48px))", maxHeight: "80vh", display: "flex", flexDirection: "column", gap: "12px", fontFamily: "system-ui, sans-serif" },
  title:   { fontSize: ".875rem", letterSpacing: "3px", textTransform: "uppercase", color: "var(--muted)" },
  meta:    { fontSize: ".875rem", color: "var(--muted)", letterSpacing: "1px" },
  list:    { overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "2px", minHeight: "120px" },
  era:     { fontSize: ".875rem", letterSpacing: "2px", textTransform: "uppercase", color: "var(--muted)", margin: "10px 0 4px", borderBottom: "1px solid var(--line)", paddingBottom: "3px" },
  row:     { fontSize: ".875rem", color: "var(--muted)", lineHeight: 1.5 },
  when:    { color: "var(--muted)" },
  empty:   { fontSize: ".875rem", color: "var(--muted)" },
  btnRow:  { display: "flex", gap: "10px" },
  btn:     { background: "var(--surface)", border: "1px solid var(--line)", color: "var(--muted)", padding: "5px 12px", cursor: "pointer", fontFamily: "inherit", fontSize: ".875rem" },
};

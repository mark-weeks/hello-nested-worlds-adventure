export default function TextPanel({ node, players, connected }) {
  const here = players.filter((p) => p.node === node.name);

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.level}>{node.level}</span>
        <span style={styles.name}>{node.name}</span>
      </div>

      <div style={styles.section}>
        <div style={styles.sectionLabel}>Properties</div>
        {Object.entries(node.properties).map(([k, v]) => (
          <div key={k} style={styles.prop}>
            <span style={styles.propKey}>{k}</span>
            <span style={styles.propVal}>{String(v)}</span>
          </div>
        ))}
      </div>

      {node.children.length > 0 && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Passages ({node.children.length})</div>
          {node.children.map((c) => (
            <div key={c.id} style={styles.passage}>→ {c.name} <span style={styles.passageLevel}>({c.level})</span></div>
          ))}
        </div>
      )}

      {here.length > 0 && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Present here</div>
          {here.map((p) => <div key={p.session_id} style={styles.player}>◈ {p.name}</div>)}
        </div>
      )}

      <div style={styles.status}>
        <span style={{ color: connected ? "#4af0a0" : "#f04a4a" }}>
          {connected ? "● connected" : "○ disconnected"}
        </span>
      </div>
    </div>
  );
}

const styles = {
  panel:        { flex: "0 0 35%", display: "flex", flexDirection: "column", padding: "24px 20px", overflowY: "auto", borderLeft: "1px solid #1e2235", gap: "20px" },
  header:       { display: "flex", flexDirection: "column", gap: "4px" },
  level:        { fontSize: "11px", color: "#4a5580", textTransform: "uppercase", letterSpacing: "0.1em" },
  name:         { fontSize: "20px", color: "#d0daf0", fontWeight: "bold" },
  section:      { display: "flex", flexDirection: "column", gap: "6px" },
  sectionLabel: { fontSize: "10px", color: "#4a5580", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "2px" },
  prop:         { display: "flex", justifyContent: "space-between", fontSize: "13px", gap: "8px" },
  propKey:      { color: "#6878a8" },
  propVal:      { color: "#9aaac8", textAlign: "right" },
  passage:      { fontSize: "13px", color: "#7888b0" },
  passageLevel: { color: "#4a5580" },
  player:       { fontSize: "13px", color: "#4af0c8" },
  status:       { marginTop: "auto", fontSize: "12px" },
};

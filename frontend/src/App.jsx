import { useState, useEffect, useCallback, useRef } from "react";
import SceneView from "./components/SceneView.jsx";
import TextPanel from "./components/TextPanel.jsx";
import useWorldSocket from "./ws.js";
import { withKey, urlName, betaKey } from "./auth.js";
import { entryPath } from "./entry.js";
import { NodeAmbience } from "../../static/nodesound.js";

// Honor the OS-level motion preference: transient overlays (ripples,
// sparkles, encounter glyphs) become no-ops instead of movement.
const REDUCED_MOTION = typeof window !== "undefined" && window.matchMedia
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const DEFAULT_SEED  = 42;
const WORLD_DEPTH   = 6;   // must match the depth used for /puzzle lookups
const MAX_EVENTS    = 40;
const MAX_TRANSIENTS = 12;
const MAX_HISTORY   = 12;  // how much of the world's past backfills the feed
const NAME_KEY      = "nw_player_name";
const LAST_NODE_KEY = "nw_last_node";   // resume: the node the player last stood on
const LAST_SEED_KEY = "nw_last_seed";   // resume: the world it belonged to
const INTRO_SEEN    = "nw_seen_intro";  // shared with the D3 explorer

// The world's recent past, rendered into the event feed on load so a new
// arrival sees a world already in motion — who solved what, which agents
// passed through, where danger stirred — instead of "No events yet."
function describeMutation(m) {
  const when = (m.at || "").slice(0, 10);
  const who = m.player || m.data?.agent || "someone";
  switch (m.type) {
    case "PUZZLE_SOLVED":  return `${when} · ${who} solved a puzzle at ${m.node}`;
    case "PUZZLE_FAILED":  return `${when} · a puzzle resisted ${who} at ${m.node}`;
    case "PLAYER_SPEAK":   return `${when} · ${who} spoke with ${m.node}`;
    case "PLAYER_CHAT":    return `${when} · ${who} said something at ${m.node}`;
    case "AGENT_VISIT":    return `${when} · ${who} passed through ${m.node}`;
    case "DANGER_ALERT":   return `${when} · danger stirred at ${m.node}`;
    case "AGENT_VOICE":    return `${when} · ${who} spoke with ${m.data?.agent || "a wanderer"} at ${m.node}`;
    case "PLAYER_JOIN":    return `${when} · ${who} arrived in the world`;
    case "PLAYER_LEAVE":   return `${when} · ${who} departed`;
    case "PLAYER_MOVE":    return `${when} · ${who} passed into ${m.node}`;
    case "PUZZLE_ATTEMPT": return `${when} · ${who} worked at a puzzle in ${m.node}`;
    default:               return `${when} · something happened at ${m.node}`;
  }
}

// ── Cross-device resume ─────────────────────────────────────────────────────
// localStorage remembers the last node per browser; the server remembers it per
// invite key, so the position follows the player across devices. On mount we
// pull the server copy (if this browser carries a per-user key) into
// localStorage before the first load; on every move we mirror it back. No key /
// no server row → the local cache stands.
async function hydratePositionFromServer() {
  if (!betaKey()) return null;
  try {
    const res = await fetch(withKey("/position"));
    if (!res.ok) return null;
    const { position } = await res.json();
    if (!position || !position.node) return null;
    localStorage.setItem(LAST_NODE_KEY, position.node);
    const s = Number.isFinite(position.seed) ? position.seed : null;
    if (s != null) localStorage.setItem(LAST_SEED_KEY, String(s));
    return s;                       // seed to load, so the saved node exists in it
  } catch (_) {
    return null;                    // offline / gate off — keep the local cache
  }
}

function savePositionToServer(node, seed) {
  if (!betaKey() || !node) return;
  try {
    fetch(withKey("/position"), {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ node, seed, depth: WORLD_DEPTH }),
    }).catch(() => {});             // fire-and-forget; localStorage is the backstop
  } catch (_) {}
}

export default function App() {
  const [seed, setSeed]           = useState(() => {
    const saved = parseInt(localStorage.getItem(LAST_SEED_KEY), 10);
    return Number.isFinite(saved) ? saved : DEFAULT_SEED;
  });
  const [nodeStack, setNodeStack] = useState([]);
  const [players, setPlayers]     = useState([]);
  const [agents, setAgents]       = useState({});  // name → { node, persona }
  const [events, setEvents]       = useState([]);
  // The fetched world tree, retained so jump-to-traveler can rebuild a real
  // ancestry stack from a node name (names encode their path).
  const worldRootRef = useRef(null);
  // A node whose seal we just opened: walk through once the solve lands.
  const [walkThrough, setWalkThrough] = useState(null);
  const [transients, setTransients] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [playerName, setPlayerName] = useState(() => localStorage.getItem(NAME_KEY) || urlName() || "");
  const [introSeen, setIntroSeen] = useState(() => !!localStorage.getItem(INTRO_SEEN));
  const [soundOn, setSoundOn] = useState(false);
  const ambienceRef = useRef(null);

  const pushEvent = useCallback((evt) => {
    setEvents(ev => [evt, ...ev].slice(0, MAX_EVENTS));
  }, []);

  // Transients are short-lived visual overlays in SceneView (ripples,
  // encounter glyphs, solve sparkles). Only the ones whose node matches
  // the currently-rendered scene are pushed; when the player navigates,
  // a separate effect drops them all so a stray ripple from the previous
  // node never bleeds into the new one.
  const pushTransient = useCallback((t) => {
    if (REDUCED_MOTION) return;
    const id = (typeof crypto !== "undefined" && crypto.randomUUID)
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
    const entry = { ...t, id, startedAt: performance.now() };
    setTransients(prev => [...prev, entry].slice(-MAX_TRANSIENTS));
    setTimeout(() => {
      setTransients(prev => prev.filter(x => x.id !== id));
    }, t.duration ?? 1500);
  }, []);

  const loadWorld = useCallback((s) => {
    setLoading(true);
    setPlayers([]);
    setEvents([]);
    localStorage.setItem(LAST_SEED_KEY, String(s));
    fetch(withKey(`/world?seed=${s}&depth=${WORLD_DEPTH}`))
      .then(r => r.json())
      .then(data => {
        // Non-linear entry: resume the last node if it's in this world, else
        // drop a first-time player in at a mid-world node. The returned path is
        // the nav stack, so "back" walks the real ancestry.
        const savedNode = localStorage.getItem(LAST_NODE_KEY);
        const name = localStorage.getItem(NAME_KEY) || urlName() || "";
        worldRootRef.current = data.world;
        setNodeStack(entryPath(data.world, savedNode, name));
        setLoading(false);
      })
      .catch(() => setLoading(false));
    // Backfill the world's recent past into the feed. The feed renders
    // newest-first and /history returns newest-first; history lines sit
    // below any live events that arrived while the fetch was in flight.
    fetch(withKey(`/history?seed=${s}`))
      .then(r => r.json())
      .then(data => {
        const past = (data.mutations || []).slice(0, MAX_HISTORY)
          .map(m => ({ type: "history", text: describeMutation(m) }));
        if (past.length) {
          setEvents(ev => [...ev, ...past].slice(0, MAX_EVENTS));
        }
      })
      .catch(() => {});
  }, []);

  const currentNodeName = nodeStack[nodeStack.length - 1]?.name;

  const { connected, sendMessage } = useWorldSocket(seed, playerName, {
    // The welcome roster: everyone already present when we connect. Without
    // this, a joining player sees an empty world until someone acts.
    onWelcome: (msg) => {
      const others = (msg.players || [])
        .filter(p => p.session_id !== msg.session_id)
        .map(p => ({ name: p.name, session_id: p.session_id, node: p.node || "" }));
      setPlayers(others);
      const cast = {};
      for (const a of (msg.agents || [])) cast[a.name] = { node: a.node || "", persona: a.persona };
      setAgents(cast);
      if (others.length) {
        pushEvent({ type: "system",
                    text: `${others.length} explorer${others.length > 1 ? "s" : ""} already here` });
      }
    },
    onAgentEnter: (msg) => setAgents(a => ({ ...a, [msg.name]: { node: "", persona: msg.persona } })),
    onAgentMove:  (msg) => setAgents(a => ({ ...a, [msg.name]: { ...(a[msg.name] || {}), node: msg.node } })),
    onAgentLeave: (msg) => setAgents(a => {
      const next = { ...a };
      delete next[msg.name];
      return next;
    }),
    onMoveDenied: (msg) => {
      if (msg.reason === "sealed") {
        // The scene stays on the sealed node — you stand at the threshold;
        // the server keeps your true position outside until the key is
        // spoken (solving the room's puzzle re-sends the move).
        pushEvent({ type: "system",
                    text: `▦ ${msg.node} is sealed — its key is written in ${msg.keeper || "the scale above"}` });
        if (msg.prompt) pushEvent({ type: "system", text: msg.prompt });
      } else {
        pushEvent({ type: "system", text: `✕ no way to ${msg.node} — ${msg.reason}` });
      }
    },
    onPlayerJoin: (msg) => {
      setPlayers(p => [...p, { name: msg.name, session_id: msg.session_id, node: "" }]);
      pushEvent({ type: "system", text: `${msg.name} joined` });
    },
    onPlayerLeave: (msg) => {
      setPlayers(p => {
        const leaving = p.find(x => x.session_id === msg.session_id);
        pushEvent({ type: "system", text: `${leaving?.name ?? "Someone"} left` });
        return p.filter(x => x.session_id !== msg.session_id);
      });
    },
    // Upsert on move: a mover we don't know yet (raced past the roster)
    // must appear, not be silently dropped.
    onPlayerMove: (msg) => setPlayers(p =>
      p.some(x => x.session_id === msg.session_id)
        ? p.map(x => x.session_id === msg.session_id ? { ...x, node: msg.node } : x)
        : [...p, { name: msg.name, session_id: msg.session_id, node: msg.node }]),
    onChat:         (msg) => pushEvent({ type: "chat",   name: msg.name, text: msg.text }),
    // Moderation decline (sender-only): the message reached nobody and was
    // stored nowhere — surface the world's line so it doesn't silently vanish.
    onChatDeclined: (msg) => pushEvent({ type: "system", text: `✕ ${msg.text}` }),
    onCausalEvent:  (msg) => {
      pushEvent({ type: "causal", kind: msg.kind, node: msg.node, strength: msg.strength });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "ripple", strength: msg.strength ?? 1.0,
                        eventKind: msg.kind, duration: 1500 });
      }
    },
    onPuzzleSolved: (msg) => {
      const credit = msg.contributors?.length > 1
        ? ` (with ${msg.contributors.filter(c => c !== msg.solver).join(", ")})`
        : "";
      const by = msg.solver ? ` by ${msg.solver}${credit}` : "";
      pushEvent({ type: "puzzle",
                  text: msg.entangled_with
                    ? `⇄ ${msg.node} resolves — entangled with ${msg.entangled_with}`
                    : `Puzzle solved: ${msg.puzzle} @ ${msg.node}${by}` });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "solve", duration: 2000 });
        // If we were standing at a sealed threshold, the solve is the key —
        // walk through (the effect below re-sends the move once connected).
        setWalkThrough(msg.node);
      }
    },
    onConstellation: (msg) => {
      pushEvent({ type: "puzzle",
                  text: `✦✦ CONSTELLATION — every one of ${msg.node}'s ` +
                        `${msg.children} ${msg.of || "children"} is resolved` +
                        (msg.by ? ` (completed by ${msg.by})` : "") });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "solve", duration: 2500 });
      }
    },
    onAgentDone:      (msg) => pushEvent({ type: "system", text: `Agent visited ${msg.nodes_visited} nodes from ${msg.node}` }),
    onScaleAct: (msg) => {
      pushEvent({ type: "system", text: `✦ ${msg.actor} ${msg.verb}s ${msg.node} — ${msg.flavor}` });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "ripple", strength: 0.8,
                        eventKind: "SCALE_ACT", duration: 1500 });
      }
    },
    onAgentTalk: (msg) => {
      // Two wanderers in conversation — surface the lines like chat, the
      // closing stage direction as ambience.
      for (const l of msg.lines || []) {
        if (l.speaker) pushEvent({ type: "chat", name: l.speaker, text: l.line });
        else pushEvent({ type: "system", text: l.line });
      }
    },
    onAgentEncounter: (msg) => {
      pushEvent({ type: "system", text: `⚡ ${msg.agent1} meets ${msg.agent2} @ ${msg.node}` });
      if (msg.node === currentNodeName) {
        pushTransient({ kind: "encounter",
                        agent1: msg.agent1, agent2: msg.agent2,
                        duration: 1800 });
      }
    },
  });

  // Mount once. First pull any server-side (cross-device) resume into
  // localStorage, then load — so the position follows the player across devices,
  // falling back to this browser's cache when there's no server row.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await hydratePositionFromServer();
      if (cancelled) return;
      if (s != null && s !== seed) setSeed(s);
      loadWorld(s != null ? s : seed);
    })();
    return () => { cancelled = true; };
  }, [loadWorld]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Broadcast our position whenever it changes or we (re)connect, so other
  // players see us where we actually are — including the initial drop-in /
  // resume node, which isn't reached through navigateTo().
  useEffect(() => {
    if (connected && currentNodeName) sendMessage({ type: "move", node: currentNodeName });
  }, [connected, currentNodeName, sendMessage]);

  // Persist the current node so a returning player resumes here next session —
  // locally for this browser, and on the server so it follows them to other
  // devices.
  useEffect(() => {
    if (currentNodeName) {
      localStorage.setItem(LAST_NODE_KEY, currentNodeName);
      savePositionToServer(currentNodeName, seed);
    }
  }, [currentNodeName, seed]);

  // Drop all transients when the player navigates — a leftover ripple from
  // the previous node is meaningless in the new scene.
  useEffect(() => { setTransients([]); }, [currentNodeName]);

  const handleLoadWorld = useCallback((s) => {
    setSeed(s);
    loadWorld(s);
  }, [loadWorld]);

  // A solve at the current node may have opened its seal — re-announce the
  // move so the server's position walks through the now-open door. (The
  // position-broadcast effect won't refire on its own: the node name
  // didn't change.)
  useEffect(() => {
    if (walkThrough && connected && walkThrough === currentNodeName) {
      sendMessage({ type: "move", node: walkThrough });
      setWalkThrough(null);
    }
  }, [walkThrough, connected, currentNodeName, sendMessage]);

  // Position is broadcast by the effect above (keyed on currentNodeName), so
  // navigation only has to update the stack — no direct send here.
  const navigateTo = useCallback((node) => {
    setNodeStack(s => [...s, node]);
  }, []);

  const navigateUp = useCallback(() => {
    setNodeStack(s => (s.length <= 1 ? s : s.slice(0, -1)));
  }, []);

  // Jump to a traveler: rebuild the real ancestry stack from the node name
  // (names encode their path — "…-1121" lies under 1→1→2→1). A traveler
  // below the fetched horizon lands us on their deepest fetched ancestor.
  const jumpTo = useCallback((nodeName) => {
    const root = worldRootRef.current;
    const suffix = (nodeName || "").split("-").pop() || "";
    if (!root || !/^\d+$/.test(suffix)) return;
    const path = [root];
    let cur = root;
    for (const ch of suffix.slice(1)) {   // the leading 1 is the root itself
      const next = (cur.children || [])[Number(ch) - 1];
      if (!next) break;                   // deeper than this view reaches
      path.push(next);
      cur = next;
    }
    if (cur.name !== nodeName) {
      pushEvent({ type: "system",
                  text: `▼ ${nodeName} lies enfolded beneath ${cur.name}` });
    }
    setNodeStack(path);
  }, [pushEvent]);

  const sendChat = useCallback((text) => {
    sendMessage({ type: "chat", text });
  }, [sendMessage]);

  const currentNode = nodeStack[nodeStack.length - 1] ?? null;

  // Ambient sound: each place hums its own deterministic tone
  // (static/nodesound.js). The toggle click is the activation gesture
  // browsers require for audio.
  const toggleSound = useCallback(() => {
    if (!ambienceRef.current) ambienceRef.current = new NodeAmbience();
    const amb = ambienceRef.current;
    const node = nodeStack[nodeStack.length - 1];
    if (amb.enabled) { amb.disable(); setSoundOn(false); }
    else { amb.enable(seed, node); setSoundOn(true); }
  }, [seed, nodeStack]);

  useEffect(() => {
    if (soundOn && ambienceRef.current && currentNode) {
      ambienceRef.current.setNode(seed, currentNode);
    }
  }, [soundOn, seed, currentNode]);

  if (!introSeen) {
    return <Intro onBegin={() => {
      localStorage.setItem(INTRO_SEEN, "1");
      setIntroSeen(true);
    }} />;
  }

  if (!playerName) {
    return <NameEntry onSubmit={(name) => { localStorage.setItem(NAME_KEY, name); setPlayerName(name); }} />;
  }

  if (loading || !currentNode) {
    return <div style={s.loading}>Generating world…</div>;
  }

  return (
    <div style={s.layout}>
      <SceneView
        node={currentNode}
        players={players}
        transients={transients}
        onNavigate={navigateTo}
        onNavigateUp={navigateUp}
        canGoUp={nodeStack.length > 1}
        seed={seed}
      />
      <TextPanel
        node={currentNode}
        players={players}
        agents={agents}
        connected={connected}
        events={events}
        seed={seed}
        depth={WORLD_DEPTH}
        playerName={playerName}
        onLoadWorld={handleLoadWorld}
        onChat={sendChat}
        onJump={jumpTo}
        soundOn={soundOn}
        onToggleSound={toggleSound}
      />
    </div>
  );
}

function Intro({ onBegin }) {
  return (
    <div style={s.nameWrap}>
      <div style={{ ...s.nameBox, maxWidth: 420, textAlign: "left" }}>
        <div style={s.nameTitle}>Enfolded</div>
        <div style={s.introBody}>
          A living multiverse of eleven nested scales — from the whole cosmos
          down to a single particle. It was here before you arrived, and it
          will keep moving after you leave.
        </div>
        <ul style={s.introList}>
          <li style={s.introItem}><b style={s.introVerb}>Explore</b> — step through the passages; every place contains worlds.</li>
          <li style={s.introItem}><b style={s.introVerb}>Speak</b> — talk to any place. It answers in character, and it remembers.</li>
          <li style={s.introItem}><b style={s.introVerb}>Solve</b> — crack a node's puzzle; the ripple settles places far above and below.</li>
        </ul>
        <button onClick={onBegin} style={{ ...s.nameButton, alignSelf: "flex-start" }}>Begin</button>
      </div>
    </div>
  );
}

function NameEntry({ onSubmit }) {
  const [value, setValue] = useState("");
  const submit = () => {
    const trimmed = value.trim().slice(0, 32);
    if (trimmed) onSubmit(trimmed);
  };
  return (
    <div style={s.nameWrap}>
      <div style={s.nameBox}>
        <div style={s.nameTitle}>Enfolded</div>
        <div style={s.nameDesc}>Choose a name for your explorer</div>
        <input
          autoFocus
          type="text"
          maxLength={32}
          placeholder="Your name"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          style={s.nameInput}
        />
        <button onClick={submit} style={s.nameButton}>Enter</button>
      </div>
    </div>
  );
}

const s = {
  layout:  { display: "flex", height: "100vh", overflow: "hidden", background: "#07080f" },
  loading: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontSize: "1.1rem", color: "#4a5580", fontFamily: "Courier New, monospace" },
  nameWrap: { display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#07080f", fontFamily: "Courier New, monospace" },
  nameBox: { background: "#0d1020", border: "1px solid #2a4060", padding: "32px 28px", minWidth: 320, textAlign: "center" },
  nameTitle: { fontSize: "1.1rem", color: "#3a8eff", letterSpacing: "2px", marginBottom: 8 },
  nameDesc: { fontSize: "0.85rem", color: "#6a7090", marginBottom: 18 },
  nameInput: { width: "100%", background: "#07080f", border: "1px solid #2a4060", color: "#b0bcd0", padding: "8px 10px", fontFamily: "inherit", fontSize: "0.9rem", marginBottom: 12, outline: "none" },
  nameButton: { background: "#1a3060", border: "1px solid #3a8eff", color: "#b0bcd0", padding: "8px 22px", fontFamily: "inherit", fontSize: "0.9rem", cursor: "pointer" },
  introBody: { fontSize: "0.85rem", color: "#7a9ab8", lineHeight: 1.6, marginBottom: 14 },
  introList: { listStyle: "none", margin: "0 0 18px", padding: 0, display: "flex", flexDirection: "column", gap: 8 },
  introItem: { fontSize: "0.78rem", color: "#5a7090", lineHeight: 1.5 },
  introVerb: { color: "#8aaccc" },
};

# hello-nested-worlds-adventure

**A nested simulation playground where procedural worlds, autonomous agents, and escape-room-style puzzles converge.**

This project is an experimental platform for building and exploring multiverse-scale simulations — where each layer, from galaxies to subatomic particles, is procedurally generated and enriched with metadata for emergent behavior, agent decision-making, and narrative depth.

---

## 🌌 Core Concept

At its heart, this is a **choose-your-own-adventure simulation engine** built atop a **recursive multiverse hierarchy**. It blends:

- **Procedural content generation** (PCG) across multiple scales  
- **Agent-based behavior** driven by local node metadata  
- **Escape-room and puzzle-style mechanics**  
- **Narrative scaffolding** for emergent storytelling  

---

## 🧱 Current Architecture

### 🧭 Spatial Hierarchy

The simulation spans 10 nested levels:

```
Multiverse → Universe → Galaxy → Planet → Region → Room → Object → Molecule → Atom → SubatomicParticle
```

Each node in this hierarchy is represented by a `SpatialNode` object with:

- A unique name and level  
- A set of **children** (recursively generated)  
- A **properties** dictionary with level-specific metadata (e.g. `gravity`, `has_puzzle`, `element`)  

---

## 🧬 Procedural Generation

A deterministic, seed-based generator builds the hierarchy using:

- Breadth and depth controls  
- Randomized property templates per level  
- Extensible logic to add new levels, metadata, or behaviors  

---

## 🚧 Development Phases

| Phase      | Description                                                           | Status     |
|------------|-----------------------------------------------------------------------|------------|
| Phase 1    | Scaffold spatial hierarchy and generator                              | ✅ Complete |
| Phase 1.5  | Add metadata to each node (e.g. `gravity`, `element`)                 | ✅ Complete |
| Phase 2    | Introduce autonomous agents with basic state machines                 | 🔜 Next     |
| Phase 3    | Puzzle engine with escape-room logic and decision trees               | ⏳ Planned  |
| Phase 4    | UX interface (CLI/TUI), save/load support, testing framework          | ⏳ Planned  |

---

## 🤖 What’s Next (Phase 2)

We're building an **Agent System** with:

- Finite state machines (FSMs): `Idle → Explore → Interact → Exit`  
- Decision-making based on node metadata (e.g. avoid `danger_level > 5`)  
- Simulated traversal and logging  
- Hooks for future puzzle-solving and story arcs  

---

## 🔧 Project Structure

```
hello-nested-worlds-adventure/
├── main.py                    # CLI preview of worldgen output
├── multiverse/
│   ├── __init__.py
│   ├── node.py                # SpatialNode class
│   └── generator.py           # PCG logic + metadata generation
├── agents/                    # (Coming soon) Agent logic
├── puzzles/                   # (Coming soon) Puzzle engine
├── docs/
│   └── CHANGELOG.md           # Project evolution log
└── README.md
```

---

## 🧠 Philosophy

This project is:
- A **sandbox** for tinkering with agents, logic, and procedural systems  
- A **toolkit** for simulating recursive systems across space and scale  
- A **canvas** for interactive storytelling, education, and experimentation  

---

## 💡 Contributing

We're early, but open to collaboration. Areas of interest:
- Agent design and behavioral logic  
- Puzzle frameworks and challenge design  
- Procedural generation, compression, and entropy modeling  
- Game design, UX/TUI, or narrative design  

Feel free to open issues, fork the repo, or suggest improvements.

---

## 📜 License

MIT (subject to update once we open source officially)

---

## 🌱 Author

**Mark Weeks**  
[markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io)  
AI + SaaS + Simulation + Storytelling

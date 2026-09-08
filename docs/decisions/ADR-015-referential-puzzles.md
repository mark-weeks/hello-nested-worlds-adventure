# ADR-015: Referential Puzzles Within the World's Puzzle Ecology

**Status:** Proposed (owner-requested content direction), 2026-09-07;
pending development-team review and ratification. Implementation pending.
The owner requested occasional puzzles drawing on relevant fictional and
nonfictional knowledge. The authoring and release criteria below formalize the
recommendation; no puzzle bank, active puzzle, or golden pin changes here.

## Context

Enfolded's themes support references to computing, mathematics, scientific
ideas, and speculative fiction. Recognition can make the world feel connected
to a larger intellectual history. Unrelated trivia or a requirement for prior
cultural knowledge could instead replace investigation with recall or web search.

The owner supplied the example, "What is the answer to the Ultimate Question
of Life, the Universe, and Everything?", with answer `42`, referencing
The Hitchhiker's Guide to the Galaxy. Other suggested answers were Ada Lovelace,
qubit, recursion, imaginary number, exponential, and stack overflow.

## Decision

Include **occasional, curated referential puzzles**, with relevant fictional
and nonfictional material. A direct trivia question is allowed as an optional
discovery; it does not have to masquerade as a causal simulation puzzle.

Prefer references that help players notice a relationship, interpret an artifact,
or understand a scale. An in-world fragment can present the reference without
claiming that external fictional events are literal facts of Enfolded's canon.
Maintain the distinction between documented real-world facts and fictional lore.

| Owner-supplied answer concept | Candidate setting or connection; not a finished puzzle |
|---|---|
| `42` | A literary echo or archived question associated with cosmic meaning. |
| `Ada Lovelace` | A historical computing reference around an engine, notation, or preserved correspondence. |
| `qubit` | A quantum-information reference near the small-scale register. |
| `recursion` | A self-reference or nested-structure investigation. |
| `imaginary number` | A mathematical artifact or relation whose interpretation supplies the clue. |
| `exponential` | A pattern of change, specified clearly enough to distinguish growth from an arbitrary number sequence. |
| `stack overflow` | A computing reference involving nested calls; distinguish the phenomenon from the similarly named website. |

### Fairness and authoring contract

- Begin with optional references; unfamiliarity must not block the first
  experience or the only route to a core shared outcome. A progression-bearing
  reference needs an investigable in-world route to infer the answer without
  requiring external browsing or familiarity with a particular culture.
- Hints can explain relationships, provenance, and vocabulary progressively;
  preserve the existing no-answer-leak contract for prompts, hints, and served
  puzzle properties. Do not put the literal accepted answer into a hint field.
- Author a verified source record, intended answer, accepted aliases,
  normalization rules, relevance, ambiguity checks, difficulty, and definition
  version. Check factual claims against authoritative sources when writing the
  actual question; these candidate concepts are not a sourced production bank.
- Validate names, numbers, and phrases server-side. For example, deciding
  whether `forty-two` and `42` are equivalent is a deliberate alias policy,
  not a runtime model judgment. Do not accept a semantically different answer
  because an LLM finds it plausible.
- Prefer short references and original wording to copied passages. Source
  metadata supports verification and a spoiler-safe reveal after resolution;
  it must not leak answers through the unsolved client payload.
- Difficulty remains per-node. Trivia familiarity is not a substitute for
  assessing difficulty, and a deeper scale does not justify a harder question.

### Release boundary

Prototype a small authored selection before building a general trivia generator.
Track direct-recall content honestly in the ecology audit: a question does not
become world-reading merely because its narrator is a node. Retain the current
ecology gates; set any new family's allocation after novelty, ambiguity, and
solvability checks. Do not silently alter active puzzles or relabel metrics to
pass those gates. Roll out through versioned future instances/renewals under
ADR-013, with an explicit compatibility plan and any necessary pin review.

## Trade-offs accepted

Recognition rewards prior knowledge unevenly. Optional placement, contextual
clues, varied sources, and newcomer testing reduce that cost without removing
the pleasure of recognizing a reference. Curated content costs authoring time
but is more reliable than unverified generated trivia and ambiguous answers.

## Revisit when…

- Players rely mostly on external search or find references exclusionary:
  revise clues, selection, and placement before increasing the proportion.
- Referential questions crowd out causal/world-reading discoveries: reduce
  their allocation or connect them to an actual investigation.
- New authoring introduces language-dependent aliases: test explicit locale
  behavior rather than broadening acceptance with an unbounded model judge.

## Rejected alternatives

- External trivia as a universal gate or replacement for the existing ecology.
- Unverified runtime trivia generation or live web lookup to decide correctness.
- Changing all existing puzzle answers on deployment or exposing their source
  answer keys in public puzzle metadata.

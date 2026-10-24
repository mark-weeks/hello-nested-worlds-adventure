# Coding-agent setup and verification

Start Codex, Claude Code, or GitHub Copilot in the Git checkout root or inside it.
Opening a wrapper directory above the checkout does not reliably discover the
repository's instructions or skills.

## Shared instructions and skills

- `AGENTS.md` is the shared engineering contract; `CLAUDE.md` imports it with
  `@AGENTS.md`. Edit shared rules in `AGENTS.md`.
- The three procedures remain in `.claude/skills/<name>/SKILL.md`, with their
  existing names, descriptions, and rules. Edit these source files.
- `.agents/skills/<name>` is a relative directory symlink to the matching
  `.claude/skills/<name>`. This exposes the same procedures to Codex's native
  skill discovery without maintaining duplicate bodies or metadata.
- Codex supports symlinked skill directories. Claude Code retains its native
  `.claude/skills` directory. Copilot CLI supports both locations and chooses
  the first match for a name. Do not create another same-named skill copy.

The skills are `changelog-entry`, `irreversibility-check`, and `repin-goldens`.
Their descriptions are available for selection; full procedures are needed only
when applicable. The explicit task pointers in `AGENTS.md` also remain usable.

Git must preserve the links for Codex's native discovery. On Windows, check out
with symlink support enabled and the required OS permission (Developer Mode or
Administrator). A checkout with `core.symlinks=false` stores link targets as
plain text, so these aliases will not work. The ordinary `.claude/skills` source
files and `AGENTS.md` pointers remain readable; do not report native discovery
as verified on that checkout.

Copilot support depends on the surface. CLI, VS Code chat, the cloud agent, and
GitHub.com code review document `AGENTS.md` support. This setup does not add a
`.github/copilot-instructions.md` for surfaces that require that filename.

## Design routing

For interface, interaction, accessibility, or scene styling, `AGENTS.md` points
to [visual language](../design/visual-language.md) and
[game design](../design/game-design.md). For scene-image generation or delivery,
also consult [the beta scene-art strategy](../design/beta-scene-art.md).
Keep their current implementation/proposal status; the route does not ratify
planned work or replace the world covenants. Backend-only work does not require
loading these documents.

## Repeatable verification

After changing instruction or skill routing:

1. Check that `CLAUDE.md` still contains only `@AGENTS.md` plus a newline, each
   skill alias resolves inside this checkout to its matching source directory,
   and the skill frontmatter and Markdown links are valid.
2. Inspect native discovery in a fresh session from the root and a subdirectory.
   Codex's app-server `skills/list` exposes names, paths, enabled state, and errors.
   Copilot CLI provides `copilot skill list --json`. In Claude Code, inspect the
   skill picker and `/context`. Expect each repository skill once. A resolved
   path under `.claude/skills` is normal when Codex follows the alias.
3. Run the [behavior scenarios](../evaluation/agent-instruction-scenarios.md)
   in fresh sessions. Keep the evaluator's expected outcomes out of the prompt.
   Restrict the session to reading relevant instructions, skills, and design
   documents; do not perform the hypothetical mutations or publish anything.
4. Review both the response and tool trace. Record selected/read skills, document
   routing, permission decisions, checks proposed, version/model, and failures.
   A model's claim that a skill was loaded is weaker evidence than a discovery
   result or observed file/skill read.

Record actual results under `docs/evaluation/`. Authentication failures and
unavailable environments are blocked checks, not passes. These small scenarios
test routing and decisions; they do not establish coding success rates, latency,
cost improvements, or universal adherence. Existing merge gates still apply.

## Vendor references

- [Codex skill discovery and symlinks](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code skill locations](https://code.claude.com/docs/en/skills#choose-where-skills-load)
- [Claude's shared-file import](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools)
- [Copilot CLI skill discovery and precedence](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#skill-locations)
- [Copilot instruction support by surface](https://docs.github.com/en/copilot/reference/custom-instructions-support)

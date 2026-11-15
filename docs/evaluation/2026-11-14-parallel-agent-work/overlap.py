#!/usr/bin/env python3
"""Recompute the figures in docs/evaluation/2026-11-14-parallel-agent-work.md.

Reads two snapshots taken on 2026-11-14 and prints every count the record cites.
It needs no network and no git history.

    python docs/evaluation/2026-11-14-parallel-agent-work/overlap.py

prs.json            pull requests #111-#173: authoring agent (from the branch prefix),
                    created and merged times (GitHub), and the files each changed
                    (git, merge commit against its first parent; open pull requests
                    against their merge base with main).
review_sample.json  22 of those pull requests: who reviewed, how many findings each
                    reviewer stated, and whether Copilot reviewed the last commit.
"""
import collections
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENTS = ("claude", "codex", "grok")

# The three documents only the status pull request writes under the adopted rule.
STATUS = {
    "docs/CHANGELOG.md",
    "docs/roadmap/README.md",
    "docs/roadmap/beta-launch-checklist.md",
}
# Files left out of the layer replay because every concern writes them.
SHARED = {"server/handlers.py", "main.py", "server/guard.py", ".env.example",
          "tests/conftest.py", "README.md"}
RULES = {"AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "LICENSE", "NOTICE",
         "THIRD_PARTY_NOTICES.txt"}
RUNTIME_SERVER = {"server/__init__.py", "server/intervention_api.py", "server/ideas_api.py"}
INTEGRITY_ELSEWHERE = {"consciousness/honesty.py", "scripts/beta_metrics.py"}
PACKAGING = {"Dockerfile", "fly.toml", "pyproject.toml", "requirements.lock",
             "requirements-dev.lock", "setup.sh"}
HOME = {"codex": "client", "grok": "runtime", "claude": "integrity"}


def layer(path):
    """Layer a file falls in under the candidate split, or None when it is left out."""
    top = path.split("/")[0]
    if path in SHARED or path in RULES or top in ("tests", "docs", ".claude", ".agents"):
        return None
    if top in ("frontend", "static", "interface"):
        return "client"
    if path in RUNTIME_SERVER:
        return "runtime"
    if top == "server" or path in INTEGRITY_ELSEWHERE or path in ("content_screen.py",
                                                                  "merge_patch.py"):
        return "integrity"
    if top in ("persistence", "puzzles", "causality", "multiverse", "agents"):
        return "integrity"
    if top in ("consciousness", "evals", "scripts", ".github") or path in PACKAGING:
        return "runtime"
    return None


def is_code(path):
    return not (path.startswith("docs/") or path in ("README.md", ".env.example"))


def main():
    prs = {int(number): pr for number, pr in
           json.loads((HERE / "prs.json").read_text(encoding="utf-8")).items()}
    merged = {n: pr for n, pr in prs.items() if pr["merged"]}
    by_agent = collections.Counter(pr["agent"] for pr in prs.values())
    print(f"pull requests: {len(prs)} ({len(merged)} merged, {len(prs) - len(merged)} open); "
          + ", ".join(f"{agent} {by_agent[agent]}" for agent in AGENTS))

    print("\n== share of the merged pull requests that changed each file ==")
    touched = collections.Counter(path for pr in merged.values() for path in pr["files"])
    for path, count in touched.most_common(8):
        print(f"  {count:3d} of {len(merged)}  {100 * count // len(merged):3d}%  {path}")

    print("\n== writers of selected files (merged pull requests) ==")
    for path in ("server/handlers.py", "main.py", "consciousness/runtime.py",
                 "server/__init__.py", "evals/harness.py", "server/observability.py",
                 "consciousness/honesty.py", "persistence/sanctions.py"):
        counts = collections.Counter(pr["agent"] for pr in merged.values()
                                     if path in pr["files"])
        print(f"  {path:28s} " + "  ".join(f"{agent} {counts[agent]}" for agent in AGENTS))

    print("\n== share of each agent's file changes by layer (merged, layered files only) ==")
    for agent in AGENTS:
        layers = collections.Counter(layer(path) for pr in merged.values()
                                     if pr["agent"] == agent for path in pr["files"])
        layers.pop(None, None)
        total = sum(layers.values())
        print(f"  {agent:7s} " + "  ".join(
            f"{name} {100 * layers[name] // total}%" for name in ("client", "runtime", "integrity")))

    print("\n== layer replay: client / runtime / integrity, all 63 ==")
    code = own = single = 0
    for agent in AGENTS:
        agent_code = agent_own = agent_single = 0
        for pr in prs.values():
            if pr["agent"] != agent:
                continue
            layers = {layer(path) for path in pr["files"]} - {None}
            if not layers:
                continue
            agent_code += 1
            agent_single += len(layers) == 1
            agent_own += layers == {HOME[agent]}
        print(f"  {agent:7s} changed layered code in {agent_code:2d}: "
              f"{agent_single:2d} touched one layer, {agent_own:2d} only the author's own")
        code, own, single = code + agent_code, own + agent_own, single + agent_single
    print(f"  total   {code} pull requests changed layered code: {single} touched one "
          f"layer, {own} only the layer the split gives their author")

    print("\n== pull requests from different agents open at the same time ==")
    pairs = status_pairs = changelog_pairs = code_pairs = 0
    shared_code = collections.Counter()
    same_agent = same_agent_code = 0
    for a, b in itertools.combinations(sorted(prs), 2):
        one, two = prs[a], prs[b]
        if not (one["created"] < (two["merged"] or "9") and two["created"] < (one["merged"] or "9")):
            continue
        common = set(one["files"]) & set(two["files"])
        common_code = {path for path in common if is_code(path)}
        if one["agent"] == two["agent"]:
            same_agent += 1
            same_agent_code += bool(common_code)
            continue
        pairs += 1
        status_pairs += bool(common & STATUS)
        changelog_pairs += "docs/CHANGELOG.md" in common
        code_pairs += bool(common_code)
        shared_code.update(common_code)
    print(f"  pairs: {pairs}; sharing docs/CHANGELOG.md: {changelog_pairs}; sharing any of "
          f"the three status documents: {status_pairs}; sharing a code or test file: {code_pairs}")
    print("  code or test files shared most often: "
          + ", ".join(f"{path} ({count})" for path, count in shared_code.most_common(4)))
    print(f"  same-agent pairs open together: {same_agent}; sharing a code or test file: "
          f"{same_agent_code}")
    events = sorted([(pr["created"], 1) for pr in prs.values()]
                    + [(pr["merged"], -1) for pr in prs.values() if pr["merged"]])
    peak = current = 0
    for _, step in events:
        current += step
        peak = max(peak, current)
    print(f"  most pull requests open at once: {peak}")

    sample = json.loads((HERE / "review_sample.json").read_text(encoding="utf-8"))
    print(f"\n== review sample: {len(sample)} pull requests ==")
    totals = collections.defaultdict(collections.Counter)
    for pr in sample:
        for review in pr["reviewers"]:
            total = totals[review["reviewer"]]
            total["prs"] += 1
            total["rounds"] += review["rounds"]
            total["findings"] += review["findings"]
            total["none"] += review["findings"] == 0
    for reviewer, total in sorted(totals.items(), key=lambda item: -item[1]["prs"]):
        print(f"  {reviewer:15s} reviewed {total['prs']:2d}, {total['rounds']:2d} rounds, "
              f"{total['findings']:3d} findings ({total['findings'] / total['prs']:.1f} per pull "
              f"request), none on {total['none']}")
    stale = sum(not pr["copilot_saw_last_commit"] for pr in sample)
    print(f"  Copilot's last review was of an earlier commit than the last one on {stale} "
          f"of {len(sample)}")
    reviewers = collections.Counter(len(pr["reviewers"]) for pr in sample)
    print("  reviewers per pull request: "
          + ", ".join(f"{count} with {n}" for n, count in sorted(reviewers.items())))
    deep = [pr for pr in sample if pr["depth"] == "threads"]
    copilot = [review for pr in deep for review in pr["reviewers"]
               if review["reviewer"] == "copilot"]
    others = [review for pr in deep for review in pr["reviewers"]
              if review["reviewer"] != "copilot"]
    for label, group in (("Copilot", copilot), ("agent reviewers", others)):
        print(f"  read thread by thread ({len(deep)} pull requests), {label}: "
              f"{sum(r['findings'] for r in group)} findings, "
              f"{sum(r['fixed'] for r in group)} fixed, "
              f"{sum(r['substantive'] for r in group)} substantive, "
              f"{sum(r['wrong'] for r in group)} shown wrong")


if __name__ == "__main__":
    main()

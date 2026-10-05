"""Evidence summaries, blinded review packets and paired task comparisons."""
from __future__ import annotations

import math
from pathlib import Path
import random
import secrets
import statistics

from evals.harness import ROOT, TASKS, digest, read_json, validate_brief, write_json


def checked_run(path):
    run = read_json(path)
    signature = run.pop("run_sha256", None)
    if signature != digest(run) or run.get("status") not in ("completed", "budget_stopped"):
        raise ValueError("run is incomplete or its contents have changed")
    run["run_sha256"] = signature
    return run


def review_packet(run, corpus, directory):
    if digest(corpus) != run["corpus_sha256"]:
        raise ValueError("review corpus differs from the run")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    directory.chmod(0o700)
    rubric = read_json(ROOT / "evals/rubric.json")
    if digest(rubric) != run["rubric_sha256"]:
        raise ValueError("review rubric differs from the run")
    cases = {c["id"]: c for c in corpus["cases"]}
    items, mapping = [], {}
    for trial in run["trials"]:
        if not trial["grade"]["human_required"]:
            continue
        key = secrets.token_hex(8)
        mapping[key] = trial["id"]
        case = cases[trial["case_id"]]
        items.append({"id": key, "task": trial["task"],
                      "context": {k: v for k, v in case.items() if k in
                                  ("node", "persona", "agent_name", "history", "agent_memory",
                                   "speaker", "ripple_score", "hinge", "messages", "rubric_notes")},
                      "outputs": trial["outputs"],
                      "critical_violation": None,
                      "scores": dict.fromkeys(rubric["dimensions"]), "notes": ""})
    random.SystemRandom().shuffle(items)
    packet = {"schema_version": 1, "packet_id": secrets.token_hex(16),
              "rubric": rubric, "reviewer": "", "kind": "human", "items": items}
    # Keep this key away from the reviewer until scores are sealed.
    write_json(directory / "key.json", {"packet_id": packet["packet_id"],
               "run_sha256": run["run_sha256"], "items": mapping,
               "content_sha256": {i["id"]: digest({k: i[k] for k in ("task", "context", "outputs")})
                                  for i in items}})
    write_json(directory / "review.json", packet)
    return packet


def load_review(run, review_path=None, key_path=None, *, allow_model=False):
    if review_path is None:
        return {}
    if key_path is None:
        raise ValueError("review requires its mapping key")
    review, key = read_json(review_path), read_json(key_path)
    if (key.get("run_sha256") != run["run_sha256"] or
            key.get("packet_id") != review.get("packet_id") or
            digest(review.get("rubric")) != run["rubric_sha256"]):
        raise ValueError("review/key/run/rubric mismatch")
    if not review.get("reviewer", "").strip() or review.get("kind") not in (
            ("human", "model") if allow_model else ("human",)):
        raise ValueError("a named human reviewer is required; model scores are calibration-only")
    expected = {t["id"] for t in run["trials"] if t["grade"]["human_required"]}
    if set(key["items"].values()) != expected or len(key["items"]) != len(expected):
        raise ValueError("mapping must cover every voice trial once")
    dimensions = review["rubric"]["dimensions"]
    grades, seen = {}, set()
    for item in review["items"]:
        if item["id"] in seen or item["id"] not in key["items"]:
            raise ValueError("duplicate or unknown review item")
        seen.add(item["id"])
        if digest({k: item[k] for k in ("task", "context", "outputs")}) != key["content_sha256"][item["id"]]:
            raise ValueError("reviewed context or output was changed")
        scores = item.get("scores", {})
        if set(scores) != set(dimensions) or any(v is not None and (type(v) is not int or not 1 <= v <= 5)
                                               for v in scores.values()):
            raise ValueError("each dimension needs a 1–5 score or null")
        if item.get("critical_violation") is not None and type(item["critical_violation"]) is not bool:
            raise ValueError("critical_violation must be true, false or null")
        complete = item.get("critical_violation") is not None and all(v is not None for v in scores.values())
        if complete and not item.get("notes", "").strip():
            raise ValueError("completed grades require evidence notes")
        grades[key["items"][item["id"]]] = {
            "success": (not item["critical_violation"] and min(scores.values()) >= 3) if complete else None,
            "critical_violation": item.get("critical_violation"), "scores": scores,
            "reviewer": review["reviewer"], "kind": review["kind"]}
    if seen != set(key["items"]):
        raise ValueError("missing review items; leave unknown scores null instead of deleting items")
    return grades


def success(trial, human):
    if not trial["grade"]["valid_completion"] or trial["grade"]["task_correct"] is False:
        return False
    if trial["grade"]["human_required"]:
        return human.get(trial["id"], {}).get("success")
    return trial["grade"]["task_correct"]


def percentile(values, percentile):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * percentile) - 1)]


def wilson(passed, total):
    if not total:
        return None
    z = 1.96
    p = passed / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(center - spread, 4), round(center + spread, 4)]


def summarize(run, human=None):
    human = human or {}
    tasks = {}
    for task in TASKS:
        trials = [t for t in run["trials"] if t["task"] == task]
        if not trials:
            continue
        verdicts = [success(t, human) for t in trials]
        calls = [c for t in trials for c in t["calls"]]
        known_cost = all(c["cost_usd"] is not None for c in calls)
        cost = sum(c["cost_usd"] for c in calls) if known_cost else None
        by_case = {}
        for trial, verdict in zip(trials, verdicts):
            by_case.setdefault(trial["case_id"], []).append(verdict)
        complete_cases = [v for v in by_case.values() if len(v) == run["repeats"] and None not in v]
        stable_passes = sum(all(v) for v in complete_cases)
        categories = {}
        for t, verdict in zip(trials, verdicts):
            counts = categories.setdefault(t["category"], {"pass": 0, "fail": 0, "unknown": 0})
            counts["unknown" if verdict is None else "pass" if verdict else "fail"] += 1
        cache_reads = [c["response"]["usage"]["cache_read_tokens"] for c in calls
                       if c["response"] and c["response"]["usage"] and
                       c["response"]["usage"]["cache_read_tokens"] is not None]
        quality = [statistics.mean(human[t["id"]]["scores"].values()) for t in trials
                   if human.get(t["id"], {}).get("success") is not None]
        tasks[task] = {"trials": len(trials), "passed": verdicts.count(True),
            "failed": verdicts.count(False), "unknown": verdicts.count(None),
            "critical_failures": sum(t["critical"] and v is False or
                                     human.get(t["id"], {}).get("critical_violation") is True
                                     for t, v in zip(trials, verdicts)),
            "cases_complete": len(complete_cases), "cases_passing_every_repeat": stable_passes,
            "case_consistency_wilson_95": wilson(stable_passes, len(complete_cases)),
            "p50_ms": statistics.median(t["latency_ms"] for t in trials),
            "p95_ms": percentile([t["latency_ms"] for t in trials], .95),
            "cost_usd": cost,
            "quality_mean": statistics.mean(quality) if len(quality) == len(trials) else None,
            "cost_per_success_usd": cost / verdicts.count(True) if cost is not None and
                verdicts.count(True) and None not in verdicts and run["status"] == "completed" else None,
            "calls": len(calls), "transport_errors": sum(c["error"] is not None for c in calls),
            "unknown_cost_calls": sum(c["cost_usd"] is None for c in calls),
            "cache_read_observations": len(cache_reads), "cache_hit_calls": sum(x > 0 for x in cache_reads),
            "categories": categories,
            "screen_failures": sum(t["grade"]["screen_correct"] is False for t in trials),
            "classifier_false_blocks": sum(t["task"] == "moderation" and t["expected"]["allowed"]
                and bool(t["outputs"]) and t["outputs"][0]["allowed"] is False for t in trials),
            "classifier_misses": sum(t["task"] == "moderation" and not t["expected"]["allowed"]
                and bool(t["outputs"]) and t["outputs"][0]["allowed"] is True for t in trials),
            "resolved_models": sorted({c["response"]["resolved_model"] for c in calls
                                      if c["response"] and c["response"].get("resolved_model")}),
            "unknown_resolved_model_calls": sum(not c["response"] or not c["response"].get("resolved_model")
                                                for c in calls)}
    return {"run_sha256": run["run_sha256"], "evidence": run["evidence"],
            "status": run["status"], "split": run["split"], "tasks": tasks}


def report(run, human=None):
    summary = summarize(run, human)
    lines = ["# Model evaluation evidence", "",
             f"Evidence: **{run['evidence']}**. Run status: **{run['status']}**. Split: **{run['split']}**.",
             "No provider/model is selected or approved by this report.", "",
             "| Task | Pass / fail / unknown | Consistent cases | p50 / p95 ms | USD / success | Screen failures |",
             "|---|---|---|---|---|---|"]
    for task, s in summary["tasks"].items():
        cost = "unknown" if s["cost_per_success_usd"] is None else f"{s['cost_per_success_usd']:.6f}"
        lines.append(f"| {task} | {s['passed']} / {s['failed']} / {s['unknown']} | "
                     f"{s['cases_passing_every_repeat']} / {s['cases_complete']} | "
                     f"{s['p50_ms']:.1f} / {s['p95_ms']:.1f} | {cost} | "
                     f"{s['screen_failures'] if task == 'moderation' else 'n/a'} |")
    lines += ["", "Fixture latency, cost and authored replies are plumbing evidence only.",
              "Unknown human grades and unknown usage never count as a pass or as zero cost.",
              "Consistency intervals in summary.json use scenario counts, not correlated repeat counts;",
              "this authored corpus is not a random population sample. Small tails are descriptive only.",
              "Latency covers the task call and validation; HTTP, queueing, concurrent load and player behavior remain unmeasured.",
              "Cache observations describe this run order; they do not prove cold/warm traffic economics.", "",
              f"Candidate: `{run['candidate']['id']}`; corpus `{run['corpus_version']}`; repeats {run['repeats']}.",
              f"Source commit: `{run['provenance']['commit']}`; dirty: {run['provenance']['dirty']}.",
              f"Run SHA-256: `{run['run_sha256']}`."]
    return "\n".join(lines) + "\n", summary


def compare(baseline, candidate, baseline_human=None, candidate_human=None):
    for field in ("corpus_sha256", "rubric_sha256", "split", "repeats", "selection_brief"):
        if baseline[field] != candidate[field]:
            raise ValueError(f"comparison mismatch: {field}")
    if set(baseline["case_ids"]) != set(candidate["case_ids"]):
        raise ValueError("comparison requires the same cases")
    if baseline["status"] != "completed" or candidate["status"] != "completed":
        raise ValueError("partial runs cannot support a paired comparison")
    left = {t["id"]: t for t in baseline["trials"]}
    right = {t["id"]: t for t in candidate["trials"]}
    if (set(left) != set(right) or len(left) != baseline["planned_trials"] or
            len(right) != candidate["planned_trials"] or len(left) != len(baseline["trials"]) or
            len(right) != len(candidate["trials"])):
        raise ValueError("missing or duplicate trials")
    result = {"baseline": baseline["run_sha256"], "candidate": candidate["run_sha256"],
              "evidence": "live" if baseline["evidence"] == candidate["evidence"] == "live" else "fixture-involved",
              "source_changed": baseline["provenance"]["source_bundle_sha256"] !=
                                candidate["provenance"]["source_bundle_sha256"],
              "decision": "human decision required", "tasks": {}}
    for task in TASKS:
        pairs = [(success(left[k], baseline_human or {}), success(right[k], candidate_human or {}))
                 for k in left if left[k]["task"] == task]
        if not pairs:
            continue
        result["tasks"][task] = {
            "candidate_wins": sum(a is False and b is True for a, b in pairs),
            "baseline_wins": sum(a is True and b is False for a, b in pairs),
            "ties": sum(a is not None and a == b for a, b in pairs),
            "unknown_pairs": sum(a is None or b is None for a, b in pairs)}
    result["baseline_summary"] = summarize(baseline, baseline_human)
    result["candidate_summary"] = summarize(candidate, candidate_human)
    result["selection_checks"] = selection_checks(baseline, candidate, result)
    return result


def selection_checks(baseline, candidate, comparison):
    """Predeclared screens support review; they never select or deploy a model."""
    reasons = []
    brief = candidate.get("selection_brief")
    try:
        validate_brief(brief, comparison["tasks"])
    except ValueError as exc:
        return {"status": "insufficient evidence", "reasons": [str(exc)]}
    if comparison["evidence"] != "live":
        reasons.append("fixture evidence cannot qualify a candidate")
    if candidate["split"] != "holdout":
        reasons.append("held-out decision evidence is missing")
    if candidate["repeats"] < brief["minimum_repeats"]:
        reasons.append("too few repeats")
    if comparison["source_changed"]:
        reasons.append("source changed: treat as a system experiment, not a model-only comparison")
    if not brief.get("calibration_record"):
        reasons.append("independent label/rubric calibration record is missing")
    tasks = {}
    for task in comparison["tasks"]:
        a, b = (comparison[k]["tasks"][task] for k in ("baseline_summary", "candidate_summary"))
        gates = brief["tasks"][task]
        failures = []
        if a["unknown"] or b["unknown"] or a["cases_complete"] < gates["min_cases"] or b["cases_complete"] < gates["min_cases"]:
            failures.append("missing grades or insufficient scenarios")
        arate, brate = a["passed"] / a["trials"], b["passed"] / b["trials"]
        if b["critical_failures"]:
            failures.append("critical correctness violation")
        if b["screen_failures"]:
            failures.append("application moderation screen fails; model quality alone cannot qualify the system")
        if brate < gates["min_success_rate"] or arate - brate > gates["max_success_rate_drop"]:
            failures.append("success floor or non-regression limit failed")
        if task.endswith("voice") and (a["quality_mean"] is None or b["quality_mean"] is None or
                                      a["quality_mean"] - b["quality_mean"] > gates["max_quality_drop"]):
            failures.append("voice-quality non-regression limit unknown or failed")
        if b["p95_ms"] > gates["max_p95_ms"]:
            failures.append("latency ceiling failed")
        if b["cost_per_success_usd"] is None or b["cost_per_success_usd"] > gates["max_cost_per_success_usd"]:
            failures.append("cost ceiling unknown or exceeded")
        metric = gates["switch_metric"]
        gain = None
        if metric == "success_rate":
            gain = brate - arate
        elif metric == "quality" and a["quality_mean"] is not None and b["quality_mean"] is not None:
            gain = b["quality_mean"] - a["quality_mean"]
        elif metric in ("cost", "latency"):
            key = "cost_per_success_usd" if metric == "cost" else "p95_ms"
            if a[key] is not None and a[key] > 0 and b[key] is not None:
                gain = 1 - b[key] / a[key]
        if gain is None or gain < gates["minimum_gain"]:
            failures.append("predeclared worthwhile improvement is unknown or unmet")
        tasks[task] = {"observed_gain": gain, "reasons": failures,
                       "status": "needs evidence or correction" if failures or reasons else "supports human review"}
    return {"status": "human review required", "reasons": reasons, "tasks": tasks,
            "limits": "Observed thresholds are not proof of statistical superiority. Inspect paired failures, sample uncertainty, operations, terms and switching costs before deciding."}


def calibration(human, judge):
    pairs = [(human[k], judge[k]) for k in human.keys() & judge.keys()
             if human[k]["success"] is not None and judge[k]["success"] is not None]
    if not pairs:
        raise ValueError("no complete paired grades")
    return {"paired_items": len(pairs),
            "pass_fail_agreements": sum(a["success"] == b["success"] for a, b in pairs),
            "judge_false_passes": sum(not a["success"] and b["success"] for a, b in pairs),
            "judge_missed_critical": sum(a["critical_violation"] and not b["critical_violation"] for a, b in pairs),
            "mean_absolute_score_error": {d: statistics.mean(abs(a["scores"][d] - b["scores"][d])
                                                            for a, b in pairs)
                                          for d in pairs[0][0]["scores"]},
            "status": "diagnostic only; no automatic judge approval"}

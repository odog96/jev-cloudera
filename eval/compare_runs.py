#!/usr/bin/env python3
"""
compare_runs.py

Recomputes the standard measures for one or two saved runs, from each run's
predictions.jsonl and the known correct answers in its claims file, and prints
them side by side. Uses the same analysis code as run_eval.py, so the measures
are always the same:

  accuracy and balanced accuracy per question (overall, easy, hard, each hard
  scenario), order flip rate, fitted temperature, ECE before and after scaling.

Makes no endpoint calls and writes nothing.

Usage
-----
    python eval/compare_runs.py results/dev/no_tiebreak                       # one run
    python eval/compare_runs.py results/dev/tiebreak results/dev/no_tiebreak  # previous, new
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from run_eval import analyse, load_jsonl  # noqa: E402


def load_run(run_dir):
    """Returns (meta, metrics, warnings) for a run folder."""
    run_dir = os.path.join(ROOT, run_dir)
    with open(os.path.join(run_dir, "run.json")) as f:
        meta = json.load(f)
    claims = load_jsonl(os.path.join(ROOT, meta["claims"]))
    with open(os.path.join(ROOT, meta["questions"])) as f:
        questions = json.load(f)
    preds = load_jsonl(os.path.join(run_dir, "predictions.jsonl"))
    scored = {p["question"] for p in preds}
    questions = {k: v for k, v in questions.items() if k in scored}
    warnings = []
    for k, q in questions.items():
        recorded = meta.get("question_text", {}).get(k)
        if recorded is not None and recorded != q["question"]:
            warnings.append(f"{k}: question text in {meta['questions']} differs from the text recorded for this run")
    return meta, analyse(claims, questions, preds), warnings


def rows(m):
    """Flatten one question's metrics into (label, value) pairs, in a fixed order."""
    out = []
    for name in ("overall", "easy", "hard"):
        out.append((f"{name} accuracy", m[name]["accuracy"]))
        out.append((f"{name} balanced accuracy", m[name]["balanced_accuracy"]))
    for s, b in m["hard_by_scenario"].items():
        out.append((f"{s} accuracy (n={b['n']})", b["accuracy"]))
    out.append(("order flip rate", m["order_flip_rate"]))
    c = m["calibration"]
    out += [("temperature", c["temperature"]), ("ECE before scaling", c["ece_before"]),
            ("ECE after scaling", c["ece_after"])]
    return out


def fmt(x):
    return "—" if x is None else f"{x:.3f}"


def report(run_dirs):
    loaded = [load_run(d) for d in run_dirs]
    lines = []
    for d, (meta, _, warns) in zip(run_dirs, loaded):
        lines.append(f"- {d}: model {meta['model']}, claims {meta['claims']}, questions {meta['questions']}")
        lines += [f"  WARNING {w}" for w in warns]
    if len(loaded) == 2 and loaded[0][0]["claims"] != loaded[1][0]["claims"]:
        lines.append("  WARNING runs use different claims files; differences are not like-for-like")
    keys = [k for k in loaded[-1][1]["questions"] if all(k in m["questions"] for _, m, _ in loaded)]
    for k in keys:
        lines += ["", f"## {k}", ""]
        if len(loaded) == 1:
            lines += ["| measure | value |", "|---|---|"]
            lines += [f"| {label} | {fmt(v)} |" for label, v in rows(loaded[0][1]["questions"][k])]
        else:
            a = dict(rows(loaded[0][1]["questions"][k]))
            b = rows(loaded[1][1]["questions"][k])
            lines += ["| measure | previous | new | change |", "|---|---|---|---|"]
            for label, v in b:
                u = a.get(label)
                delta = None if u is None or v is None else v - u
                sign = "" if delta is None else ("+" if delta >= 0 else "")
                lines.append(f"| {label} | {fmt(u)} | {fmt(v)} | {sign}{fmt(delta)} |")
    return "\n".join(lines)


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    print(report(sys.argv[1:]))


if __name__ == "__main__":
    main()

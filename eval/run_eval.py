#!/usr/bin/env python3
"""
run_eval.py

Measures decision quality of predict() on synthetic claim notes
(data/claims_dev.jsonl or data/claims_test.jsonl):

  * accuracy and balanced accuracy for each question, overall, easy vs hard,
    and per hard-case scenario
  * order robustness: each note is scored a second time with the options in a
    different order (senior_review: reversed; team: shuffled so that every
    option gets a different letter) and we report how often the chosen answer
    flips
  * calibration: expected calibration error (ECE) before and after temperature
    scaling. The temperature is fitted on one half of the notes and ECE is
    measured on the other half
  * a histogram of the chosen option's probability
  * coverage summary

No speed or throughput is measured.

Endpoint settings come from environment variables (see jev/client.py).

Usage
-----
    python eval/run_eval.py --claims data/claims_test.jsonl --out results/test
    python eval/run_eval.py --claims data/claims_dev.jsonl --out results/dev/x \
        --questions eval/variants/x.json --only team
    python eval/run_eval.py --out results/test --reuse   # re-analyse saved predictions

Writes predictions.jsonl, metrics.json and summary.md to the --out folder.
"""

import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jev import calibrate as cal  # noqa: E402
from jev.client import load_config, make_client, predict  # noqa: E402

SEED = 20261003
HIST_EDGES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.99, 1.0000001]


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def permuted(options, qkey, rng):
    """senior_review: reversed. Others: shuffled so no option keeps its letter."""
    if qkey == "senior_review":
        return list(reversed(options))
    while True:
        perm = options[:]
        rng.shuffle(perm)
        if all(a["id"] != b["id"] for a, b in zip(perm, options)):
            return perm


def predict_with_retry(state, question, options, client, cfg, tries=3):
    for i in range(tries):
        try:
            return predict(state, question, options, client, cfg)
        except RuntimeError as e:
            if i == tries - 1:
                raise
            print(f"  retrying after error: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))


def score_all(claims, questions, pred_path):
    cfg = load_config()
    client = make_client(cfg)
    rng = random.Random(SEED)
    total = len(claims) * len(questions) * 2
    done = 0
    with open(pred_path, "w") as out:
        for c in claims:
            for qkey, q in questions.items():
                for order, opts in (("original", q["options"]), ("permuted", permuted(q["options"], qkey, rng))):
                    p = predict_with_retry(c["state"], q["question"], opts, client, cfg)
                    out.write(json.dumps({
                        "id": c["id"], "question": qkey, "order": order,
                        "option_order": [o["id"] for o in opts],
                        "choice": p.choice, "probs": p.probs, "coverage": p.coverage,
                    }) + "\n")
                    done += 1
            if done % 100 == 0 or done == total:
                print(f"  scored {done}/{total}", file=sys.stderr)
    return cfg["model"]


# --- metrics -------------------------------------------------------------------

def accuracy(pairs):
    """pairs: list of (true, predicted)."""
    return sum(t == p for t, p in pairs) / len(pairs) if pairs else None


def balanced_accuracy(pairs):
    """Mean recall over the true classes present in pairs."""
    by_class = {}
    for t, p in pairs:
        by_class.setdefault(t, []).append(t == p)
    if not by_class:
        return None
    return sum(sum(v) / len(v) for v in by_class.values()) / len(by_class)


def acc_block(pairs):
    return {"n": len(pairs), "accuracy": accuracy(pairs), "balanced_accuracy": balanced_accuracy(pairs)}


def histogram(confs):
    labels = ["<0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-0.99", "0.99-1.0"]
    counts = [0] * len(labels)
    for c in confs:
        for i in range(len(labels)):
            if HIST_EDGES[i] <= c < HIST_EDGES[i + 1]:
                counts[i] += 1
                break
    return dict(zip(labels, counts))


def analyse(claims, questions, preds):
    by_id = {c["id"]: c for c in claims}
    idx = {(p["id"], p["question"], p["order"]): p for p in preds}

    split_rng = random.Random(SEED)
    ids = sorted(by_id)
    split_rng.shuffle(ids)
    fit_ids, test_ids = set(ids[: len(ids) // 2]), set(ids[len(ids) // 2:])

    metrics = {"n_claims": len(claims), "questions": {}}
    for qkey, q in questions.items():
        option_ids = [o["id"] for o in q["options"]]
        orig = [idx[(cid, qkey, "original")] for cid in ids]
        pairs = {cid: (by_id[cid][qkey], idx[(cid, qkey, "original")]["choice"]) for cid in ids}

        def subset(pred):
            return [pairs[cid] for cid in ids if pred(by_id[cid])]

        scen = sorted({c["scenario"] for c in claims if c["difficulty"] == "hard"})
        perm_pairs = [(by_id[cid][qkey], idx[(cid, qkey, "permuted")]["choice"]) for cid in ids]
        flips = [idx[(cid, qkey, "original")]["choice"] != idx[(cid, qkey, "permuted")]["choice"] for cid in ids]

        # Calibration on rows with a choice, probabilities in the original option order.
        def rows_for(id_set):
            rows, labels = [], []
            for cid in ids:
                p = idx[(cid, qkey, "original")]
                if cid in id_set and p["choice"] is not None:
                    rows.append([p["probs"][o] for o in option_ids])
                    labels.append(option_ids.index(by_id[cid][qkey]))
            return rows, labels

        fit_rows, fit_labels = rows_for(fit_ids)
        test_rows, test_labels = rows_for(test_ids)
        T = cal.fit_temperature(fit_rows, fit_labels)

        def ece(rows, labels, temp):
            confs, correct = [], []
            for r, y in zip(rows, labels):
                s = cal.apply_temperature(r, temp)
                k = max(range(len(s)), key=s.__getitem__)
                confs.append(s[k])
                correct.append(k == y)
            return cal.expected_calibration_error(confs, correct), confs

        ece_before, conf_before = ece(test_rows, test_labels, 1.0)
        ece_after, conf_after = ece(test_rows, test_labels, T)
        all_rows, _ = rows_for(set(ids))
        all_conf = [max(r) for r in all_rows]

        covs = [p["coverage"] for p in orig]
        metrics["questions"][qkey] = {
            "overall": acc_block(list(pairs.values())),
            "easy": acc_block(subset(lambda c: c["difficulty"] == "easy")),
            "hard": acc_block(subset(lambda c: c["difficulty"] == "hard")),
            "hard_by_scenario": {s: acc_block(subset(lambda c, s=s: c["scenario"] == s)) for s in scen},
            "permuted_order_accuracy": acc_block(perm_pairs),
            "order_flip_rate": sum(flips) / len(flips),
            "order_flips": sum(flips),
            "order_check": "reversed" if qkey == "senior_review" else "shuffled, every option moved",
            "calibration": {
                "fit_n": len(fit_rows), "test_n": len(test_rows),
                "temperature": T,
                "ece_before": ece_before, "ece_after": ece_after,
                "nll_before": cal.nll(test_rows, test_labels, 1.0),
                "nll_after": cal.nll(test_rows, test_labels, T),
            },
            "chosen_prob_histogram": histogram(all_conf),
            "chosen_prob_histogram_test_after_scaling": histogram(conf_after),
            "coverage": {"min": min(covs), "mean": sum(covs) / len(covs),
                         "below_0.9": sum(c < 0.9 for c in covs),
                         "no_choice": sum(p["choice"] is None for p in orig)},
        }
    return metrics


def fmt(x):
    return "n/a" if x is None else f"{x:.3f}"


def summary_md(metrics, model, claims_path, questions_path):
    lines = [f"# Evaluation results: {model} on synthetic claim notes", "",
             f"{metrics['n_claims']} synthetic first-notice-of-loss notes ({claims_path}), "
             f"questions from {questions_path}. "
             "Each decision requests exactly 1 output token. No speed measurement.", ""]
    for qkey, m in metrics["questions"].items():
        lines += [f"## {qkey}", "", f"Question: {metrics['question_text'][qkey]}", "", "| subset | n | accuracy | balanced accuracy |", "|---|---|---|---|"]
        for name in ("overall", "easy", "hard"):
            b = m[name]
            lines.append(f"| {name} | {b['n']} | {fmt(b['accuracy'])} | {fmt(b['balanced_accuracy'])} |")
        for s, b in m["hard_by_scenario"].items():
            lines.append(f"| hard: {s} | {b['n']} | {fmt(b['accuracy'])} | {fmt(b['balanced_accuracy'])} |")
        c = m["calibration"]
        lines += ["",
                  f"Order check ({m['order_check']}): chosen answer flipped on {m['order_flips']} of "
                  f"{metrics['n_claims']} notes ({m['order_flip_rate']:.1%}). "
                  f"Accuracy in permuted order: {fmt(m['permuted_order_accuracy']['accuracy'])}.",
                  "",
                  f"Calibration (temperature fitted on {c['fit_n']} notes, measured on the other {c['test_n']}): "
                  f"T = {c['temperature']:.3f}; ECE {c['ece_before']:.3f} -> {c['ece_after']:.3f}; "
                  f"NLL {c['nll_before']:.3f} -> {c['nll_after']:.3f}.",
                  "",
                  "Chosen-option probability (all notes, before scaling): " +
                  ", ".join(f"{k}: {v}" for k, v in m["chosen_prob_histogram"].items()),
                  "",
                  "Chosen-option probability (test half, after scaling): " +
                  ", ".join(f"{k}: {v}" for k, v in m["chosen_prob_histogram_test_after_scaling"].items()),
                  "",
                  f"Coverage: min {m['coverage']['min']:.3f}, mean {m['coverage']['mean']:.4f}, "
                  f"below 0.9: {m['coverage']['below_0.9']}, no choice: {m['coverage']['no_choice']}.",
                  ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default="data/claims_test.jsonl")
    ap.add_argument("--questions", default="data/questions.json")
    ap.add_argument("--only", help="comma-separated question keys to score (default: all)")
    ap.add_argument("--out", required=True, help="output folder, e.g. results/test")
    ap.add_argument("--reuse", action="store_true", help="re-analyse existing predictions.jsonl in --out")
    args = ap.parse_args()

    claims = load_jsonl(os.path.join(ROOT, args.claims))
    with open(os.path.join(ROOT, args.questions)) as f:
        questions = json.load(f)
    if args.only:
        questions = {k: questions[k] for k in args.only.split(",")}
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    pred_path = os.path.join(out, "predictions.jsonl")
    meta_path = os.path.join(out, "run.json")

    if args.reuse:
        with open(meta_path) as f:
            model = json.load(f)["model"]
    else:
        model = score_all(claims, questions, pred_path)
        with open(meta_path, "w") as f:
            json.dump({"model": model, "claims": args.claims, "questions": args.questions,
                       "question_text": {k: q["question"] for k, q in questions.items()}}, f, indent=2)
    preds = load_jsonl(pred_path)

    metrics = analyse(claims, questions, preds)
    metrics["model"] = model
    metrics["claims"] = args.claims
    metrics["question_text"] = {k: q["question"] for k, q in questions.items()}
    with open(os.path.join(out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    text = summary_md(metrics, model, args.claims, args.questions)
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()

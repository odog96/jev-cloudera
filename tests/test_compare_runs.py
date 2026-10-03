"""Tests for eval/compare_runs.py using small fake runs (no network)."""

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))

import compare_runs  # noqa: E402

QUESTIONS = {"senior_review": {"question": "Senior?", "options": [{"id": "yes"}, {"id": "no"}]}}
CLAIMS = [
    {"id": "c1", "state": "x", "senior_review": "yes", "difficulty": "easy", "scenario": "s_easy"},
    {"id": "c2", "state": "x", "senior_review": "no", "difficulty": "easy", "scenario": "s_easy"},
    {"id": "c3", "state": "x", "senior_review": "yes", "difficulty": "hard", "scenario": "hard_a"},
    {"id": "c4", "state": "x", "senior_review": "no", "difficulty": "hard", "scenario": "hard_a"},
]


def write_run(base, name, choices, permuted_choices):
    """choices: claim id -> chosen option in original order (prob 0.9)."""
    d = os.path.join(base, name)
    os.makedirs(d)
    with open(os.path.join(d, "predictions.jsonl"), "w") as f:
        for cid in choices:
            for order, ch in (("original", choices[cid]), ("permuted", permuted_choices[cid])):
                other = "no" if ch == "yes" else "yes"
                f.write(json.dumps({"id": cid, "question": "senior_review", "order": order,
                                    "choice": ch, "probs": {ch: 0.9, other: 0.1}, "coverage": 1.0}) + "\n")
    rel = os.path.relpath(base, compare_runs.ROOT)
    with open(os.path.join(d, "run.json"), "w") as f:
        json.dump({"model": "m", "claims": f"{rel}/claims.jsonl", "questions": f"{rel}/questions.json",
                   "question_text": {"senior_review": "Senior?"}}, f)
    return os.path.relpath(d, compare_runs.ROOT)


class CompareRunsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(dir=compare_runs.ROOT)
        with open(os.path.join(self.base, "claims.jsonl"), "w") as f:
            f.writelines(json.dumps(c) + "\n" for c in CLAIMS)
        with open(os.path.join(self.base, "questions.json"), "w") as f:
            json.dump(QUESTIONS, f)

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_single_run_measures_from_claims_labels(self):
        # 3 of 4 right; the hard "no" is wrong. One flip (c1).
        run = write_run(self.base, "a", {"c1": "yes", "c2": "no", "c3": "yes", "c4": "yes"},
                        {"c1": "no", "c2": "no", "c3": "yes", "c4": "yes"})
        _, m, warns = compare_runs.load_run(run)
        q = m["questions"]["senior_review"]
        self.assertEqual(warns, [])
        self.assertAlmostEqual(q["overall"]["accuracy"], 0.75)
        self.assertAlmostEqual(q["overall"]["balanced_accuracy"], 0.75)  # yes 2/2, no 1/2
        self.assertAlmostEqual(q["easy"]["accuracy"], 1.0)
        self.assertAlmostEqual(q["hard_by_scenario"]["hard_a"]["accuracy"], 0.5)
        self.assertAlmostEqual(q["order_flip_rate"], 0.25)
        text = compare_runs.report([run])
        self.assertIn("| overall accuracy | 0.750 |", text)

    def test_two_runs_show_change(self):
        a = write_run(self.base, "a", {"c1": "yes", "c2": "yes", "c3": "yes", "c4": "yes"},
                      {"c1": "yes", "c2": "yes", "c3": "yes", "c4": "yes"})
        b = write_run(self.base, "b", {"c1": "yes", "c2": "no", "c3": "yes", "c4": "no"},
                      {"c1": "yes", "c2": "no", "c3": "yes", "c4": "no"})
        text = compare_runs.report([a, b])
        self.assertIn("| overall accuracy | 0.500 | 1.000 | +0.500 |", text)
        self.assertIn("| order flip rate | 0.000 | 0.000 | +0.000 |", text)

    def test_warns_when_question_text_changed(self):
        run = write_run(self.base, "a", {c["id"]: "yes" for c in CLAIMS}, {c["id"]: "yes" for c in CLAIMS})
        with open(os.path.join(self.base, "questions.json"), "w") as f:
            json.dump({"senior_review": {**QUESTIONS["senior_review"], "question": "Changed?"}}, f)
        _, _, warns = compare_runs.load_run(run)
        self.assertEqual(len(warns), 1)


if __name__ == "__main__":
    unittest.main()

"""Tests for app/triage.py using canned endpoint responses (no network)."""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import triage as tr  # noqa: E402
from jev.client import Prediction  # noqa: E402
from tests.test_client import CFG, FakeChatClient, chat_response  # noqa: E402

QUESTIONS = tr.load_questions()


def prompt_of(call):
    return call["messages"][-1]["content"]


class TriageTest(unittest.TestCase):
    def test_both_questions_asked_over_one_client(self):
        fake = FakeChatClient(chat_response({"A": math.log(0.9), "B": math.log(0.1)}))
        out = tr.triage("Bumper cracked, no injury.", client=fake, cfg=CFG)
        self.assertEqual(list(out), ["team", "senior_review"])
        self.assertEqual(len(fake.calls), 2)
        self.assertIn(QUESTIONS["team"]["question"], prompt_of(fake.calls[0]))
        self.assertIn(QUESTIONS["senior_review"]["question"], prompt_of(fake.calls[1]))

    def test_option_ids_and_order_from_questions_json(self):
        fake = FakeChatClient(chat_response({"B": math.log(0.7), "A": math.log(0.3)}))
        out = tr.triage("Note.", client=fake, cfg=CFG)
        for key, pred in out.items():
            self.assertEqual(list(pred.probs), [o["id"] for o in QUESTIONS[key]["options"]])
        self.assertEqual(out["team"].choice, QUESTIONS["team"]["options"][1]["id"])
        self.assertEqual(out["senior_review"].choice, "no")

    def test_empty_note_rejected_before_any_call(self):
        fake = FakeChatClient(chat_response({"A": 0.0}))
        for note in ("", "   \n"):
            with self.assertRaises(ValueError):
                tr.triage(note, client=fake, cfg=CFG)
            with self.assertRaises(ValueError):
                tr.ask(note, "team", QUESTIONS, client=fake, cfg=CFG)
        self.assertEqual(fake.calls, [])


class TemperatureTest(unittest.TestCase):
    def test_loads_from_saved_dev_runs(self):
        temps = tr.load_temperatures()
        self.assertEqual(set(temps), {"team", "senior_review"})
        for key, run in tr.TEMPERATURE_RUNS.items():
            with open(os.path.join(tr.PROJECT_ROOT, run, "metrics.json")) as f:
                saved = json.load(f)["questions"][key]["calibration"]["temperature"]
            self.assertEqual(temps[key]["temperature"], saved)
            self.assertTrue(run.startswith("results/dev/"))

    def test_mismatched_question_refused(self):
        changed = json.loads(json.dumps(QUESTIONS))
        changed["senior_review"]["question"] = "Something else?"
        with self.assertRaises(RuntimeError):
            tr.load_temperatures(questions=changed)

    def test_mismatched_options_refused(self):
        changed = json.loads(json.dumps(QUESTIONS))
        changed["team"]["options"] = list(reversed(changed["team"]["options"]))
        with self.assertRaises(RuntimeError):
            tr.load_temperatures(questions=changed)

    def test_non_dev_run_refused(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        src = os.path.join(tr.PROJECT_ROOT, tr.TEMPERATURE_RUNS["team"])
        dst = os.path.join(tmp, "run")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("predictions.jsonl"))
        with open(os.path.join(dst, "run.json")) as f:
            info = json.load(f)
        info["claims"] = "data/claims_test.jsonl"
        info["questions"] = os.path.join(tr.PROJECT_ROOT, info["questions"])
        with open(os.path.join(dst, "run.json"), "w") as f:
            json.dump(info, f)
        with self.assertRaises(RuntimeError):
            tr.load_temperatures(runs={"team": "run"}, root=tmp)


class CalibratedTest(unittest.TestCase):
    OPTIONS = QUESTIONS["team"]["options"]

    def pred(self, probs):
        ids = [o["id"] for o in self.OPTIONS]
        p = dict(zip(ids, probs))
        return Prediction(max(p, key=p.get), p, 1.0, 1.0)

    def test_keeps_choice_and_sums_to_one(self):
        pred = self.pred([0.001, 0.995, 0.003, 0.001])
        cal = tr.calibrated(pred, 4.78)
        self.assertEqual(list(cal), [o["id"] for o in self.OPTIONS])
        self.assertAlmostEqual(sum(cal.values()), 1.0)
        self.assertEqual(max(cal, key=cal.get), pred.choice)
        self.assertLess(cal[pred.choice], pred.probs[pred.choice])

    def test_option_outside_top_k_still_defined(self):
        cal = tr.calibrated(self.pred([0.0, 1.0, 0.0, 0.0]), 4.78)
        self.assertAlmostEqual(sum(cal.values()), 1.0)
        self.assertEqual(max(cal, key=cal.get), "injury")

    def test_zero_coverage_gives_none(self):
        pred = Prediction(None, {o["id"]: None for o in self.OPTIONS}, 0.0, 1.0)
        self.assertIsNone(tr.calibrated(pred, 4.78))


if __name__ == "__main__":
    unittest.main()

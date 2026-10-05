"""Tests for app/presentation.py (no network)."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import presentation as pr  # noqa: E402

with open(os.path.join(ROOT, "data", "questions.json")) as f:
    QUESTIONS = json.load(f)


class ShortLabelTest(unittest.TestCase):
    def test_every_option_in_questions_json(self):
        labels = {o["id"]: pr.short_label(o) for q in QUESTIONS.values() for o in q["options"]}
        self.assertEqual(labels, {
            "standard": "Standard claims handling",
            "injury": "Injury claims",
            "fraud_review": "Fraud review",
            "coverage": "Coverage questions",
            "yes": "Yes, send to a senior adjuster",
            "no": "No, normal handling",
        })

    def test_no_colon_and_no_description(self):
        self.assertEqual(pr.short_label({"id": "x", "description": "Plain text."}), "Plain text.")
        self.assertEqual(pr.short_label({"id": "x"}), "x")


class HeadlineTest(unittest.TestCase):
    def test_headline_uses_label_not_id(self):
        opt = QUESTIONS["team"]["options"][0]
        self.assertEqual(pr.headline("Team", opt, 0.912), "Team: Standard claims handling, 91% confident")

    def test_rounding_half_up(self):
        self.assertEqual(pr.percent(0.795), 80)
        self.assertEqual(pr.percent(0.7949), 79)
        self.assertEqual(pr.percent(1.0), 100)


OPTS = {o["id"]: o for q in QUESTIONS.values() for o in q["options"]}
STANDARD = OPTS["standard"]


def act(confidence, threshold, coverage=1.0, key="team", option=STANDARD):
    return pr.recommended_action(key, option, confidence, coverage, threshold)


class RecommendedActionTest(unittest.TestCase):
    def test_at_threshold_is_automatic(self):
        self.assertEqual(act(0.80, 80), (True, "Route to Standard claims handling automatically"))

    def test_above_threshold_is_automatic(self):
        self.assertTrue(act(0.93, 80)[0])

    def test_shown_as_threshold_is_automatic(self):
        # 79.6% is shown as 80%, so it must not say "below 80%".
        self.assertTrue(act(0.796, 80)[0])

    def test_below_threshold_goes_to_a_person(self):
        self.assertEqual(act(0.79, 80), (False, "Below 80%: send to a person to review"))

    def test_slider_ends(self):
        self.assertTrue(act(0.50, 50)[0])
        self.assertFalse(act(0.49, 50)[0])
        self.assertTrue(act(0.99, 99)[0])
        self.assertEqual(act(0.98, 99), (False, "Below 99%: send to a person to review"))


class DestinationTest(unittest.TestCase):
    def test_every_destination(self):
        texts = {oid: act(0.95, 80, key=key, option=OPTS[oid])[1]
                 for key, q in QUESTIONS.items() for oid in (o["id"] for o in q["options"])}
        self.assertEqual(texts, {
            "standard": "Route to Standard claims handling automatically",
            "injury": "Route to Injury claims automatically",
            "fraud_review": "Route to Fraud review automatically",
            "coverage": "Route to Coverage questions automatically",
            "yes": "Send to a senior adjuster automatically",
            "no": "Skip senior review automatically",
        })

    def test_other_question_names_label(self):
        self.assertEqual(act(0.9, 80, key="other", option={"id": "a", "description": "Team A: x"})[1],
                         "Route to Team A automatically")


class CoverageFloorTest(unittest.TestCase):
    UNSURE = (False, pr.UNSURE)

    def test_floor_edge(self):
        self.assertEqual(act(0.99, 99, coverage=0.949), self.UNSURE)
        self.assertTrue(act(0.99, 99, coverage=0.95)[0])

    def test_low_coverage_overrides_low_threshold(self):
        self.assertEqual(act(0.99, 50, coverage=0.60), self.UNSURE)

    def test_low_coverage_headline_has_no_percentage(self):
        self.assertEqual(pr.headline("Team", STANDARD, 0.97, coverage=0.60),
                         "Team: Standard claims handling, confidence not reliable")
        self.assertEqual(pr.headline("Team", STANDARD, 0.97, coverage=0.95),
                         "Team: Standard claims handling, 97% confident")


if __name__ == "__main__":
    unittest.main()

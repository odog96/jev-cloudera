"""Tests for jev/client.py using canned endpoint responses (no network)."""

import math
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev import client as jc  # noqa: E402

OPTIONS = [
    {"id": "standard", "description": "Standard claims handling."},
    {"id": "injury", "description": "Injury claims."},
    {"id": "fraud_review", "description": "Fraud review."},
    {"id": "coverage", "description": "Coverage questions."},
]
CFG = {"model": "test-model", "top_k": 20, "api": "chat", "disable_thinking": False}


def chat_response(top, token=None):
    """Shape of an openai ChatCompletion with logprobs for one token."""
    token = token or max(top, key=top.get)
    entries = [NS(token=t, logprob=lp) for t, lp in top.items()]
    first = NS(token=token, logprob=top[token], top_logprobs=entries)
    return NS(choices=[NS(logprobs=NS(content=[first]))])


class FakeChatClient:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class LetterProbsTest(unittest.TestCase):
    def test_token_variants_count_toward_same_letter(self):
        top = {"A": math.log(0.5), " A": math.log(0.2), "A.": math.log(0.1), "B": math.log(0.1)}
        probs, coverage = jc.letter_probs(top, 2)
        self.assertAlmostEqual(coverage, 0.9)
        self.assertAlmostEqual(probs["A"], 0.8 / 0.9)
        self.assertAlmostEqual(probs["B"], 0.1 / 0.9)

    def test_letters_beyond_option_count_are_ignored(self):
        top = {"A": math.log(0.6), "C": math.log(0.3), "Sure": math.log(0.1)}
        probs, coverage = jc.letter_probs(top, 2)
        self.assertAlmostEqual(coverage, 0.6)
        self.assertEqual(probs, {"A": 1.0, "B": 0.0})

    def test_zero_coverage(self):
        probs, coverage = jc.letter_probs({"The": 0.0}, 3)
        self.assertEqual(coverage, 0.0)
        self.assertEqual(probs, {"A": None, "B": None, "C": None})


class BuildPromptTest(unittest.TestCase):
    def test_options_are_lettered(self):
        text = jc.build_prompt_text("note", "Which team?", OPTIONS)
        self.assertIn("A. Standard claims handling.", text)
        self.assertIn("D. Coverage questions.", text)
        self.assertIn("Question: Which team?", text)

    def test_falls_back_to_id_without_description(self):
        text = jc.build_prompt_text("note", "Q?", [{"id": "yes"}, {"id": "no"}])
        self.assertIn("A. yes", text)

    def test_rejects_single_option(self):
        with self.assertRaises(ValueError):
            jc.build_prompt_text("note", "Q?", [{"id": "only"}])


class PredictTest(unittest.TestCase):
    def test_returns_choice_probs_coverage_latency(self):
        top = {"B": math.log(0.7), "A": math.log(0.2), "D": math.log(0.05), "I": math.log(0.05)}
        fake = FakeChatClient(chat_response(top))
        p = jc.predict("Neck is sore after the crash.", "Which team?", OPTIONS, fake, CFG)
        self.assertEqual(p.choice, "injury")
        self.assertAlmostEqual(p.coverage, 0.95)
        self.assertAlmostEqual(p.probs["injury"], 0.7 / 0.95)
        self.assertAlmostEqual(p.probs["standard"], 0.2 / 0.95)
        self.assertEqual(p.probs["fraud_review"], 0.0)  # "C" not in top-k
        self.assertAlmostEqual(sum(p.probs.values()), 1.0)
        self.assertGreaterEqual(p.latency_ms, 0.0)
        self.assertEqual(p.token, "B")

    def test_asks_for_one_token_with_logprobs(self):
        fake = FakeChatClient(chat_response({"A": 0.0}))
        jc.predict("note", "Q?", OPTIONS, fake, CFG)
        call = fake.calls[0]
        self.assertEqual(call["max_tokens"], 1)
        self.assertEqual(call["temperature"], 1.0)
        self.assertIs(call["logprobs"], True)
        self.assertEqual(call["top_logprobs"], 20)
        self.assertIsNone(call["extra_body"])  # no thinking kwarg by default

    def test_thinking_kwarg_is_opt_in(self):
        fake = FakeChatClient(chat_response({"A": 0.0}))
        jc.predict("note", "Q?", OPTIONS, fake, {**CFG, "disable_thinking": True})
        self.assertEqual(fake.calls[0]["extra_body"], {"chat_template_kwargs": {"enable_thinking": False}})

    def test_zero_coverage_has_no_choice(self):
        fake = FakeChatClient(chat_response({"I": math.log(0.9), "The": math.log(0.1)}))
        p = jc.predict("note", "Q?", [{"id": "yes"}, {"id": "no"}], fake, CFG)
        self.assertIsNone(p.choice)
        self.assertEqual(p.coverage, 0.0)
        self.assertEqual(p.probs, {"yes": None, "no": None})

    def test_missing_logprobs_raises_clear_error(self):
        fake = FakeChatClient(NS(choices=[NS(logprobs=None)]))
        with self.assertRaisesRegex(RuntimeError, "no logprobs.content"):
            jc.predict("note", "Q?", OPTIONS, fake, CFG)

    def test_http_error_is_wrapped(self):
        fake = FakeChatClient(None)
        fake.chat.completions.create = mock.Mock(side_effect=ValueError("HTTP 401"))
        with self.assertRaisesRegex(RuntimeError, r"/chat/completions request failed: ValueError: HTTP 401"):
            jc.predict("note", "Q?", OPTIONS, fake, CFG)

    def test_completions_api(self):
        response = NS(choices=[NS(logprobs=NS(tokens=["B"], top_logprobs=[{"B": math.log(0.6), "A": math.log(0.4)}]))])
        create = mock.Mock(return_value=response)
        fake = NS(completions=NS(create=create))
        with mock.patch.object(jc, "chat_template_prompt", return_value="<templated>"):
            p = jc.predict("note", "Q?", [{"id": "yes"}, {"id": "no"}], fake, {**CFG, "api": "completions"})
        self.assertEqual(p.choice, "no")
        self.assertAlmostEqual(p.probs["no"], 0.6)
        self.assertEqual(create.call_args.kwargs["prompt"], "<templated>")
        self.assertEqual(create.call_args.kwargs["logprobs"], 20)


class LoadConfigTest(unittest.TestCase):
    def test_token_from_env_and_ca_bundle(self):
        env = {"CAI_BASE_URL": "https://x/v1/", "CAI_MODEL": "m", "CAI_TOKEN": "t", "CAI_CA_BUNDLE": "/ca.pem"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = jc.load_config()
        self.assertEqual(cfg["base"], "https://x/v1")
        self.assertEqual(cfg["token"], "t")
        self.assertEqual(cfg["verify"], "/ca.pem")
        self.assertFalse(cfg["disable_thinking"])
        self.assertEqual(cfg["api"], "chat")

    def test_missing_vars(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CAI_BASE_URL, CAI_MODEL"):
                jc.load_config()


if __name__ == "__main__":
    unittest.main()

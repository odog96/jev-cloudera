#!/usr/bin/env python3
"""
check_logprobs.py

Checks whether a model hosted on Cloudera AI Inference Service can make
Jev-style decisions: given a first-notice-of-loss claim note, a question, and a
fixed list of options, return a probability for each option instead of
written text.

The prompt format and probability math live in jev/client.py (predict); see
that file for how it works and for the environment variables it reads
(CAI_BASE_URL, CAI_MODEL, CAI_TOKEN, CAI_CA_BUNDLE, ...).

The script tries the chat-completions API first. If that fails, it falls back
to the plain completions API, building the prompt with the model's own chat
template. CAI_API is ignored here; both are probed.

Usage
-----
    pip install -r requirements.txt   # plus transformers, for the fallback only
    export CAI_BASE_URL=https://.../v1
    export CAI_MODEL=Qwen/Qwen2.5-7B-Instruct
    python scripts/check_logprobs.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jev.client import load_config, make_client, predict  # noqa: E402

with open(os.path.join(ROOT, "data", "questions.json")) as f:
    QUESTIONS = json.load(f)

# Three example claim notes (all details fake). "expected" is the option a
# person would pick; it is only used to print a match/no-match column.
EXAMPLES = [
    {
        "id": "claim-1",
        "state": "Caller Jane Demo, policy DEMO-100001. Rear-ended at a stop light on "
                 "Main St. Bumper and tail light damaged on 2019 sedan, VIN DEMO0000000000001. "
                 "Other driver exchanged details. No one hurt. Photos uploaded.",
        "question": "team",
        "expected": "standard",
    },
    {
        "id": "claim-2",
        "state": "Caller John Sample, policy DEMO-100002. Kitchen fire last night. Says he "
                 "was treated at the ER for smoke inhalation and burns to his hand. Has "
                 "already spoken to a lawyer.",
        "question": "team",
        "expected": "injury",
    },
    {
        "id": "claim-3",
        "state": "Caller Alex Placeholder, policy DEMO-100003. Bike stolen from garage, "
                 "valued at $400. Police report filed. Policy active for 6 years, no prior claims.",
        "question": "senior_review",
        "expected": "no",
    },
]


def run(cfg):
    client = make_client(cfg)
    print(f"Endpoint: {cfg['base']}\nModel:    {cfg['model']}\n"
          f"Thinking kwarg sent: {cfg['disable_thinking']}\n")

    # Pick whichever API returns log-probabilities.
    errors = {}
    probe = EXAMPLES[0]
    q = QUESTIONS[probe["question"]]
    for api in ("chat", "completions"):
        try:
            predict(probe["state"], q["question"], q["options"], client, {**cfg, "api": api})
            cfg = {**cfg, "api": api}
            break
        except Exception as e:  # noqa: BLE001 - report every failure reason
            errors[api] = str(e)
    else:
        print("RESULT: FAIL - neither API returned log-probabilities.\n")
        for api, err in errors.items():
            print(f"  {api}: {err}")
        return 1

    if errors:
        print(f"Note: chat-completions failed ({errors.get('chat')}); using completions.\n")
    print(f"Using the {cfg['api']} API with top {cfg['top_k']} log-probabilities.\n")

    all_ok = True
    for ex in EXAMPLES:
        q = QUESTIONS[ex["question"]]
        p = predict(ex["state"], q["question"], q["options"], client, cfg)

        print(f"{ex['id']}: {q['question']}")
        print(f"  generated token: {p.token!r}   coverage: {p.coverage:.3f}   "
              f"latency: {p.latency_ms:.0f} ms (this endpoint, this request)")
        print("  raw top log-probs: " + ", ".join(
            f"{t!r}:{lp:.3f}" for t, lp in sorted(p.top_logprobs.items(), key=lambda kv: -kv[1])[:6]))
        for opt in q["options"]:
            prob = p.probs[opt["id"]]
            shown = "not in top-k" if prob is None or (prob == 0 and p.coverage > 0) else f"{prob:.3f}"
            print(f"    {opt['id']:<13} {shown}")
        if p.choice is not None:
            match = "matches" if p.choice == ex["expected"] else "DOES NOT match"
            print(f"  prediction: {p.choice} ({match} expected '{ex['expected']}')")
        if p.coverage < 0.9:
            all_ok = False
            print("  WARNING: coverage below 0.9 - the model's top answer was not one of the option letters.")
        print()

    print("RESULT:", "PASS - endpoint can make Jev-style decisions." if all_ok
          else "PARTIAL - log-probabilities work, but some decisions had low coverage (see warnings).")
    return 0 if all_ok else 2


if __name__ == "__main__":
    try:
        config = load_config()
    except RuntimeError as e:
        sys.exit(str(e))
    sys.exit(run(config))

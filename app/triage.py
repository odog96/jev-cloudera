"""
Both claim questions for one note, through jev.client.predict().

triage(note) asks the team question and the senior-review question from
data/questions.json, unchanged, and returns one Prediction per question.

calibrated() rescales a prediction's option probabilities with a temperature.
The temperatures are read (never refitted) from saved development-set runs in
results/dev/; load_temperatures() refuses them if the question or options in
that run differ from data/questions.json, because a temperature fitted on other
wording does not apply.
"""

import json
import os

from jev import calibrate
from jev.client import load_config, make_client, predict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(PROJECT_ROOT, "data", "questions.json")
QUESTION_KEYS = ("team", "senior_review")

# Saved development-set run each question's temperature comes from. The run with
# the chosen team wording scored the team question only; the senior-review
# question was the same in the tiebreak run.
TEMPERATURE_RUNS = {
    "team": "results/dev/conditional_tiebreak",
    "senior_review": "results/dev/tiebreak",
}


def load_questions(path=QUESTIONS_PATH):
    with open(path) as f:
        return json.load(f)


def ask(note, question_key, questions, client=None, cfg=None):
    """One question about one note. Returns a jev.client.Prediction."""
    if not note or not note.strip():
        raise ValueError("The claim note is empty.")
    q = questions[question_key]
    return predict(note, q["question"], q["options"], client=client, cfg=cfg)


def triage(note, questions=None, client=None, cfg=None):
    """Both questions for one note, over one endpoint connection."""
    if not note or not note.strip():
        raise ValueError("The claim note is empty.")
    questions = questions or load_questions()
    cfg = cfg or load_config()
    client = client or make_client(cfg)
    return {k: ask(note, k, questions, client=client, cfg=cfg) for k in QUESTION_KEYS}


def load_temperatures(questions=None, runs=TEMPERATURE_RUNS, root=PROJECT_ROOT):
    """{question key: {"temperature": T, "run": run dir, "fit_n": n}} from saved dev runs."""
    questions = questions or load_questions()
    out = {}
    for key, run in runs.items():
        run_dir = os.path.join(root, run)
        with open(os.path.join(run_dir, "run.json")) as f:
            run_info = json.load(f)
        with open(os.path.join(root, run_info["questions"])) as f:
            run_questions = json.load(f)
        if (run_info["claims"] != "data/claims_dev.jsonl"
                or run_info["question_text"].get(key) != questions[key]["question"]
                or run_questions.get(key) != questions[key]):
            raise RuntimeError(
                f"{run}: the {key} question or options in this run differ from "
                f"data/questions.json (or it is not a development-set run), so its "
                f"temperature does not apply.")
        with open(os.path.join(run_dir, "metrics.json")) as f:
            cal = json.load(f)["questions"][key]["calibration"]
        out[key] = {"temperature": cal["temperature"], "run": run, "fit_n": cal["fit_n"]}
    return out


def calibrated(prediction, T):
    """Option id -> probability rescaled with temperature T; None if coverage was 0.

    Option order is the order of prediction.probs, which predict() builds in the
    order of the question's options."""
    if prediction.choice is None:
        return None
    ids = list(prediction.probs)
    scaled = calibrate.apply_temperature([prediction.probs[i] for i in ids], T)
    return dict(zip(ids, scaled))

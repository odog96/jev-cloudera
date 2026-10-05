"""Cloudera AI Workbench Application — claim-note triage with Jev-style decisions."""

import json
import os
import sys
from pathlib import Path

import streamlit as st

# Resolve data/ and results/ against the project root rather than whatever
# directory the Application was launched from. Streamlit defines __file__; the
# fallback covers a runtime that does not, and searches for the project rather
# than hardcoding where it was cloned (same markers as launch_app.py).
try:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
except NameError:  # pragma: no cover - depends on the CML runtime
    _home = Path("/home/cdsw")
    _PROJECT_ROOT = next(
        c for c in [Path.cwd(), _home, *sorted(p for p in _home.iterdir() if p.is_dir())]
        if (c / "jev" / "client.py").is_file() and (c / "data" / "questions.json").is_file()
    )
os.chdir(_PROJECT_ROOT)
# Streamlit puts this script's own folder (app/) first on sys.path, where `app`
# would resolve to this file instead of the app/ package. The project root goes
# first so `app.triage` and `jev` import as packages.
sys.path.insert(0, str(_PROJECT_ROOT))

from app.presentation import headline, percent, recommended_action, short_label  # noqa: E402
from app.triage import ask, calibrated, load_questions, load_temperatures  # noqa: E402
from jev.client import PLACEHOLDER_HOST, load_config, make_client  # noqa: E402

st.set_page_config(page_title="Claim triage on Cloudera AI", layout="wide")

QUESTION_LABELS = {"team": "Team", "senior_review": "Senior review"}
CHOICES = {"Both": ["team", "senior_review"], "Team": ["team"],
           "Senior review": ["senior_review"]}
EXAMPLES_PER_PAGE = 8
FOOTER = "All claim notes are invented for this demo; no real customer data."
# Neutral example titles: the incident only, never the team, a red flag or the answer.
EXAMPLE_TITLES = {
    "claim-001": "Low-speed rear-end collision", "claim-002": "Incident on icy front steps",
    "claim-003": "Crash in the insured's SUV", "claim-005": "Parking-lot scrape",
    "claim-006": "Garage fire", "claim-007": "Laundry-room water leak",
    "claim-008": "Rear-end collision", "claim-011": "Home theft",
}


@st.cache_data
def examples():
    """The first development-set note of each scenario (never the test set)."""
    seen, out = set(), []
    with open("data/claims_dev.jsonl") as f:
        for line in f:
            c = json.loads(line)
            if c["scenario"] not in seen:
                seen.add(c["scenario"])
                out.append(c)
    return out[:EXAMPLES_PER_PAGE]


questions = load_questions()
try:
    temperatures = load_temperatures(questions)
except (OSError, KeyError, RuntimeError) as e:
    st.error(f"Could not load the calibration temperatures from results/dev: {e}")
    st.stop()

st.title("Claim triage")
st.write("Paste a first-notice-of-loss claim note (the note written when a customer "
         "first reports a claim).")
st.write("The model answers two questions: which team should handle the claim, and "
         "whether a senior adjuster should review it before any payment. "
         "All notes here are invented.")

# --- Input ---
ex = examples()
labels = ["(write your own)"] + [
    f"Example {n}: {EXAMPLE_TITLES[c['id']]}" if c["id"] in EXAMPLE_TITLES else f"Example {n}"
    for n, c in enumerate(ex, 1)]


def _load_example():
    i = labels.index(st.session_state.example)
    st.session_state.note = ex[i - 1]["state"] if i else ""
    st.session_state.pop("results", None)


st.selectbox("Load an invented example note", labels,
             key="example", on_change=_load_example)
note = st.text_area("Claim note", key="note", height=140)
left, right = st.columns([2, 1])
with left:
    which = st.radio("Question", list(CHOICES), horizontal=True)
with right:
    threshold = st.slider("Automation threshold", min_value=50, max_value=99, value=80,
                          format="%d%%", key="threshold")
    st.caption("Demo setting: answers at or above this confidence are routed "
               "automatically, unless the model's answer did not fit the options; "
               "the rest go to a person.")

if st.button("Score this note", type="primary"):
    if not note.strip():
        st.warning("Paste a claim note first.")
    else:
        try:
            cfg = load_config()
            client = make_client(cfg)
            with st.spinner("Asking the endpoint…"):
                st.session_state.results = {
                    k: ask(note, k, questions, client=client, cfg=cfg) for k in CHOICES[which]}
            st.session_state.results_note = note
        except RuntimeError as e:
            st.error(f"Endpoint configuration problem: {e}")
        except Exception as e:  # noqa: BLE001 - shown to the user, not swallowed
            st.error(f"The endpoint call failed: {type(e).__name__}: {e}")

# --- Results (stored in session state: moving the slider never re-scores) ---
show_raw = st.session_state.get("show_raw", False)  # the switch lives in Technical details
results = st.session_state.get("results")
if not (results and st.session_state.get("results_note") == note):
    results = None
if results:
    example = next((c for c in ex if c["state"] == note), None)
    for col, (key, pred) in zip(st.columns(len(results)), results.items()):
        q = questions[key]
        options = {o["id"]: o for o in q["options"]}
        with col:
            if pred.choice is None:
                st.subheader(QUESTION_LABELS[key])
                st.warning("The model gave no usable answer for this note: "
                           "send to a person to review.")
                continue
            cal = calibrated(pred, temperatures[key]["temperature"])
            st.subheader(headline(QUESTION_LABELS[key], options[pred.choice], cal[pred.choice],
                                  pred.coverage))
            automatic, action = recommended_action(key, options[pred.choice], cal[pred.choice],
                                                   pred.coverage, threshold)
            (st.success if automatic else st.warning)(action)
            st.markdown("**How confident the model is in each option**")
            for oid, opt in options.items():
                text = f"{short_label(opt)} — {percent(cal[oid])}%"
                if show_raw:
                    text += f" · raw model score {pred.probs[oid]:.1%}"
                st.progress(cal[oid], text=text)
                st.caption(opt["description"])
            if example:
                st.caption("Correct answer in the demo data: "
                           f"{short_label(options[example[key]])}")
    st.caption("Confidence was tuned on invented demo notes and may not hold on real claims.")

# --- Technical details (collapsed) ---
with st.expander("Technical details", expanded=False):
    st.markdown("**Endpoint**")
    st.write(f"Model: `{os.environ.get('CAI_MODEL') or 'not set'}`")
    base_url = os.environ.get("CAI_BASE_URL", "")
    st.write("CAI_BASE_URL: " + ("**still the placeholder**" if PLACEHOLDER_HOST in base_url
                                 else "set" if base_url else "**not set**"))
    st.caption("Configured by environment variables in Project Settings. "
               "The endpoint is deployed by hand in Cloudera AI Inference Service.")

    st.markdown("**Calibration**")
    for key, t in temperatures.items():
        st.write(f"{QUESTION_LABELS[key]}: T = {t['temperature']:.3f}")
        st.caption(f"from {t['run']}, fitted on {t['fit_n']} development notes")

    st.toggle("Show raw model scores", key="show_raw")

    if results:
        st.markdown("**This request**")
        for key, pred in results.items():
            st.write(f"{QUESTION_LABELS[key]}: coverage {pred.coverage:.3f}; latency "
                     f"(this endpoint, this request) {pred.latency_ms:.0f} ms")
        st.caption("Coverage is the share of the model's probability that landed on "
                   "the option letters. Only the top-20 log-probabilities are visible, "
                   "so coverage below 1 means some score was not seen.")

    st.markdown("**About these numbers**")
    st.caption("Each option's probability comes from one output token and its top-20 "
               "log-probabilities.")
    st.caption(
        "Synthetic data only: every claim note is invented, with obviously fake policy, "
        "vehicle and phone details. "
        "Calibrated: the model's raw scores rescaled with a temperature fitted on half of "
        "the synthetic development notes (values and source runs above). Raw model "
        "scores are usually 0.99 or higher, including on most wrong answers. Calibration "
        "changes confidence, not the chosen option. "
        "The state / question / options interface follows Jev, as "
        "[SemIf-OpenJev](https://github.com/TheoLeeCJ/SemIf-OpenJev) does.")

# --- Footer ---
st.divider()
st.caption(FOOTER)

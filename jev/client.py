"""
Jev-style decisions over a standard OpenAI-compatible endpoint.

predict(state, question, options) labels each option with a letter (A, B, C,
...), asks the endpoint for exactly ONE output token along with the top
log-probabilities for that token (see TEMPERATURE for why it is 1.0), and
reads the probability of each option letter. The letter probabilities are rescaled to sum to 1 across
the options.

"Coverage" is the total probability that landed on the option letters before
rescaling. Near 1 means the model really was choosing among the options; low
coverage means it wanted to say something else, and the result should not be
trusted. Only the top TOP_K tokens are visible, so an option letter that falls
outside them gets probability 0, and coverage shows how much was missed.

The state / question / options fields follow the Jev interface, as
SemIf-OpenJev does.

Configuration (environment variables)
-------------------------------------
CAI_BASE_URL   OpenAI-compatible base URL of the endpoint, ending in /v1
               (from the endpoint's details page in Cloudera AI Inference Service).
CAI_MODEL      Model id the endpoint expects, e.g. Qwen/Qwen2.5-7B-Instruct.
CAI_TOKEN      Optional inside a Workbench session. Bearer token (CDP access
               token / JWT). If unset, read from /tmp/jwt, which Workbench provides.
CAI_CA_BUNDLE  Optional. Path to a private-cloud CA certificate file. Set to
               "false" to skip certificate checks (test environments only).
CAI_API        Optional. "chat" (default) or "completions".
CAI_DISABLE_THINKING
               Optional, off by default. "1" sends chat_template_kwargs
               enable_thinking=false (vLLM-specific), for models with a thinking
               mode such as Qwen3. Not needed for Qwen2.5.
CAI_TOKENIZER  Optional. Hugging Face tokenizer id, used only by the
               completions API to apply the chat template. Defaults to CAI_MODEL.
TOP_K          Optional. How many top log-probabilities to request (default 20).
"""

import json
import math
import os
import time
from dataclasses import dataclass, field

LETTERS = "ABCDEFGHIJ"

# We read log-probabilities; we don't sample. Temperature only matters if the
# serving engine applies it before returning log-probabilities: then 0 would
# collapse every result to 1.0 / 0.0, and 1.0 is the only value that leaves the
# model's scores untouched. (On Qwen2.5-7B-Instruct on Cloudera AI Inference
# Service, 0 and 1.0 returned identical log-probabilities.) The one sampled
# token is not used to pick the answer.
TEMPERATURE = 1.0


@dataclass
class Prediction:
    choice: str | None          # id of the highest-probability option (None if coverage is 0)
    probs: dict                 # option id -> probability (rescaled to sum to 1), None if coverage is 0
    coverage: float             # probability on the option letters before rescaling
    latency_ms: float           # this endpoint, this request
    token: str = ""             # the one token the model sampled (not used for choice)
    top_logprobs: dict = field(default_factory=dict)  # raw {token: logprob} for that token


PLACEHOLDER_HOST = "YOUR-ENDPOINT"  # default in .project-metadata.yaml


def load_config():
    """Read endpoint settings from environment variables."""
    missing = [k for k in ("CAI_BASE_URL", "CAI_MODEL") if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))
    if PLACEHOLDER_HOST in os.environ["CAI_BASE_URL"]:
        raise RuntimeError("CAI_BASE_URL is still the placeholder from .project-metadata.yaml; "
                           "set your endpoint's URL in Project Settings -> Advanced and "
                           "restart the application.")
    token = os.environ.get("CAI_TOKEN")
    if not token:
        try:
            with open("/tmp/jwt") as f:
                token = json.load(f)["access_token"]
        except (OSError, ValueError, KeyError) as e:
            raise RuntimeError(f"CAI_TOKEN is not set and /tmp/jwt could not be read ({e}).") from e
    ca = os.environ.get("CAI_CA_BUNDLE")
    verify = True if not ca else (False if ca.lower() == "false" else ca)
    api = os.environ.get("CAI_API", "chat").lower()
    if api not in ("chat", "completions"):
        raise RuntimeError(f"CAI_API must be 'chat' or 'completions', got {api!r}")
    return {
        "base": os.environ["CAI_BASE_URL"].rstrip("/"),
        "token": token,
        "model": os.environ["CAI_MODEL"],
        "verify": verify,
        "api": api,
        "top_k": int(os.environ.get("TOP_K", "20")),
        "disable_thinking": os.environ.get("CAI_DISABLE_THINKING", "").lower() in ("1", "true", "yes"),
        "tokenizer": os.environ.get("CAI_TOKENIZER") or os.environ["CAI_MODEL"],
    }


def make_client(cfg):
    import httpx
    from openai import OpenAI

    return OpenAI(
        base_url=cfg["base"],
        api_key=cfg["token"],
        http_client=httpx.Client(verify=cfg["verify"], timeout=60),
        max_retries=0,
    )


def build_prompt_text(state, question, options):
    """The instruction the model sees. Options are labeled with letters."""
    if not 2 <= len(options) <= len(LETTERS):
        raise ValueError(f"need between 2 and {len(LETTERS)} options, got {len(options)}")
    lines = [
        "Read the text and answer the question by choosing one option.",
        "",
        "Text:",
        state,
        "",
        "Question: " + question,
        "",
        "Options:",
    ]
    for letter, opt in zip(LETTERS, options):
        lines.append(f"{letter}. {opt.get('description') or opt['id']}")
    lines += ["", "Answer with the single letter of the best option and nothing else."]
    return "\n".join(lines)


def letter_probs(top, n_options):
    """Turn the top-token log-probabilities into option-letter probabilities.

    Tokens like "A", " A", "A." are all counted toward option A.
    Returns ({letter: probability or None}, coverage)."""
    raw = {letter: 0.0 for letter in LETTERS[:n_options]}
    for token, logprob in top.items():
        key = token.strip().rstrip(".):").upper()
        if key in raw:
            raw[key] += math.exp(logprob)
    coverage = sum(raw.values())
    if coverage == 0:
        return {k: None for k in raw}, 0.0
    return {k: v / coverage for k, v in raw.items()}, coverage


def chat_template_prompt(cfg, text):
    """Build a raw prompt for the completions API from the model's own chat
    template, so it matches what the chat-completions API would send."""
    try:
        from transformers import AutoTokenizer
    except ImportError as e:
        raise RuntimeError("the completions API needs the 'transformers' package "
                           "to apply the model's chat template (pip install transformers)") from e
    try:
        tok = AutoTokenizer.from_pretrained(cfg["tokenizer"])
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"could not load tokenizer '{cfg['tokenizer']}' "
                           f"(set CAI_TOKENIZER to a local path or HF id): {e}") from e
    return tok.apply_chat_template(
        [{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True
    )


def top_logprobs_chat(cfg, client, text):
    """Returns (generated_token, {token: logprob}) using /chat/completions."""
    extra = {}
    if cfg.get("disable_thinking"):
        # vLLM-specific: turn off thinking (Qwen3-style models) so the first token is the answer.
        extra["chat_template_kwargs"] = {"enable_thinking": False}
    try:
        out = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": text}],
            max_tokens=1,
            temperature=TEMPERATURE,
            logprobs=True,
            top_logprobs=cfg["top_k"],
            extra_body=extra or None,
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"/chat/completions request failed: {type(e).__name__}: {e}") from e
    lp = out.choices[0].logprobs
    content = lp.content if lp else None
    if not content:
        raise RuntimeError("Response had no logprobs.content; endpoint may not return log-probabilities.")
    first = content[0]
    return first.token, {t.token: t.logprob for t in first.top_logprobs}


def top_logprobs_completions(cfg, client, text):
    """Returns (generated_token, {token: logprob}) using /completions."""
    prompt = chat_template_prompt(cfg, text)
    try:
        out = client.completions.create(
            model=cfg["model"],
            prompt=prompt,
            max_tokens=1,
            temperature=TEMPERATURE,
            logprobs=cfg["top_k"],
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"/completions request failed: {type(e).__name__}: {e}") from e
    lp = out.choices[0].logprobs
    if not lp or not lp.top_logprobs:
        raise RuntimeError("Response had no logprobs.top_logprobs; endpoint may not return log-probabilities.")
    return lp.tokens[0], dict(lp.top_logprobs[0])


_FETCHERS = {"chat": top_logprobs_chat, "completions": top_logprobs_completions}


def predict(state, question, options, client=None, cfg=None):
    """Score each option for one question about one piece of text.

    options: list of {"id": ..., "description": ...}. Returns a Prediction.
    client/cfg default to an endpoint configured from environment variables."""
    cfg = cfg or load_config()
    client = client or make_client(cfg)
    text = build_prompt_text(state, question, options)
    t0 = time.perf_counter()
    token, top = _FETCHERS[cfg.get("api", "chat")](cfg, client, text)
    latency_ms = (time.perf_counter() - t0) * 1000
    by_letter, coverage = letter_probs(top, len(options))
    probs = {opt["id"]: by_letter[letter] for letter, opt in zip(LETTERS, options)}
    choice = None
    if coverage > 0:
        choice = max(options, key=lambda o: probs[o["id"]])["id"]
    return Prediction(choice, probs, coverage, latency_ms, token, top)

"""
Temperature scaling for option probabilities.

One number, T, is fitted on labeled examples. Each probability vector is
treated as log-probabilities divided by T and re-normalized:

    p_i(T) = p_i ** (1/T) / sum_j p_j ** (1/T)

T > 1 softens the probabilities, T < 1 sharpens them. Because x ** (1/T) is
increasing for T > 0, the order of the options never changes, so the chosen
option stays the same.

Also includes expected calibration error (ECE), the usual measure of whether
"90% confident" answers are right about 90% of the time.
"""

import math

# Options outside the top-k log-probabilities come back with probability 0.
# They are floored here so log() is defined; this never changes the argmax.
EPS = 1e-9


def apply_temperature(probs, T):
    """Rescale one probability vector with temperature T (> 0)."""
    if T <= 0:
        raise ValueError("temperature must be positive")
    logs = [math.log(max(p, EPS)) / T for p in probs]
    m = max(logs)
    exps = [math.exp(x - m) for x in logs]
    s = sum(exps)
    return [e / s for e in exps]


def nll(rows, labels, T):
    """Mean negative log-likelihood of the correct option after scaling.
    rows: list of probability vectors (lengths may differ); labels: index of
    the correct option in each row."""
    total = 0.0
    for probs, y in zip(rows, labels):
        total -= math.log(max(apply_temperature(probs, T)[y], 1e-300))
    return total / len(rows)


def fit_temperature(rows, labels, lo=0.05, hi=20.0, iters=100):
    """Find the T that minimises nll on the labeled rows.

    NLL is convex in 1/T, so a golden-section search over 1/T finds the
    minimum. T is searched within [lo, hi]."""
    if not rows:
        raise ValueError("need at least one labeled row")
    a, b = 1.0 / hi, 1.0 / lo
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = nll(rows, labels, 1 / c), nll(rows, labels, 1 / d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = nll(rows, labels, 1 / c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = nll(rows, labels, 1 / d)
    return 1.0 / ((a + b) / 2)


def expected_calibration_error(confidences, correct, n_bins=10):
    """ECE with equal-width bins over [0, 1].

    confidences: probability of the chosen option per row.
    correct: whether the chosen option was right, per row."""
    if not confidences:
        raise ValueError("need at least one row")
    bins = [[] for _ in range(n_bins)]
    for conf, ok in zip(confidences, correct):
        i = min(int(conf * n_bins), n_bins - 1)
        bins[i].append((conf, 1.0 if ok else 0.0))
    n = len(confidences)
    ece = 0.0
    for b in bins:
        if b:
            avg_conf = sum(c for c, _ in b) / len(b)
            acc = sum(a for _, a in b) / len(b)
            ece += len(b) / n * abs(avg_conf - acc)
    return ece

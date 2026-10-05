"""
Plain-language text for the demo page: short option labels, the headline per
question, and the recommended action for an automation threshold.

Confidence is shown and compared as the same whole percentage, so the
recommended action never contradicts the number on screen.
"""

# Below this coverage the model's answer mostly fell outside the options, so the
# rescaled confidence can't be trusted and a person reviews whatever the threshold.
COVERAGE_FLOOR = 0.95


def percent(p):
    """Probability -> whole percent, rounding halves up (0.795 -> 80)."""
    return int(p * 100 + 0.5)


def short_label(option):
    """The option description up to its first ':' (the plain name of the
    option); the whole description if it has no ':'; the id if it has none."""
    description = option.get("description")
    if not description:
        return option["id"]
    return description.split(":", 1)[0].strip()


UNSURE = ("The model's answer did not fit the listed options well, so its confidence "
          "can't be trusted: send to a person to review")


def headline(question_label, option, confidence, coverage=1.0):
    """e.g. 'Team: Standard claims handling, 91% confident'. Below the coverage
    floor no percentage is shown, as it can't be trusted."""
    if coverage < COVERAGE_FLOOR:
        return f"{question_label}: {short_label(option)}, confidence not reliable"
    return f"{question_label}: {short_label(option)}, {percent(confidence)}% confident"


def automatic_action(question_key, option):
    """What 'automatic' means for this answer, naming the destination."""
    if question_key == "senior_review":
        if option["id"] == "yes":
            return "Send to a senior adjuster automatically"
        if option["id"] == "no":
            return "Skip senior review automatically"
    return f"Route to {short_label(option)} automatically"


def recommended_action(question_key, option, confidence, coverage, threshold_percent):
    """(automatic, text) for the chosen option, its calibrated confidence, the
    prediction's coverage and a threshold in percent."""
    if coverage < COVERAGE_FLOOR:
        return False, UNSURE
    if percent(confidence) >= threshold_percent:
        return True, automatic_action(question_key, option)
    return False, f"Below {threshold_percent}%: send to a person to review"

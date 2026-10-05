"""
Plain-language text for the demo page: short option labels, the headline per
question, and the recommended action for an automation threshold.

Confidence is shown and compared as the same whole percentage, so the
recommended action never contradicts the number on screen.
"""


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


def headline(question_label, option, confidence):
    """e.g. 'Team: Standard claims handling, 91% confident'."""
    return f"{question_label}: {short_label(option)}, {percent(confidence)}% confident"


def recommended_action(confidence, threshold_percent):
    """(automatic, text) for a calibrated confidence and a threshold in percent."""
    if percent(confidence) >= threshold_percent:
        return True, "Confident enough to route automatically"
    return False, f"Below {threshold_percent}%: send to a person to review"

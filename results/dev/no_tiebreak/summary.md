# Evaluation results: Qwen/Qwen2.5-7B-Instruct on synthetic claim notes

300 synthetic first-notice-of-loss notes (data/claims_dev.jsonl), questions from eval/variants/no_tiebreak.json. Each decision requests exactly 1 output token. No speed measurement.

## team

Question: Which team should handle this claim?

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.900 | 0.886 |
| easy | 200 | 0.935 | 0.915 |
| hard | 100 | 0.830 | 0.824 |
| hard: hard_angry_small | 10 | 1.000 | 1.000 |
| hard: hard_distractor_coverage | 10 | 0.600 | 0.600 |
| hard: hard_line_items_over | 8 | 0.875 | 0.875 |
| hard: hard_new_policy_genuine | 10 | 0.800 | 0.800 |
| hard: hard_passing_injury | 12 | 0.333 | 0.333 |
| hard: hard_small_attorney | 6 | 1.000 | 1.000 |
| hard: hard_subtle_coverage | 10 | 0.800 | 0.800 |
| hard: hard_subtle_fraud | 10 | 1.000 | 1.000 |
| hard: hard_two_teams_coverage_injury | 9 | 1.000 | 1.000 |
| hard: hard_two_teams_fraud_injury | 8 | 1.000 | 1.000 |
| hard: hard_unrelated_injury | 7 | 1.000 | 1.000 |

Order check (shuffled, every option moved): chosen answer flipped on 29 of 300 notes (9.7%). Accuracy in permuted order: 0.860.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 4.862; ECE 0.134 -> 0.056; NLL 1.652 -> 0.439.

Chosen-option probability (all notes, before scaling): <0.5: 1, 0.5-0.6: 1, 0.6-0.7: 0, 0.7-0.8: 3, 0.8-0.9: 2, 0.9-0.99: 11, 0.99-1.0: 282

Chosen-option probability (test half, after scaling): <0.5: 3, 0.5-0.6: 4, 0.6-0.7: 6, 0.7-0.8: 4, 0.8-0.9: 7, 0.9-0.99: 126, 0.99-1.0: 0

Coverage: min 1.000, mean 1.0000, below 0.9: 0, no choice: 0.

# Evaluation results: Qwen/Qwen2.5-7B-Instruct on synthetic claim notes

300 synthetic first-notice-of-loss notes (data/claims_test.jsonl), questions from data/questions.json. Each decision requests exactly 1 output token. No speed measurement.

## team

Question: Which team should handle this claim? Only if the note clearly fits more than one team, prefer fraud review, then coverage questions, then injury claims.

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.877 | 0.881 |
| easy | 200 | 0.935 | 0.921 |
| hard | 100 | 0.760 | 0.795 |
| hard: hard_angry_small | 10 | 0.700 | 0.700 |
| hard: hard_distractor_coverage | 10 | 0.600 | 0.600 |
| hard: hard_line_items_over | 8 | 0.375 | 0.375 |
| hard: hard_new_policy_genuine | 10 | 0.700 | 0.700 |
| hard: hard_passing_injury | 12 | 0.583 | 0.583 |
| hard: hard_small_attorney | 6 | 1.000 | 1.000 |
| hard: hard_subtle_coverage | 10 | 0.600 | 0.600 |
| hard: hard_subtle_fraud | 10 | 1.000 | 1.000 |
| hard: hard_two_teams_coverage_injury | 9 | 1.000 | 1.000 |
| hard: hard_two_teams_fraud_injury | 8 | 1.000 | 1.000 |
| hard: hard_unrelated_injury | 7 | 1.000 | 1.000 |

Order check (shuffled, every option moved): chosen answer flipped on 21 of 300 notes (7.0%). Accuracy in permuted order: 0.900.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 5.502; ECE 0.130 -> 0.033; NLL 1.666 -> 0.475.

Chosen-option probability (all notes, before scaling): <0.5: 1, 0.5-0.6: 0, 0.6-0.7: 3, 0.7-0.8: 2, 0.8-0.9: 9, 0.9-0.99: 13, 0.99-1.0: 272

Chosen-option probability (test half, after scaling): <0.5: 7, 0.5-0.6: 7, 0.6-0.7: 5, 0.7-0.8: 7, 0.8-0.9: 53, 0.9-0.99: 71, 0.99-1.0: 0

Coverage: min 1.000, mean 1.0000, below 0.9: 0, no choice: 0.

## senior_review

Question: Should a senior adjuster review this claim before any payment?

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.873 | 0.822 |
| easy | 200 | 0.905 | 0.870 |
| hard | 100 | 0.810 | 0.736 |
| hard: hard_angry_small | 10 | 0.600 | 0.600 |
| hard: hard_distractor_coverage | 10 | 1.000 | 1.000 |
| hard: hard_line_items_over | 8 | 1.000 | 1.000 |
| hard: hard_new_policy_genuine | 10 | 1.000 | 1.000 |
| hard: hard_passing_injury | 12 | 1.000 | 1.000 |
| hard: hard_small_attorney | 6 | 0.333 | 0.333 |
| hard: hard_subtle_coverage | 10 | 1.000 | 1.000 |
| hard: hard_subtle_fraud | 10 | 0.100 | 0.100 |
| hard: hard_two_teams_coverage_injury | 9 | 1.000 | 1.000 |
| hard: hard_two_teams_fraud_injury | 8 | 0.750 | 0.750 |
| hard: hard_unrelated_injury | 7 | 1.000 | 1.000 |

Order check (reversed): chosen answer flipped on 12 of 300 notes (4.0%). Accuracy in permuted order: 0.900.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 4.018; ECE 0.119 -> 0.035; NLL 0.704 -> 0.316.

Chosen-option probability (all notes, before scaling): <0.5: 0, 0.5-0.6: 4, 0.6-0.7: 3, 0.7-0.8: 8, 0.8-0.9: 5, 0.9-0.99: 33, 0.99-1.0: 247

Chosen-option probability (test half, after scaling): <0.5: 0, 0.5-0.6: 10, 0.6-0.7: 9, 0.7-0.8: 16, 0.8-0.9: 24, 0.9-0.99: 90, 0.99-1.0: 1

Coverage: min 0.996, mean 0.9996, below 0.9: 0, no choice: 0.

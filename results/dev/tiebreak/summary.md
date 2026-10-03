# Evaluation results: Qwen/Qwen2.5-7B-Instruct on synthetic claim notes

300 synthetic first-notice-of-loss notes (data/claims_dev.jsonl), questions from results/dev/tiebreak/questions.json. Each decision requests exactly 1 output token. No speed measurement.

## team

Question: Which team should handle this claim? If more than one team fits, fraud review takes priority, then coverage questions, then injury claims.

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.693 | 0.794 |
| easy | 200 | 0.750 | 0.847 |
| hard | 100 | 0.580 | 0.687 |
| hard: hard_angry_small | 10 | 0.000 | 0.000 |
| hard: hard_distractor_coverage | 10 | 0.500 | 0.500 |
| hard: hard_line_items_over | 8 | 0.000 | 0.000 |
| hard: hard_new_policy_genuine | 10 | 0.400 | 0.400 |
| hard: hard_passing_injury | 12 | 0.583 | 0.583 |
| hard: hard_small_attorney | 6 | 1.000 | 1.000 |
| hard: hard_subtle_coverage | 10 | 0.800 | 0.800 |
| hard: hard_subtle_fraud | 10 | 1.000 | 1.000 |
| hard: hard_two_teams_coverage_injury | 9 | 0.667 | 0.667 |
| hard: hard_two_teams_fraud_injury | 8 | 1.000 | 1.000 |
| hard: hard_unrelated_injury | 7 | 0.571 | 0.571 |

Order check (shuffled, every option moved): chosen answer flipped on 83 of 300 notes (27.7%). Accuracy in permuted order: 0.837.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 6.681; ECE 0.286 -> 0.083; NLL 3.409 -> 0.819.

Chosen-option probability (all notes, before scaling): <0.5: 0, 0.5-0.6: 2, 0.6-0.7: 10, 0.7-0.8: 8, 0.8-0.9: 15, 0.9-0.99: 47, 0.99-1.0: 218

Chosen-option probability (test half, after scaling): <0.5: 7, 0.5-0.6: 28, 0.6-0.7: 14, 0.7-0.8: 32, 0.8-0.9: 69, 0.9-0.99: 0, 0.99-1.0: 0

Coverage: min 1.000, mean 1.0000, below 0.9: 0, no choice: 0.

## senior_review

Question: Should a senior adjuster review this claim before any payment?

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.860 | 0.806 |
| easy | 200 | 0.890 | 0.858 |
| hard | 100 | 0.800 | 0.713 |
| hard: hard_angry_small | 10 | 0.900 | 0.900 |
| hard: hard_distractor_coverage | 10 | 1.000 | 1.000 |
| hard: hard_line_items_over | 8 | 1.000 | 1.000 |
| hard: hard_new_policy_genuine | 10 | 1.000 | 1.000 |
| hard: hard_passing_injury | 12 | 1.000 | 1.000 |
| hard: hard_small_attorney | 6 | 0.167 | 0.167 |
| hard: hard_subtle_coverage | 10 | 1.000 | 1.000 |
| hard: hard_subtle_fraud | 10 | 0.000 | 0.000 |
| hard: hard_two_teams_coverage_injury | 9 | 1.000 | 1.000 |
| hard: hard_two_teams_fraud_injury | 8 | 0.500 | 0.500 |
| hard: hard_unrelated_injury | 7 | 1.000 | 1.000 |

Order check (reversed): chosen answer flipped on 16 of 300 notes (5.3%). Accuracy in permuted order: 0.880.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 4.264; ECE 0.109 -> 0.027; NLL 0.610 -> 0.299.

Chosen-option probability (all notes, before scaling): <0.5: 0, 0.5-0.6: 4, 0.6-0.7: 6, 0.7-0.8: 12, 0.8-0.9: 6, 0.9-0.99: 33, 0.99-1.0: 239

Chosen-option probability (test half, after scaling): <0.5: 0, 0.5-0.6: 11, 0.6-0.7: 14, 0.7-0.8: 15, 0.8-0.9: 29, 0.9-0.99: 81, 0.99-1.0: 0

Coverage: min 0.991, mean 0.9994, below 0.9: 0, no choice: 0.

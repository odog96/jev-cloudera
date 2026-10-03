# Evaluation results: Qwen/Qwen2.5-7B-Instruct on synthetic claim notes

300 synthetic first-notice-of-loss notes (data/claims_dev.jsonl), questions from eval/variants/conditional_tiebreak.json. Each decision requests exactly 1 output token. No speed measurement.

## team

Question: Which team should handle this claim? Only if the note clearly fits more than one team, prefer fraud review, then coverage questions, then injury claims.

| subset | n | accuracy | balanced accuracy |
|---|---|---|---|
| overall | 300 | 0.880 | 0.894 |
| easy | 200 | 0.965 | 0.964 |
| hard | 100 | 0.710 | 0.749 |
| hard: hard_angry_small | 10 | 0.400 | 0.400 |
| hard: hard_distractor_coverage | 10 | 0.600 | 0.600 |
| hard: hard_line_items_over | 8 | 0.250 | 0.250 |
| hard: hard_new_policy_genuine | 10 | 0.800 | 0.800 |
| hard: hard_passing_injury | 12 | 0.250 | 0.250 |
| hard: hard_small_attorney | 6 | 1.000 | 1.000 |
| hard: hard_subtle_coverage | 10 | 0.800 | 0.800 |
| hard: hard_subtle_fraud | 10 | 1.000 | 1.000 |
| hard: hard_two_teams_coverage_injury | 9 | 1.000 | 1.000 |
| hard: hard_two_teams_fraud_injury | 8 | 1.000 | 1.000 |
| hard: hard_unrelated_injury | 7 | 1.000 | 1.000 |

Order check (shuffled, every option moved): chosen answer flipped on 28 of 300 notes (9.3%). Accuracy in permuted order: 0.880.

Calibration (temperature fitted on 150 notes, measured on the other 150): T = 4.781; ECE 0.151 -> 0.058; NLL 1.732 -> 0.495.

Chosen-option probability (all notes, before scaling): <0.5: 1, 0.5-0.6: 2, 0.6-0.7: 3, 0.7-0.8: 3, 0.8-0.9: 4, 0.9-0.99: 21, 0.99-1.0: 266

Chosen-option probability (test half, after scaling): <0.5: 2, 0.5-0.6: 5, 0.6-0.7: 10, 0.7-0.8: 11, 0.8-0.9: 19, 0.9-0.99: 103, 0.99-1.0: 0

Coverage: min 1.000, mean 1.0000, below 0.9: 0, no choice: 0.

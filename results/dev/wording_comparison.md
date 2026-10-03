# Team-question wording comparison (development set, data/claims_dev.jsonl)

Selection rule, fixed before the variant runs: highest balanced accuracy in the original order;
if within 0.01, the lower flip rate wins.

| wording | accuracy | balanced acc. | easy acc. | hard acc. | standard->fraud (orig. order) | standard->fraud (shuffled) | flips |
|---|---|---|---|---|---|---|---|
| tiebreak | 0.693 | 0.794 | 0.750 | 0.580 | 71 of 145 | 15 of 145 | 83 of 300 (27.7%) |
| no_tiebreak | 0.900 | 0.886 | 0.935 | 0.830 | 6 of 145 | 1 of 145 | 29 of 300 (9.7%) |
| conditional_tiebreak | 0.880 | 0.894 | 0.965 | 0.710 | 17 of 145 | 4 of 145 | 28 of 300 (9.3%) |

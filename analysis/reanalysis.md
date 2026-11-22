# Re-analysis: three-way outcomes and scenario-level paired tests


## final / notes: three-way outcome, in-authority attacks (G1-G3)

| Model | Setup | n | Resisted | Blocked before execution | Executed, detected | Executed, undetected |
|---|---|---|---|---|---|---|
| granite4.1:8b | S0 | 72 | 60 (83%) | 0 (0%) | 0 (0%) | 12 (17%) |
| granite4.1:8b | S1 | 72 | 63 (88%) | 0 (0%) | 0 (0%) | 9 (12%) |
| granite4.1:8b | S3 | 72 | 63 (88%) | 0 (0%) | 0 (0%) | 9 (12%) |
| granite4.1:8b | S4 | 72 | 63 (88%) | 6 (8%) | 3 (4%) | 0 (0%) |
| granite4.1:8b | S5 | 72 | 63 (88%) | 6 (8%) | 3 (4%) | 0 (0%) |
| granite4.1:8b | S5noL1 | 72 | 60 (83%) | 9 (12%) | 3 (4%) | 0 (0%) |
| qwen3:14b | S0 | 72 | 48 (67%) | 0 (0%) | 0 (0%) | 24 (33%) |
| qwen3:14b | S3 | 72 | 42 (58%) | 0 (0%) | 0 (0%) | 30 (42%) |
| qwen3:14b | S5 | 72 | 42 (58%) | 18 (25%) | 9 (12%) | 3 (4%) |
| qwen3:8b | S0 | 72 | 44 (61%) | 0 (0%) | 0 (0%) | 28 (39%) |
| qwen3:8b | S1 | 72 | 44 (61%) | 0 (0%) | 0 (0%) | 28 (39%) |
| qwen3:8b | S3 | 72 | 44 (61%) | 0 (0%) | 0 (0%) | 28 (39%) |
| qwen3:8b | S4 | 72 | 44 (61%) | 15 (21%) | 10 (14%) | 3 (4%) |
| qwen3:8b | S5 | 72 | 44 (61%) | 15 (21%) | 10 (14%) | 3 (4%) |
| qwen3:8b | S5noL1 | 72 | 44 (61%) | 15 (21%) | 10 (14%) | 3 (4%) |

**G0 (out-of-authority) attacks, final/notes:** granite4.1:8b S0: 24/0/0/0; granite4.1:8b S1: 24/0/0/0; granite4.1:8b S3: 24/0/0/0; granite4.1:8b S4: 24/0/0/0; granite4.1:8b S5: 24/0/0/0; granite4.1:8b S5noL1: 24/0/0/0; qwen3:14b S0: 22/0/0/2; qwen3:14b S3: 24/0/0/0; qwen3:14b S5: 24/0/0/0; qwen3:8b S0: 24/0/0/0; qwen3:8b S1: 24/0/0/0; qwen3:8b S3: 24/0/0/0; qwen3:8b S4: 24/0/0/0; qwen3:8b S5: 24/0/0/0; qwen3:8b S5noL1: 24/0/0/0 (resisted/blocked/exec-detected/exec-undetected)

## final / sensor: three-way outcome, in-authority attacks (G1-G3)

| Model | Setup | n | Resisted | Blocked before execution | Executed, detected | Executed, undetected |
|---|---|---|---|---|---|---|
| granite4.1:8b | S0 | 24 | 16 (67%) | 0 (0%) | 0 (0%) | 8 (33%) |
| granite4.1:8b | S3 | 24 | 18 (75%) | 0 (0%) | 0 (0%) | 6 (25%) |
| granite4.1:8b | S4 | 24 | 18 (75%) | 0 (0%) | 0 (0%) | 6 (25%) |
| granite4.1:8b | S5 | 24 | 18 (75%) | 0 (0%) | 6 (25%) | 0 (0%) |
| granite4.1:8b | S5noL1 | 24 | 16 (67%) | 0 (0%) | 5 (21%) | 3 (12%) |
| qwen3:14b | S0 | 24 | 13 (54%) | 0 (0%) | 0 (0%) | 11 (46%) |
| qwen3:14b | S3 | 24 | 15 (62%) | 0 (0%) | 0 (0%) | 9 (38%) |
| qwen3:14b | S5 | 24 | 15 (62%) | 6 (25%) | 0 (0%) | 3 (12%) |
| qwen3:8b | S0 | 24 | 15 (62%) | 0 (0%) | 0 (0%) | 9 (38%) |
| qwen3:8b | S3 | 24 | 15 (62%) | 0 (0%) | 0 (0%) | 9 (38%) |
| qwen3:8b | S4 | 24 | 15 (62%) | 0 (0%) | 0 (0%) | 9 (38%) |
| qwen3:8b | S5 | 24 | 15 (62%) | 0 (0%) | 6 (25%) | 3 (12%) |
| qwen3:8b | S5noL1 | 24 | 15 (62%) | 0 (0%) | 6 (25%) | 3 (12%) |

## heldout / heldout: three-way outcome, in-authority attacks (G1-G3)

| Model | Setup | n | Resisted | Blocked before execution | Executed, detected | Executed, undetected |
|---|---|---|---|---|---|---|
| granite4.1:8b | S0 | 56 | 46 (82%) | 0 (0%) | 0 (0%) | 10 (18%) |
| granite4.1:8b | S3 | 56 | 50 (89%) | 0 (0%) | 0 (0%) | 6 (11%) |
| granite4.1:8b | S5noL1 | 56 | 46 (82%) | 2 (4%) | 0 (0%) | 8 (14%) |
| qwen3:14b | S0 | 56 | 52 (93%) | 0 (0%) | 0 (0%) | 4 (7%) |
| qwen3:14b | S5noL1 | 56 | 52 (93%) | 4 (7%) | 0 (0%) | 0 (0%) |
| qwen3:8b | S0 | 56 | 54 (96%) | 0 (0%) | 0 (0%) | 2 (4%) |
| qwen3:8b | S3 | 56 | 49 (88%) | 0 (0%) | 0 (0%) | 7 (12%) |
| qwen3:8b | S5noL1 | 56 | 54 (96%) | 0 (0%) | 2 (4%) | 0 (0%) |

## Scenario-level paired tests: in-authority undetected (Holm over all rows)

Each attack scenario is one pair; seeds are summed inside the scenario. Sign-flip = exact permutation test on per-scenario differences. CI = paired cluster bootstrap (resampling scenarios) of the difference in rates. McNemar on scenario x seed pairs is a secondary check (assumes seeds independent). Holm is applied within each set to the pre-specified primary comparisons (marked P); other rows are exploratory.

| Set | Model | A | B | P | Undetected A | Undetected B | Scenarios that differ | Difference A-B [95% CI] | p sign-flip | p (Holm) | McNemar p (pairs A-only/B-only) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| final/notes | granite4.1:8b | S0 | S5 | P | 12/72 | 0/72 | 4/24 | +16.7 pp [+4.2, +33.3] | 0.1250 | 0.2500 | 0.0005 (12/0) |
| final/notes | granite4.1:8b | S3 | S5 | P | 9/72 | 0/72 | 4/24 | +12.5 pp [+1.4, +25.0] | 0.1250 | 0.2500 | 0.0039 (9/0) |
| final/notes | granite4.1:8b | S5noL1 | S5 |  | 0/72 | 0/72 | 0/24 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/notes | granite4.1:8b | S0 | S5noL1 |  | 12/72 | 0/72 | 4/24 | +16.7 pp [+4.2, +33.3] | 0.1250 | – | 0.0005 (12/0) |
| final/notes | granite4.1:8b | S3 | S5noL1 |  | 9/72 | 0/72 | 4/24 | +12.5 pp [+1.4, +25.0] | 0.1250 | – | 0.0039 (9/0) |
| final/notes | granite4.1:8b | S0 | S3 |  | 12/72 | 9/72 | 3/24 | +4.2 pp [-2.8, +15.3] | 0.7500 | – | 0.3750 (4/1) |
| final/notes | granite4.1:8b | S0 | S4 |  | 12/72 | 0/72 | 4/24 | +16.7 pp [+4.2, +33.3] | 0.1250 | – | 0.0005 (12/0) |
| final/notes | granite4.1:8b | S4 | S5 |  | 0/72 | 0/72 | 0/24 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/notes | qwen3:14b | S0 | S5 | P | 24/72 | 3/72 | 8/24 | +29.2 pp [+12.5, +48.6] | 0.0078 | 0.0234 | 0.0000 (21/0) |
| final/notes | qwen3:14b | S3 | S5 | P | 30/72 | 3/72 | 9/24 | +37.5 pp [+16.7, +58.3] | 0.0039 | 0.0234 | 0.0000 (27/0) |
| final/notes | qwen3:14b | S0 | S3 |  | 24/72 | 30/72 | 3/24 | -8.3 pp [-19.4, +0.0] | 0.2500 | – | 0.0312 (0/6) |
| final/notes | qwen3:8b | S0 | S5 | P | 28/72 | 3/72 | 9/24 | +34.7 pp [+16.7, +54.2] | 0.0039 | 0.0234 | 0.0000 (25/0) |
| final/notes | qwen3:8b | S3 | S5 | P | 28/72 | 3/72 | 9/24 | +34.7 pp [+16.7, +54.2] | 0.0039 | 0.0234 | 0.0000 (25/0) |
| final/notes | qwen3:8b | S5noL1 | S5 |  | 3/72 | 3/72 | 0/24 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/notes | qwen3:8b | S0 | S5noL1 |  | 28/72 | 3/72 | 9/24 | +34.7 pp [+16.7, +54.2] | 0.0039 | – | 0.0000 (25/0) |
| final/notes | qwen3:8b | S3 | S5noL1 |  | 28/72 | 3/72 | 9/24 | +34.7 pp [+16.7, +54.2] | 0.0039 | – | 0.0000 (25/0) |
| final/notes | qwen3:8b | S0 | S3 |  | 28/72 | 28/72 | 0/24 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (1/1) |
| final/notes | qwen3:8b | S0 | S4 |  | 28/72 | 3/72 | 9/24 | +34.7 pp [+16.7, +54.2] | 0.0039 | – | 0.0000 (25/0) |
| final/notes | qwen3:8b | S4 | S5 |  | 3/72 | 3/72 | 0/24 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/sensor | granite4.1:8b | S0 | S5 | P | 8/24 | 0/24 | 3/8 | +33.3 pp [+8.3, +66.7] | 0.2500 | 1.0000 | 0.0078 (8/0) |
| final/sensor | granite4.1:8b | S3 | S5 | P | 6/24 | 0/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | 1.0000 | 0.0312 (6/0) |
| final/sensor | granite4.1:8b | S5noL1 | S5 |  | 3/24 | 0/24 | 1/8 | +12.5 pp [+0.0, +37.5] | 1.0000 | – | 0.2500 (3/0) |
| final/sensor | granite4.1:8b | S0 | S5noL1 |  | 8/24 | 3/24 | 2/8 | +20.8 pp [+0.0, +50.0] | 0.5000 | – | 0.0625 (5/0) |
| final/sensor | granite4.1:8b | S3 | S5noL1 |  | 6/24 | 3/24 | 3/8 | +12.5 pp [-25.0, +50.0] | 1.0000 | – | 0.5078 (6/3) |
| final/sensor | granite4.1:8b | S0 | S3 |  | 8/24 | 6/24 | 2/8 | +8.3 pp [-12.5, +37.5] | 1.0000 | – | 0.6250 (3/1) |
| final/sensor | granite4.1:8b | S0 | S4 |  | 8/24 | 6/24 | 2/8 | +8.3 pp [-12.5, +37.5] | 1.0000 | – | 0.6250 (3/1) |
| final/sensor | granite4.1:8b | S4 | S5 |  | 6/24 | 0/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | – | 0.0312 (6/0) |
| final/sensor | qwen3:14b | S0 | S5 | P | 11/24 | 3/24 | 3/8 | +33.3 pp [+0.0, +62.5] | 0.2500 | 1.0000 | 0.0078 (8/0) |
| final/sensor | qwen3:14b | S3 | S5 | P | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | 1.0000 | 0.0312 (6/0) |
| final/sensor | qwen3:14b | S0 | S3 |  | 11/24 | 9/24 | 4/8 | +8.3 pp [-37.5, +50.0] | 1.0000 | – | 0.7539 (6/4) |
| final/sensor | qwen3:8b | S0 | S5 | P | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | 1.0000 | 0.0312 (6/0) |
| final/sensor | qwen3:8b | S3 | S5 | P | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | 1.0000 | 0.0312 (6/0) |
| final/sensor | qwen3:8b | S5noL1 | S5 |  | 3/24 | 3/24 | 0/8 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/sensor | qwen3:8b | S0 | S5noL1 |  | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | – | 0.0312 (6/0) |
| final/sensor | qwen3:8b | S3 | S5noL1 |  | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | – | 0.0312 (6/0) |
| final/sensor | qwen3:8b | S0 | S3 |  | 9/24 | 9/24 | 0/8 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/sensor | qwen3:8b | S0 | S4 |  | 9/24 | 9/24 | 0/8 | +0.0 pp [+0.0, +0.0] | 1.0000 | – | 1.0000 (0/0) |
| final/sensor | qwen3:8b | S4 | S5 |  | 9/24 | 3/24 | 2/8 | +25.0 pp [+0.0, +62.5] | 0.5000 | – | 0.0312 (6/0) |
| heldout/heldout | granite4.1:8b | S0 | S5noL1 | P | 10/56 | 8/56 | 1/28 | +3.6 pp [+0.0, +10.7] | 1.0000 | 1.0000 | 0.5000 (2/0) |
| heldout/heldout | granite4.1:8b | S3 | S5noL1 | P | 6/56 | 8/56 | 1/28 | -3.6 pp [-10.7, +0.0] | 1.0000 | 1.0000 | 0.5000 (0/2) |
| heldout/heldout | granite4.1:8b | S0 | S3 |  | 10/56 | 6/56 | 2/28 | +7.1 pp [+0.0, +17.9] | 0.5000 | – | 0.1250 (4/0) |
| heldout/heldout | qwen3:14b | S0 | S5noL1 | P | 4/56 | 0/56 | 2/28 | +7.1 pp [+0.0, +17.9] | 0.5000 | 1.0000 | 0.1250 (4/0) |
| heldout/heldout | qwen3:8b | S0 | S5noL1 | P | 2/56 | 0/56 | 1/28 | +3.6 pp [+0.0, +10.7] | 1.0000 | 1.0000 | 0.5000 (2/0) |
| heldout/heldout | qwen3:8b | S3 | S5noL1 | P | 7/56 | 0/56 | 4/28 | +12.5 pp [+1.8, +25.0] | 0.1250 | 0.6250 | 0.0156 (7/0) |
| heldout/heldout | qwen3:8b | S0 | S3 |  | 2/56 | 7/56 | 3/28 | -8.9 pp [-19.6, +0.0] | 0.2500 | – | 0.0625 (0/5) |

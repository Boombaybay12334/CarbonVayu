# CarbonVayu Complete Pipeline Report

## 1) Executive Summary
This document explains the full CarbonVayu scoring system implemented in the current run: M2 transport matrix, M3 effort multiplier, and VT final scoring engine.

The pipeline is fully operational and produces all required outputs. Mathematically, it is internally consistent and reproducible. However, the current data scales and thresholds create important interpretation risks:
- VT top-end clipping occurs (3 states at 700).
- Fine-claim generation is empty because harm magnitudes are much smaller than the fixed 0.5 MT threshold.
- Absorption values are much larger than emissions in the current input tables, which can dominate score behavior.

## 2) Inputs and Data Sources
The implementation uses these inputs:
- ERA5 file: [data/era5.nc](data/era5.nc)
- Absorption: [data/m1b.csv](data/m1b.csv)
- Emissions panel: [data/m1a/state_emissions_panel_2015_2022.csv](data/m1a/state_emissions_panel_2015_2022.csv)
- Emissions 2022: [data/m1a/state_emissions_2022.csv](data/m1a/state_emissions_2022.csv)

ERA5 structure detected in this run:
- Variables: u, v
- Dimensions: valid_time=36, pressure_level=1, latitude=141, longitude=141

## 3) End-to-End Architecture
Pipeline order:
1. M2 computes inter-state atmospheric transport matrix and confidence.
2. M3 computes state-level effort multiplier from 5 signals.
3. VT engine combines absorption, M2 harms/credits, M3 multiplier, and historical baseline correction into final 300-700 score.
4. Fine-claims are auto-generated from M2 + confidence using threshold rules.

Code entry point:
- [pipeline_m2_m3_vt.py](pipeline_m2_m3_vt.py)

## 4) M2 Module: Atmospheric Transport Matrix (28x28)
### 4.1 What M2 measures
For source state i and target state j:
- M[i][j] is transported harm in MT CO2e from i to j.

Diagonal M[i][i] is self-retained emissions.
Off-diagonal M[i][j] is exported transport burden.

### 4.2 M2 algorithm logic
1. For each state centroid, interpolate ERA5 u and v winds (nearest grid).
2. Compute monthly wind direction toward:
   direction = degrees(atan2(u, v)).
3. For each source-target pair, compute geodesic bearing and distance.
4. Compute angular difference between source wind direction and source-to-target bearing.
5. If angle difference <= 60 degrees, monthly weight contributes as:
   cos(angle_diff) / distance_km^2
   else 0.
6. Average monthly weights and normalize off-diagonal row weights to sum to 1.
7. Compute diagonal retention fraction per state:
   area / (area + 50000)
8. Populate matrix using 2022 emissions:
   - diagonal = emission * diagonal_frac
   - off-diagonal = emission * (1 - diagonal_frac) * normalized_weight
9. Confidence per pair is derived from circular standard deviation of monthly angle offsets.
10. High-confidence corridor overrides are applied to confidence only (M values are not altered).

### 4.3 M2 derived indicators
From M:
- own_emission_mt = diagonal
- exported_harm_mt = row off-diagonal sum
- received_credit_mt = column off-diagonal sum

### 4.4 M2 quality from this run
- Matrix shape correct: 28x28
- Row conservation error near zero: 1.64e-15 maximum absolute error
- Mean diagonal share: 56.44%
- Diagonal sanity checks match expectations:
  - Goa: 0.0689
  - Delhi proxy: 0.2997
  - Madhya Pradesh: 0.8604
  - Rajasthan: 0.8725

Interpretation:
- M2 is numerically stable and physically directional.
- Confidence is sparse by design because unstable directional pairs are zeroed.

## 5) M3 Module: Effort Multiplier
### 5.1 Goal
M3 estimates state effort and maps it into multiplier range [0.5, 2.0].

### 5.2 Signals
- S1: Emission trend (2019 to 2022 change scaled by 5% rule)
- S2: Renewable fraction (hardcoded values)
- S3: Forest health proxy (normalized absorption)
- S4: AQI trend transform
- S5: Compliance proxy set equal to S1

### 5.3 Archetype weighting
Each state belongs to F, I, or M archetype and uses archetype-specific signal weights.

Effort formula:
- effort_multiplier = 0.5 + 1.5 * weighted_average(S1..S5)

### 5.4 M3 quality from this run
- Shape correct: 28 rows
- Multiplier range observed: 0.665 to 1.698
- All multipliers are within [0.5, 2.0]

Archetype means in this run:
- F: 1.265
- I: 0.988
- M: 0.963

Interpretation:
- M3 behaves as intended and differentiates archetypes.
- Since S5 = S1, trend signal is effectively double-represented.

## 6) VT Engine: Original Formula (300-700)
### 6.1 Baseline correction principle
Each state is evaluated against its own expected baseline (2019-2021 net balance), not against neighbors.

baseline_expected[state] = absorption - mean(emissions_2019_2021)

### 6.2 Raw balance for scoring year 2022
raw_balance = absorption - own_emission - exported_harm + received_credit

This preserves victim protection by adding received_credit rather than penalizing receivers.

### 6.3 Effort adjustment
adjusted_balance = raw_balance * effort_multiplier

### 6.4 Excess over baseline
excess_over_baseline = adjusted_balance - baseline_expected

### 6.5 Robust normalization to VT
Using all states:
- median_excess and IQR are computed.
- z = (x - median_excess) / (IQR/2)
- VT = clip(500 + z*85, 300, 700)

This maps median near 500 with robust scaling, reducing outlier compression relative to min-max scaling.

## 7) Fine Claims Engine
Rule:
- Include claim if confidence > 0.75 and M[i][j] > 0.5 MT.
- fine_vt_units = harm_mt * confidence

Current run result:
- No rows in [outputs/fine_claims.csv](outputs/fine_claims.csv)

Why empty:
- Even high-confidence links have low harm magnitude in current matrix.
- Maximum harm among confidence>0.75 links is ~0.0219 MT, far below 0.5 MT threshold.

## 8) Current Output Review
Generated files:
- [outputs/M2_matrix.csv](outputs/M2_matrix.csv)
- [outputs/M2_confidence.csv](outputs/M2_confidence.csv)
- [outputs/M2_derived.csv](outputs/M2_derived.csv)
- [outputs/M3_effort.csv](outputs/M3_effort.csv)
- [outputs/VT_scores_final.csv](outputs/VT_scores_final.csv)
- [outputs/fine_claims.csv](outputs/fine_claims.csv)

Key diagnostics:
- VT clipped at 700 for 3 states
- VT clipped at 300 for 0 states
- Penalty zone (VT < 500): 14 states
- Incentive zone (VT >= 500): 14 states

## 9) Strengths
1. Full formula fidelity to requested logic.
2. Strong modularity and reproducibility.
3. Conservation consistency in M2.
4. Clear policy structure: own harm, exported harm, victim protection credit, effort correction, baseline fairness.
5. Robust normalization framework around median and IQR.

## 10) Weaknesses and Risks
1. Scale mismatch risk:
   Absorption values are much larger than emissions in current data, which can dominate score behavior.
2. VT saturation risk:
   3 states clipping at 700 indicates top-tail compression.
3. Fine-claims threshold mismatch:
   Harm threshold 0.5 MT is far above observed off-diagonal magnitudes.
4. Signal coupling in M3:
   S5 duplicates S1, reducing effective signal diversity.
5. Spatial simplification:
   Single centroid per state may miss intra-state transport heterogeneity.
6. Temporal smoothing:
   Monthly averaging across all available periods can dilute seasonal transport dynamics.

## 11) Interpretation Guidance
How to read VT:
- VT >= 500 suggests performance above own historical baseline after transport and effort adjustment.
- VT < 500 suggests underperformance against own baseline.

What VT is not:
- It is not a pure emissions ranking.
- It is not a direct measure of absolute climate goodness.
- It is a relative, baseline-adjusted, effort-weighted performance index with transport accountability.

## 12) Recommended Next Calibration Steps
1. Re-tune fine-claim threshold from fixed 0.5 MT to a distribution-based threshold (for example top decile of harms among high-confidence links).
2. Reduce clipping pressure by tuning robust scale factor (currently 85) or adding soft-tail handling while preserving 300-700 envelope.
3. Validate unit compatibility between absorption and emissions sources.
4. Introduce uncertainty bands for M2 edges using confidence levels.
5. Consider multi-point state wind sampling instead of single centroid.
6. Split seasonal transport diagnostics (monsoon vs non-monsoon) to improve explainability.

## 13) Bottom Line
The pipeline is a strong functional implementation of the designed economics and atmospheric logic. It is ready for iterative calibration and policy simulation, but current output behavior indicates that threshold and scale calibration is still needed before high-stakes governance use.

# CarbonVayu Deep Technical Report

## Scope
This report explains the full production pipeline implemented in [pipeline_m2_m3_vt.py](pipeline_m2_m3_vt.py):
1. M2 atmospheric transport matrix
2. M3 effort multiplier
3. VT final score engine (300-700)
4. Fine-claim generation

It includes exact formulas, data nature, interpretation, and run-specific conclusions based on:
- [outputs/M2_matrix.csv](outputs/M2_matrix.csv)
- [outputs/M2_confidence.csv](outputs/M2_confidence.csv)
- [outputs/M2_derived.csv](outputs/M2_derived.csv)
- [outputs/M3_effort.csv](outputs/M3_effort.csv)
- [outputs/VT_scores_final.csv](outputs/VT_scores_final.csv)
- [outputs/fine_claims.csv](outputs/fine_claims.csv)

---

## 1) What This Model Is (and Is Not)
### What it is
A deterministic climate-accounting and incentive engine with transport physics:
- Deterministic means the same inputs always produce same outputs.
- Physics-informed means wind-direction transport affects interstate accountability.
- Baseline-corrected means states are judged versus their own historical context.

### What it is not
A trained predictive ML model (no learned weights from supervised training in the current pipeline).
- No neural network, no gradient descent, no model fitting stage.
- The only statistical elements are robust scaling and circular statistics.

If you call the whole system "ML pipeline", the most accurate phrasing is:
- "Data-science scoring pipeline with physics + rule-based policy logic."

---

## 2) Nature of Data
### 2.1 Input datasets and structure
1. ERA5 wind dataset [data/era5.nc](data/era5.nc)
- Variables: u, v
- Dims: valid_time=36, pressure_level=1, latitude=141, longitude=141
- Type: gridded, monthly atmospheric vector field over India domain

2. Absorption data [data/m1b.csv](data/m1b.csv)
- Columns: state, absorption_mtco2_per_year
- Type: annual state-level scalar (proxy repeated across years for baseline)

3. Emission panel [data/m1a/state_emissions_panel_2015_2022.csv](data/m1a/state_emissions_panel_2015_2022.csv)
- Columns: state, year, total_emission_mt
- Type: longitudinal state panel (2015-2022)

4. Emission scoring year [data/m1a/state_emissions_2022.csv](data/m1a/state_emissions_2022.csv)
- Columns: state, total_emission_mt
- Type: one-year snapshot used by M2 matrix scaling

### 2.2 Data characteristics that matter mathematically
1. Strong scale imbalance: absorption values are much larger than emissions in current files.
2. Spatial abstraction: each state represented by one centroid point.
3. Temporal abstraction: ERA5 winds averaged into pairwise weights across all available months.
4. Categorical archetyping: states assigned to F/I/M with fixed weights.

---

## 3) M2 Math: Transport Matrix
Let states be indexed by $i,j \in \{1,...,28\}$ and months by $m$.

### 3.1 Wind direction and speed at state centroid
From ERA5-interpolated vectors for source state $i$ at month $m$:

$$
\theta_{i,m} = \left(\operatorname{deg}(\operatorname{atan2}(u_{i,m}, v_{i,m})) + 360\right) \bmod 360
$$

$$
s_{i,m} = \sqrt{u_{i,m}^2 + v_{i,m}^2}
$$

### 3.2 Geometric terms between states
For pair $(i,j)$:
- Bearing from centroid $i$ to centroid $j$: $\beta_{ij}$
- Geodesic distance in km: $d_{ij}$

Circular angular difference:

$$
\Delta_{ijm} = \min\left(|\theta_{i,m} - \beta_{ij}|, 360 - |\theta_{i,m} - \beta_{ij}|\right)
$$

### 3.3 Monthly directional raw weights

$$
w^{raw}_{ijm} =
\begin{cases}
\frac{\cos(\Delta_{ijm} \pi / 180)}{d_{ij}^2}, & \Delta_{ijm} \le 60^\circ \\
0, & \Delta_{ijm} > 60^\circ
\end{cases}
$$

### 3.4 Average and row-normalize off-diagonals

$$
\bar w_{ij} = \frac{1}{M}\sum_m w^{raw}_{ijm}
$$

For $j \ne i$:

$$
\tilde w_{ij} = \frac{\bar w_{ij}}{\sum_{k \ne i} \bar w_{ik}}
$$

Hence, for each row $i$, off-diagonal normalized shares sum to 1 (if denominator positive).

### 3.5 Self-retention diagonal fraction

$$
r_i = \frac{A_i}{A_i + 50000}
$$

where $A_i$ is state area in km2.

### 3.6 Build transport matrix from 2022 emissions $E_i$

$$
M_{ii} = E_i r_i
$$

$$
M_{ij} = E_i (1-r_i)\tilde w_{ij}, \quad i \ne j
$$

### 3.7 Confidence matrix
For non-zero off-diagonal links, compute circular std dev of monthly directional offsets:

$$
\sigma^{circ}_{ij} = \operatorname{circstd}(\theta_{i,m} - \beta_{ij})
$$

Confidence assignment:
- if $\sigma^{circ}_{ij} < 20^\circ$: 0.80
- else if $\sigma^{circ}_{ij} < 50^\circ$: 0.65
- else: 0.0

Then apply corridor overrides for selected known pairs (confidence only, no change to $M$).

### 3.8 Derived accountability terms

$$
\text{own}_i = M_{ii}
$$

$$
\text{exported}_i = \sum_{j \ne i} M_{ij}
$$

$$
\text{received}_i = \sum_{j \ne i} M_{ji}
$$

---

## 4) M3 Math: Effort Multiplier
For each state $i$, compute five normalized signals.

### 4.1 Signal S1: emission trend
Using panel values $E_{i,2019}$ and $E_{i,2022}$:

$$
\delta_i = \frac{E_{i,2022} - E_{i,2019}}{E_{i,2019}}
$$

$$
S1_i = \operatorname{clip}\left(1 - \frac{\delta_i}{0.05}, 0, 1\right)
$$

### 4.2 Signal S2: renewable share

$$
S2_i = RE_i
$$

### 4.3 Signal S3: forest health proxy
If $Abs_i$ is absorption and $Abs_{max}$ is max across states:

$$
S3_i = \operatorname{clip}\left(\frac{Abs_i}{Abs_{max}}, 0, 1\right)
$$

### 4.4 Signal S4: AQI trend proxy
Given hardcoded $\Delta AQI_i$:

$$
S4_i = \operatorname{clip}\left(0.5 - \frac{\Delta AQI_i}{40}, 0, 1\right)
$$

### 4.5 Signal S5: compliance proxy

$$
S5_i = S1_i
$$

### 4.6 Archetype-weighted aggregate and multiplier
For archetype-specific weights $\omega_k$ over $k\in\{S1,S2,S3,S4,S5\}$:

$$
\bar S_i = \sum_k \omega_k S_{k,i}
$$

$$
Eff_i = 0.5 + 1.5\bar S_i
$$

By construction: $Eff_i \in [0.5, 2.0]$.

---

## 5) VT Math: Final Score Engine
### 5.1 Baseline expected net balance
Using 2019-2021 mean emissions:

$$
Baseline_i = Abs_i - \operatorname{mean}(E_{i,2019}, E_{i,2020}, E_{i,2021})
$$

### 5.2 Raw scoring-year balance (2022)

$$
Raw_i = Abs_i - own_i - exported_i + received_i
$$

Victim protection is explicit through $+received_i$.

### 5.3 Effort-adjusted balance

$$
Adj_i = Raw_i \cdot Eff_i
$$

### 5.4 Excess-over-baseline

$$
X_i = Adj_i - Baseline_i
$$

### 5.5 Robust normalization to 300-700
Across all states:
- median $m = \operatorname{median}(X)$
- IQR $q = P75(X)-P25(X)$

$$
z_i = \frac{X_i - m}{q/2}
$$

$$
VT_i = \operatorname{clip}(500 + 85z_i, 300, 700)
$$

Interpretation targets:
- median maps to ~500
- tails map toward 330 and 670 bands under typical spread
- clipping only for extreme outliers

---

## 6) Fine-Claims Math
For each directed pair $(i,j)$, $i\ne j$:

Claim exists iff:

$$
Confidence_{ij} > 0.75 \quad \text{and} \quad M_{ij} > 0.5
$$

Fine units:

$$
Fine_{ij} = M_{ij} \cdot Confidence_{ij}
$$

---

## 7) Run-Specific Conclusive Output (Current Execution)
### 7.1 VT distribution
- Mean: 499.794
- Median: 500.000
- Std: 115.900
- Min: 303.508
- Max: 700.000
- Penalty zone VT<500: 14 states
- Incentive zone VT>=500: 14 states
- Exact clipping at 300: 0 states
- Exact clipping at 700: 3 states

### 7.2 Top and bottom VT outcomes
Top 5 include:
- Arunachal Pradesh (700)
- Maharashtra (700)
- Nagaland (700)
- Tripura (661.535)
- Madhya Pradesh (650.431)

Bottom 5 include:
- Uttar Pradesh (303.508)
- Jharkhand (321.542)
- Telangana (370.821)
- Bihar (378.025)
- Andhra Pradesh (392.848)

### 7.3 M2 diagnostics
- Total off-diagonal transported harm: 0.96846 MT
- Row-conservation max error: 1.64e-15 (excellent)
- Non-zero confidence cells: 212 of 784
- High-confidence (>0.75) cells: 18
- Top exporter states: Tamil Nadu, West Bengal, Chhattisgarh
- Top receiver states: Kerala, West Bengal, Goa

### 7.4 M3 diagnostics
- Effort min: 0.665
- Effort max: 1.698
- Archetype means:
  - F: 1.265
  - I: 0.988
  - M: 0.963

### 7.5 Fine-claims
- Count: 0
- Reason: observed high-confidence transport magnitudes are far below the fixed 0.5 MT trigger.

---

## 8) Why These Results Happened
### 8.1 Main driver: scale dominance
Absorption scale is much larger than emissions and transported harms in current tables. This pushes:
- Raw balances strongly positive for many states
- Baseline-corrected outcomes to depend heavily on effort scaling and small deltas

### 8.2 Secondary driver: effort multiplier sensitivity
Because VT uses $Adj_i = Raw_i \cdot Eff_i$, multiplier spread strongly affects rank movement when raw balances are large.

### 8.3 Transport claims sparsity
The directional physics creates small off-diagonal masses after distance-squared damping and self-retention. Therefore fixed 0.5 MT claim threshold becomes too high for this run.

### 8.4 Tail saturation at top
Three states reached 700 due high excess-over-baseline relative to robust scale parameter (85 factor after IQR scaling).

---

## 9) Strengths
1. Full formula fidelity and deterministic reproducibility.
2. Excellent conservation and accounting in M2.
3. Transparent modular decomposition and inspectable outputs.
4. Fairness intent preserved: baseline correction + victim protection.
5. Robust normalization avoids min-max distortion in center distribution.

## 10) Weaknesses / Risks
1. Unit/scale mismatch risk between absorption and emissions can dominate scores.
2. Top-tail clipping indicates possible calibration pressure.
3. Fine-claim threshold currently misaligned with observed harm magnitudes.
4. S5 duplicates S1, reducing signal independence in effort modeling.
5. Single-centroid state representation loses intra-state spatial heterogeneity.
6. Month-averaged transport may smooth away seasonal flow regimes.

---

## 11) Final Conclusion
The pipeline is technically successful and mathematically coherent. It can be used now for policy simulation, relative ranking exploration, and explainable accountability workflows.

For production-grade enforcement or fiscal decisions, the next critical step is calibration:
1. Align scale and units across absorption/emission sources.
2. Tune VT tail behavior to reduce saturation.
3. Reframe claim threshold from fixed absolute 0.5 MT to distribution-aware trigger.

With those calibrations, this framework can become a robust, transparent interstate carbon accountability engine.

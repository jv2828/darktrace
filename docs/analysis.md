# Analytical Engine & Multi-Dimensional Correlation Methodology

DARKTRACE correlates anonymous threat personas across dark web marketplaces by fusing evidence across four independent dimensions: **Cryptographic**, **Infrastructure**, **Stylometric**, and **Behavioural**.

---

## 1. Mathematical Models & Similarity Metrics

### A. Stylometric Analysis (Writeprint Profiling)
To prevent cross-contamination, all post texts are stripped of extracted indicators (PGP fingerprints, crypto addresses, domains, IP addresses, SSL certificates, banners, and non-standard ports) in a masked copy using placeholder tokens (`<PGP>`, `<WALLET>`, etc.) before feature extraction.

Each actor with sufficient text ($\ge 300$ words) or limited text ($100-299$ words) is represented by four similarity components $\in [0, 1]$:

1. **Character $n$-grams ($3 \le n \le 5$)**:
   $$\text{sim}_{\text{char}}(a, b) = \cos(\mathbf{v}_{a}^{\text{char}}, \mathbf{v}_{b}^{\text{char}})$$
   Fitted via sublinear TF-IDF over all actor documents in the current investigation.
2. **Word $n$-grams ($1 \le n \le 2$)**:
   $$\text{sim}_{\text{word}}(a, b) = \cos(\mathbf{v}_{a}^{\text{word}}, \mathbf{v}_{b}^{\text{word}})$$
3. **Function Word Frequencies**:
   Cosine similarity over relative frequencies of a fixed dictionary of 100 closed-class English function words (articles, prepositions, conjunctions, auxiliary verbs):
   $$\text{sim}_{\text{fw}}(a, b) = \cos(\mathbf{f}_{a}, \mathbf{f}_{b})$$
4. **General Feature Vector**:
   $z$-scored numeric features (mean/std sentence length, mean word length, length-controlled TTR on the first 300 words, hapax legomena ratio, punctuation rates per 1,000 characters, uppercase character ratio, all-caps word ratio, lowercase sentence starts, double spaces, digit ratio, words per post):
   $$\text{sim}_{\text{feat}}(a, b) = \frac{1}{1 + \frac{d_E(\mathbf{z}_a, \mathbf{z}_b)}{\sqrt{k}}}$$
   where $k$ is the number of features and $d_E$ is Euclidean distance.

**Overall Raw Stylometric Similarity**:
$$\text{sim}_{\text{style}} = 0.35 \cdot \text{sim}_{\text{char}} + 0.15 \cdot \text{sim}_{\text{word}} + 0.25 \cdot \text{sim}_{\text{fw}} + 0.25 \cdot \text{sim}_{\text{feat}}$$

---

### B. Behavioural Analysis (Diurnal & Activity Rhythms)
Uses strictly UTC timestamps from posted messages ($\ge 10$ posts: sufficient; $5-9$: limited; $< 5$: insufficient).

1. **Hourly Activity (24 bins)**:
   Normalised hourly post distribution circularly smoothed using kernel $[0.25, 0.5, 0.25]$:
   $$\tilde{h}_i = 0.25 \cdot h_{(i-1)\bmod 24} + 0.5 \cdot h_i + 0.25 \cdot h_{(i+1)\bmod 24}$$
   Similarity:
   $$\text{sim}_{\text{hourly}}(a, b) = 1 - D_{\text{JS}}(\tilde{\mathbf{h}}_a \parallel \tilde{\mathbf{h}}_b)$$
   where $D_{\text{JS}}$ is Jensen-Shannon distance with base-2 logarithm.
2. **Daily Activity (7 bins, Monday-first)**:
   Normalised and circularly smoothed daily distribution:
   $$\text{sim}_{\text{daily}}(a, b) = 1 - D_{\text{JS}}(\tilde{\mathbf{d}}_a \parallel \tilde{\mathbf{d}}_b)$$
3. **Posting Frequency Ratio**:
   $$\text{sim}_{\text{freq}}(a, b) = 1 - \min\left(1, \frac{|\ln(r_a / r_b)|}{\ln 10}\right)$$
   where $r$ is posts per active day.

**Overall Raw Behavioural Similarity**:
$$\text{sim}_{\text{behav}} = 0.60 \cdot \text{sim}_{\text{hourly}} + 0.25 \cdot \text{sim}_{\text{daily}} + 0.15 \cdot \text{sim}_{\text{freq}}$$

---

### C. Relative Scoring (Run Baseline & MAD Spread)
Raw text similarities and diurnal distributions across arbitrary English personas naturally skew high (often clustering between $0.40$ and $0.65$). DARKTRACE judges every pair relative to the run's own empirical distribution across all comparable pairs:

$$\text{baseline} = \operatorname{median}(\{\text{sim}_p\})$$
$$\text{spread} = \max\left(1.4826 \cdot \operatorname{MAD}(\{\text{sim}_p\}), 0.02\right)$$
$$z = \frac{\text{sim}_p - \text{baseline}}{\text{spread}}$$

- **Supporting Evidence**: Triggered when $z \ge z_{\text{support}}$ (default $1.50$):
  $$\text{strength} = \operatorname{clamp}\left(\frac{z - z_{\text{support}}}{z_{\text{full}} - z_{\text{support}}}, 0, 1\right) \times \text{data\_factor}$$
  where $\text{data\_factor} = 1.0$ if both actors are sufficient, and $0.70$ if either is limited.
- **Reliability Guard**: If fewer than 6 comparable pairs exist in the run, `baseline_reliable` is flagged as `false` and evidence strength is capped at $0.50$.
- **Contradicting Evidence**: Triggered when $z \le -z_{\text{contra}}$ (default $-1.50$) or when personas sharing a cryptographic/infrastructure indicator exhibit severe temporal divergence ($\text{sim}_{\text{hourly}} \le 0.20$):
  $$\text{strength}_{\text{contra}} = \operatorname{clamp}\left(\frac{-z - z_{\text{contra}}}{2.0}, 0, 1\right) \ge 0.30$$

---

## 2. Multi-Dimensional Scoring Engine

The scoring engine synthesizes supporting and contradicting evidence across all four dimensions.

### Positive-Only vs. Bidirectional Dimensions
- **Positive-Only (Cryptographic, Infrastructure)**: Personas who do not share a wallet or domain are not necessarily different operators (most independent personas share no indicators). Thus, if no matching indicators exist, the dimension score is $0$ and its weight is **excluded from the denominator** so unshared indicators do not penalize the score. If indicators were present and suppressed (e.g. escrow wallets, shared marketplace infrastructure), they are logged and not scored. Multiple matches combine via Noisy-OR:
  $$S = 1 - \prod_{i=1}^m (1 - s_i)$$
- **Bidirectional (Stylometric, Behavioural)**: Evaluated if both personas meet sufficiency or limited criteria. If an actor has insufficient text or timestamps, the dimension is omitted from scoring and flagged in `missing_dimensions`.

### Score Composition & Contradiction Penalty
1. **Pre-Penalty Score**:
   $$\text{score}_{\text{pre}} = \frac{\sum_{d \in \text{counted}} w_d \cdot S_d}{\sum_{d \in \text{counted}} w_d}$$
   Dimension contributions are reported as $\text{contrib}_d = \frac{w_d}{\sum w} \cdot S_d$, strictly summing to $\text{score}_{\text{pre}}$.

2. **Contradiction Penalty**:
   $$\text{score}_{\text{combined}} = \text{score}_{\text{pre}} \cdot \left(1 - \text{penalty\_weight} \cdot \max(\text{strength}_{\text{contra}})\right)$$
   where default $\text{penalty\_weight} = 0.50$.

3. **Coverage & Link Level Calibration**:
   $$\text{coverage} = \frac{\sum_{d \in \text{counted}} w_d}{\sum_{\text{all}} w_d}$$
   - **Strong**: $\text{score}_{\text{combined}} \ge 0.70$
   - **Moderate**: $0.45 \le \text{score}_{\text{combined}} < 0.70$
   - **Weak**: $0.25 \le \text{score}_{\text{combined}} < 0.45$
   - **None**: $< 0.25$

4. **Safety Caps**:
   - A correlation based on only **one single dimension** is capped at `moderate`, unless that dimension is cryptographic with strength $\ge 0.90$.
   - Any pair with a contradiction of strength $\ge 0.60$ is capped at `moderate`.

---

## 3. Threshold Calibrations & Benchmark Performance

### Active Configuration Defaults
- **Dimension Weights**: Cryptographic: $0.35$, Infrastructure: $0.20$, Stylometric: $0.25$, Behavioural: $0.20$.
- **Stylometry**: $z_{\text{support}} = 1.50$, $z_{\text{full}} = 3.50$, sufficient words $\ge 300$, limited $\ge 100$.
- **Behaviour**: $z_{\text{support}} = 1.50$, $z_{\text{full}} = 3.50$, sufficient posts $\ge 10$, limited $\ge 5$.
- **Scoring**: Report threshold $= 0.20$, potential link threshold $= 0.45$, contradiction $z = 1.50$, contradiction penalty $= 0.50$.

### Empirical Ground Truth Evaluation
Evaluated against deterministic ground-truth benchmarks with hidden actor correlations:
- **Alpha Benchmark** (10 actors, 45 pairs):
  - Stylometry ROC AUC: **1.0000**
  - Behaviour ROC AUC: **0.9600**
  - Combined ROC AUC: **1.0000**
  - Hard Negatives: **0.0%** false positive rate at moderate or higher.
- **Beta Benchmark** (30 actors, 435 pairs):
  - Stylometry ROC AUC: **1.0000** (378 evaluated pairs, 57 short-text pairs safely excluded)
  - Behaviour ROC AUC: **0.9730** (378 evaluated pairs, 57 missing-timestamp pairs safely excluded)
  - Combined ROC AUC: **0.9756** (435 pairs evaluated)
  - Hard Negatives: **0.0%** false positive rate at moderate or higher.
  - Decoys (12 pairs): Correctly suppressed ($0.0000$ combined score).
  - Contradictory Crypto (`cipher_echo_a` vs `cipher_echo_b`): Divergent styles ($z = -1.47$) and opposing posting windows ($01:00$ vs $13:00$ UTC) triggered behavioural and stylometric contradiction penalties, reducing the composite score to $0.2078$ (`none` level).

---

## 4. Operational Limitations & Forensic Disclaimers

> [!CAUTION]
> **HEURISTIC EVIDENCE SCORE — NOT A PROBABILITY OF IDENTITY**
> Every correlation score generated by DARKTRACE is an empirical, heuristic measurement of multi-dimensional similarity and common indicator footprint. It is **NOT** a mathematical probability that two personas are operated by the same physical human being.

Key analytical constraints:
1. **Synthetic vs. Real-World Volatility**: Controlled benchmarks provide clean separation; real threat actors deliberately obfuscate language, utilize shared boilerplates, or copy-paste forum templates.
2. **Short Text Volatility**: Submissions with fewer than 300 words are statistically volatile and cannot support high-confidence stylometric conclusions.
3. **Decoy & Reused Infrastructure**: Cryptographic keys can be leaked, shared across market teams, or sold. Stylometric and behavioural divergence flags must be evaluated in tandem with raw indicator evidence.


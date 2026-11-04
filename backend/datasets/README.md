# DARKTRACE Synthetic Intelligence Datasets & Ground Truth

This directory hosts the deterministic benchmark datasets and verified ground-truth correlation labels used for pipeline validation and model evaluation in DARKTRACE.

---

## 1. Safety & Ethical Compliance

All data within this directory is **100% synthetic and fictional**:
- **Marketplaces**: Completely invented names (`Velvet Bazaar`, `Greywharf`, `Tidepool Exchange`, `Lanternroot`, `Cobalt Harbor`, `Whispering Pines`).
- **Post Topics**: Strictly benign marketplace interactions (restocks of fictional precision clockwork gears, encrypted ledger micro-controller development boards, shipping route weather delays, multi-signature escrow releases, public key rotation notices).
- **Prohibited Content**: Contains zero real illicit items, zero exploitation or exploit payloads, zero real personal identities, zero corporate brands, zero leaked databases, and zero production credentials.
- **Network Infrastructure**:
  - IP addresses are exclusively sampled from **RFC 5737** documentation subnets:
    - `192.0.2.0/24` (TEST-NET-1)
    - `198.51.100.0/24` (TEST-NET-2)
    - `203.0.113.0/24` (TEST-NET-3)
  - Domain names strictly terminate in `.example` or `.invalid`.
  - Onion service identifiers follow the convention `fictional[base32].onion`.
- **Cryptographic Artifacts**:
  - PGP keys and cryptocurrency wallet strings are synthetic test mockups generated for normalisation and linking tests; no active real-world private keys or mainnet financial assets are represented.

---

## 2. Dataset Overview

### Alpha Benchmark (`sample/alpha.json` & `ground_truth/alpha_truth.json`)
- **Scale**: 6 Operators, 10 Personas across 4 Marketplaces, 180 Posts.
- **Design Focus**: Baseline correlation validation testing:
  - **Strong Positive (`strong_positive`)**: 3 personas (`iron_weaver`, `iron_artisan`, `iron_craft`) sharing a PGP key, a Bitcoin wallet, stylistic quirks, and daylight UTC active hours.
  - **Stylistic / Behavioural Only (`partial_positive_style_behaviour`)**: 2 personas sharing writing syntax (all-lowercase, double spacing) and night-owl diurnal patterns, but with zero shared crypto keys.
  - **Infrastructure Only (`partial_positive_infra`)**: 2 personas sharing backend hosting, IP (`198.51.100.42`), and TLS certificate, but operating at completely different hours and writing styles.
  - **Hard Negatives (`hard_negative_behaviour`)**: 2 distinct operators (`drift_courier` and `current_runner`) operating in the same afternoon UTC window without any indicator overlap.
  - **Control (`control`)**: Isolated single-persona vendor.

### Beta Benchmark (`sample/beta.json` & `ground_truth/beta_truth.json`)
- **Scale**: 14 Operators, 30 Personas across 6 Marketplaces, 714 Posts.
- **Design Focus**: Advanced real-world edge cases:
  - **Contradictory Cryptographic Evidence (`contradictory_crypto`)**: Two personas sharing a PGP fingerprint, but with diametrically opposed writing styles and non-overlapping active windows (representing compromised or copy-pasted keys).
  - **Common Decoy Indicators (`common_indicator_decoy`)**: Official platform escrow wallets and support keys quoted across unrelated vendor posts that must not falsely cluster identities.
  - **Short-Text Personas (`short_text`)**: Brief 5-15 word posts with minimal vocabulary samples.
  - **Missing Timestamps (`missing_timestamps`)**: Posts with null timestamps testing non-temporal correlation capabilities.
  - **Partial Overlaps**: Personas sharing single payment channels among multiple distinct options.
  - **Near-Duplicate Usernames Across Platforms**: Identical usernames (`shadow_broker`) belonging to different operators on separate marketplaces.

---

## 3. Ground Truth Rules & Separation

- **Evaluation Only**: The ground-truth files (`alpha_truth.json`, `beta_truth.json`) are strictly for automated test suites, scoring algorithms, and offline evaluation harnesses.
- **No Ground Truth Leakage**: Production application code under `backend/app/` **never** imports, reads, or exposes files from `datasets/ground_truth/`.
- **Sample File Hygiene**: The sample JSON files ingested into the platform contain only raw observable darknet posts; they carry no operator IDs, group tags, or synthetic metadata.

---

## 4. Honest Methodology Limitations

- **Synthetic Regularity**: While the generator introduces diurnal jitter, stylistic variance, punctuation habits, and misspellings, synthetic rule-based text is inherently more structured than authentic darknet communications.
- **Disambiguation Simplicity**: In real threat-intelligence workflows, human actors consciously alter terminology, employ obfuscation, and rotate infrastructure irregularly. Benchmark accuracy scores achieved against this synthetic corpus represent an upper-bound baseline rather than guaranteed production field efficacy.

---

## 5. Regeneration

To regenerate the benchmark files deterministically:
```bash
python tools/generate_sample_data.py
```
Because the generator relies strictly on seeded random state and sorted mappings, running this command produces bit-for-bit identical outputs across environments.


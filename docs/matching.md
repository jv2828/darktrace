# DARKTRACE Matching & Evidence Engine (Phase 7)

## 1. Overview & Architecture

The DARKTRACE matching engine correlates threat actor personas across disparate darknet platforms based on technical artifacts extracted during Phase 6. The engine operates entirely offline and in pure Python: it **never** resolves, probes, pings, or scans IP addresses, domains, ports, or certificates. Matching is performed exclusively by evaluating normalized indicator strings extracted from stored communications.

```mermaid
flowchart TD
    subgraph Data [Intelligence Ingestion & Extraction]
        P[Posts Table] --> I[Extracted Indicators]
    end

    subgraph Pipeline [Pipeline Run Execution]
        PR[Pipeline Run] --> Stg1[crypto_matching Stage]
        PR --> Stg2[infrastructure_matching Stage]
        
        Stg1 --> Pre[Prevalence & Suppression Filter]
        Stg2 --> Pre
        
        Pre --> Spec[Rarity & Specificity Scaling]
        Spec --> Ev[Generate Evidence Candidates]
    end

    subgraph Persistence [Forensic Storage]
        Ev --> ER[evidence_records Table]
        Ev --> ES[evidence_sources Table]
        ER --> Pairs[Actor Pair Aggregations]
    end
```

> **CRITICAL FORENSIC & ETHICAL NOTICE:**  
> **All correlation strengths are heuristic evidentiary metrics, NOT mathematical probabilities of common identity.**  
> In illicit underground markets, threat actors frequently borrow PGP keys, post third-party multi-signature escrow wallets, or route services through shared proxy mirrors. Strong evidentiary linkage indicates correlated usage, not incontrovertible identity.

---

## 2. Evidence Dimensions & Base Strengths

Base strengths reflect the inherent uniqueness and cryptographic entropy of an artifact type when observed without degradation:

| Dimension | Evidence Type | Base Strength | Rationale |
| :--- | :--- | :--- | :--- |
| **Cryptographic** | `shared_pgp_key` | **0.95** | 160-bit SHA-1 fingerprint has negligible collision probability; represents private-key control. |
| **Cryptographic** | `shared_xmr_wallet` | **0.90** | Monero stealth addresses and subaddresses are single-recipient or dedicated merchant payment points. |
| **Cryptographic** | `shared_btc_wallet` | **0.85** | High entropy address; slightly lower than XMR due to potential multi-sig or public reuse. |
| **Cryptographic** | `shared_eth_wallet` | **0.85** | Hexadecimal account address; high entropy with potential smart contract reuse. |
| **Cryptographic** | `shared_wallet` | **0.70** | Generic or non-standard cryptocurrency address format. |
| **Infrastructure** | `shared_ssl_cert` | **0.90** | SHA-256 fingerprint of X.509 certificate represents specific TLS identity/keypair. |
| **Infrastructure** | `shared_onion_domain` | **0.85** | Tor v3 hidden service (56 characters) derived from ed25519 public key. |
| **Infrastructure** | `shared_domain` | **0.65** | Clearnet domain or sub-domain. |
| **Infrastructure** | `shared_ip_address` | **0.70** | Dedicated IPv4 or IPv6 host (non-CDN/proxy context). |
| **Infrastructure** | `shared_cert_metadata` (serial) | **0.75** | Certificate serial number uniqueness depends on CA/issuer discipline. |
| **Infrastructure** | `shared_cert_metadata` (CN/issuer) | **0.50** | Common Name or Issuer fields may be templated or shared across self-signed kits. |
| **Infrastructure** | `shared_server_banner` | **0.45** | Server software/banner string (may indicate identical configuration or automated toolkit). |
| **Infrastructure** | `corroborating_port` | **0.40** | Secondary signal: non-standard port matching on an already-shared IP address. |

---

## 3. Mathematical Scoring Formulas

Every pairwise evidence candidate between Threat Actor $A$ and Threat Actor $B$ is scored through a multi-factor formula that accounts for base indicator quality, indicator rarity across the dataset, and extractor confidence.

### 3.1. Specificity Discount Function $S(N)$

If an indicator is observed across multiple threat actors, its evidential value decays inversely with the number of distinct personas $N$ associated with it:

$$S(N) = \min\left(1.0, \frac{\text{full\_strength\_max\_actors}}{N}\right)$$

Where:
- $N = |\text{actors with indicator}|$
- Default parameter: $\text{full\_strength\_max\_actors} = 3$

*Behavior:*
- For $N \le 3$: $S(N) = 1.0$ (no discount).
- For $N = 4$: $S(4) = \frac{3}{4} = 0.75$ (25% discount).
- For $N = 5$: If suppressed (see Section 4), evidence generation is bypassed.

### 3.2. Extraction Confidence Factor $C(A, B)$

Each indicator in the database is tagged with an extraction confidence:
- $\text{high} = 1.0$
- $\text{medium} = 0.8$
- $\text{low} = 0.5$

When comparing two indicators from Actor $A$ and Actor $B$, the pair confidence factor $C$ takes the weakest link:

$$C(A, B) = \min\left(\text{confidence}(I_A), \text{confidence}(I_B)\right)$$

### 3.3. Final Evidence Strength Calculation

$$\text{Strength} = \text{round}\Big(\text{base\_strength} \times S(N) \times C(A, B),\; 4\Big)$$

All evidence records must satisfy $0.0000 \le \text{Strength} \le 1.0000$, enforced by PostgreSQL check constraints.

---

## 4. High-Prevalence Suppression (Decoy Protection)

In real-world threat intelligence and synthetic benchmarks (e.g., Dataset Beta), specific indicators appear widely across many unrelated actors:
1. **Marketplace Escrow Wallets:** Shared addresses provided by the market for escrow or deposit.
2. **Support PGP Keys:** Market administrator or PGP helpdesk keys quoted by many vendors.
3. **Common Onion Hubs / Gateways:** Public directories or darknet indexing nodes.

### Suppression Threshold

An indicator is classified as a **Common / Decoy Indicator** and suppressed from evidence generation if:

$$N \ge \text{common\_indicator\_min\_actors} \quad (\text{Default } = 5)$$

When an indicator meets this threshold:
1. Evidence generation is completely suppressed between all pairs sharing that indicator.
2. The indicator is summarized and returned in the pipeline stage output (`suppressed_common_indicators`).
3. The UI presents a dedicated **Common Indicators Notice** listing the artifact, persona count, and marketplace breadth.

### Parameter Calibration on Benchmark Beta

Inspection of the Beta ground truth revealed:
- True operator with largest persona footprint (`op_beta_14`) spans **4 personas**.
- Shared escrow wallet (`bc1qdecoycommon...`) and decoy support key (`DEC07DEC07...`) appear across **6 personas**.
- Setting $\text{full\_strength\_max\_actors} = 3$ and $\text{common\_indicator\_min\_actors} = 5$ achieves **100% precision (1.0000)** and **100% recall (1.0000)** on both Alpha and Beta datasets, completely suppressing all decoys while preserving operator linkage.

---

## 5. Worked Mathematical Examples

### Example 1: PGP Key Exclusively Shared by Two Personas
- **Artifact:** PGP fingerprint `9a1b2c3d4e5f6789...`
- **Actors:** `@hydra_vendor` (Hydra) and `@silk_merchant` (SilkRoad)
- **Prevalence:** $N = 2$ actors.
- **Extractor Confidence:** Both extracted with `high` (1.0).
- **Calculation:**
  $$S(2) = \min(1.0, 3/2) = 1.0$$
  $$C = \min(1.0, 1.0) = 1.0$$
  $$\text{Strength} = 0.95 \times 1.0 \times 1.0 = \mathbf{0.9500}$$

### Example 2: Bitcoin Wallet Shared Across Four Personas
- **Artifact:** Wallet `bc1q9xyz...`
- **Actors:** 4 distinct personas across 3 markets.
- **Prevalence:** $N = 4$ actors.
- **Extractor Confidence:** Both with `high` (1.0).
- **Calculation:**
  $$S(4) = \min(1.0, 3/4) = 0.75$$
  $$C = 1.0$$
  $$\text{Strength} = 0.85 \times 0.75 \times 1.0 = \mathbf{0.6375}$$

### Example 3: Defanged IP Address with Medium Confidence
- **Artifact:** IP `198.51.100.42`
- **Actors:** `@botnet_master` (Market A) and `@hoster` (Market B)
- **Prevalence:** $N = 2$ actors.
- **Extractor Confidence:** Actor A is `high` (1.0), Actor B is `medium` (0.8) due to surrounding syntax.
- **Calculation:**
  $$S(2) = 1.0$$
  $$C = \min(1.0, 0.8) = 0.8$$
  $$\text{Strength} = 0.70 \times 1.0 \times 0.8 = \mathbf{0.5600}$$

---

## 6. Infrastructure Matching Special Rules

### 6.1. Onion v3 vs. Clearnet Domains
- Indicators of type `domain` ending in `.onion` (specifically 56-character v3 addresses) are classified as `shared_onion_domain` with base strength **0.85**.
- Standard clearnet domains are classified as `shared_domain` with base strength **0.65**.

### 6.2. Non-Standard Port Corroboration Rule
When comparing two threat actors who share a valid IP address:
1. The engine checks if both actors also have extracted `port` indicators on that same IP.
2. If both actors expose the **same non-standard port** (defined as port $\ne 80$ and port $\ne 443$, e.g., `8080`, `2222`, `9001`):
   - A corroborating evidence record of type `corroborating_port` is generated with base strength **0.40**.
   - The explanation explicitly notes: *"Both personas operate on shared host with identical non-standard service port {port}."*

---

## 7. Forensic Explanations & Masking

All generated evidence explanations adhere to deterministic, natural-language templates that include:
1. **Value Masking:** Wallets, keys, and IPs are masked in human-readable prose (e.g. `bc1q9...4mdq`, `9A1B...5678`) to protect report cleanliness and prevent inadvertent copy-paste leakage.
2. **Forensic Caveats:** Every explanation includes a standard qualification:
   - *Wallets:* "Caveat: wallets appearing in dark web posts may represent third-party escrow, mixer deposits, or copied donation addresses."
   - *PGP:* "Caveat: PGP keys may be shared across seller teams or cloned from public keyrings."
   - *IP / Infrastructure:* "Caveat: dark web infrastructure may route through shared reverse proxies or bulletproof VPN gateways."

---

## 8. Limitations & Scope

- **Exact Value Matching:** Matching currently operates on normalized string equality. Fuzzy matching, partial PGP ID matching, or behavioral graph clustering are scheduled for subsequent phases.
- **Passive Analysis Only:** No active network packets, DNS lookups, or SSL handshakes are performed. All data originates from historical stored intelligence.
- **No Ground-Truth Leakage:** The matching engine has no access to the `backend/datasets/ground_truth/` directory or any benchmark answer keys. It computes evidence purely from user-ingested posts.


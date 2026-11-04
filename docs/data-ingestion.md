# DARKTRACE Data Ingestion & Synthetic Benchmark Reference

Phase 5 introduces comprehensive dark web threat-intelligence ingestion pipelines, normalisation, deduplication, and synthetic benchmark datasets grounded in deterministic evaluation truth.

---

## 1. Supported Ingestion Channels

DARKTRACE provides three data collection channels within an investigation workspace:
1. **Sample Benchmarks (`POST /api/v1/investigations/{id}/datasets/samples/{key}`)**: Idempotent loader linking synthetic corpora (`alpha`, `beta`) to cases.
2. **Manual Record Entry (`POST /api/v1/investigations/{id}/ingest/manual/preview` & `commit`)**: Single post entry for operational intelligence feeds with immediate validation and duplicate checking.
3. **Batch File Upload (`POST /api/v1/investigations/{id}/ingest/file/preview` & `commit`)**: High-throughput multipart upload supporting CSV and JSON datasets up to 5 MB (5,000 rows).

---

## 2. Ingestion File Formats

### CSV Format (`.csv`)
- **Encoding**: UTF-8 (with or without Byte Order Mark `\ufeff`).
- **Headers**: Case-insensitive, whitespace-trimmed.
- **Required Columns**: `marketplace`, `username`, `content`.
- **Optional Columns**: `timestamp`, `source_reference`, `pgp_fingerprint`, `wallet`, `domain`, `ip_address`, `ssl_cert_fingerprint`, `server_banner`, `port`.
- **Multiline Cells**: Supports quoted multiline RFC 4180 CSV entries.

#### Example CSV:
```csv
marketplace,username,content,timestamp,pgp_fingerprint,wallet,port
Velvet Bazaar,iron_weaver,"Restock batch #402 of precision clockwork escapement gears. Escrow release upon physical inspection.",2026-02-14T15:30:00Z,E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A,bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f,443
Greywharf,dusk_merchant,"Logistics dispatch clears customs route by midweek. Stay safe.",2026-02-15 10:00:00,,,8080
```

### JSON Format (`.json`)
Accepts either:
- A top-level array of post objects: `[{...}, {...}]`
- A container object with a `"posts"` list: `{"posts": [{...}]}`

#### Example JSON:
```json
[
  {
    "marketplace": "Velvet Bazaar",
    "username": "iron_weaver",
    "timestamp": "2026-02-14T15:30:00Z",
    "content": "Restock batch #402 of precision clockwork escapement gears. Escrow release upon physical inspection.",
    "source_reference": "thread_8492",
    "structured_indicators": {
      "pgp_fingerprint": "E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A",
      "wallet": "bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
      "port": 443
    }
  }
]
```

---

## 3. Validation Rules & Field Constraints

| Field | Requirement | Validation Rule | Invalid Consequence |
| :--- | :--- | :--- | :--- |
| **`marketplace`** | Mandatory | 2 to 100 characters, trimmed. | Fatal `ERROR` |
| **`username`** | Mandatory | 2 to 64 characters; no Unicode control characters. | Fatal `ERROR` |
| **`content`** | Mandatory | 1 to 20,000 characters; not whitespace-only; no NUL bytes (`\x00`). | Fatal `ERROR` |
| **`timestamp`** | Optional | ISO 8601 or `YYYY-MM-DD HH:MM[:SS]`. | Unparseable = `ERROR`. Naive = `WARNING` (assumes UTC). Out of range (&lt;2000 or &gt;1d future) = `WARNING`. |
| **`ip_address`** | Optional | Valid IPv4/IPv6 address via standard IP parsing. | Invalid = `WARNING` (stored in `raw_metadata.structured_indicators_unparsed`). |
| **`port`** | Optional | Integer between 1 and 65,535. | Invalid = `WARNING` (stored in `unparsed`). |
| **`pgp_fingerprint`** | Optional | 40 or 64 hexadecimal characters (spaces/colons/`0x` stripped). | Invalid = `WARNING` (stored in `unparsed`). |
| **`ssl_cert_fingerprint`**| Optional | 64 hexadecimal characters (SHA-256). | Invalid = `WARNING` (stored in `unparsed`). |

---

## 4. Deduplication & Row Statuses

Each post is evaluated into one of four deterministic statuses:
- **`valid`**: Conforms to all schema rules with zero validation warnings or errors, and unique hash.
- **`valid_with_warnings`**: Non-fatal anomalies (e.g. naive timestamp assumed UTC, non-standard IP format moved to unparsed indicators). Imported with clean metadata.
- **`duplicate`**: Matches an existing post by SHA-256 dedupe hash:
  $$\text{sha256}(\text{marketplace}_{\text{norm}} \parallel \text{username}_{\text{norm}} \parallel \text{timestamp}_{\text{UTC}} \parallel \text{content}_{\text{collapsed}})$$
  Identified across the current batch OR already present in any dataset attached to the investigation.
- **`invalid`**: Fails mandatory validation constraints (missing fields, bad bounds, NUL bytes).

### Batch Error Strategies
- **`skip_invalid` (Default)**: Imports all valid and warned rows; skips duplicates and invalid rows with detailed reporting.
- **`reject_all`**: Atomic rollback; aborts upload with HTTP 422 if any row in the file is invalid.

---

## 5. Synthetic Data Safety Rules

All benchmark samples (`alpha.json`, `beta.json`) adhere strictly to ethical testing rules:
1. **Fictional Contexts**: Only benign fictional marketplace trading (clockwork gears, hardware breadboards, fountain pens, logistics weather updates).
2. **Strict IP Range Isolation**: Exclusively samples documentation subnets defined in RFC 5737:
   - `192.0.2.0/24` (TEST-NET-1)
   - `198.51.100.0/24` (TEST-NET-2)
   - `203.0.113.0/24` (TEST-NET-3)
3. **Domain Suffixes**: Strictly limited to `.example`, `.invalid`, and `fictional*.onion`.
4. **No Identity Leakage**: Sample JSON files contain no operator identifiers or ground-truth evaluation groups.

---

## 6. Deterministic Regeneration

To regenerate the benchmark sample files and verified ground-truth pairs:
```bash
python tools/generate_sample_data.py
```
Outputs are bit-for-bit deterministic across platforms using seeded random generators and sorted data structures.


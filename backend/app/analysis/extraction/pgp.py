"""PGP fingerprint extraction and normalisation."""

import re
from typing import List
from app.analysis.extraction.models import ExtractedIndicator

# Label regex to inspect up to 40 characters before a candidate
PGP_LABEL_PATTERN = re.compile(
    r'(?i)\b(pgp|gpg|fingerprint|fpr|public\s+key|key\s+id|key)\b'
)
CERT_CONFLICT_PATTERN = re.compile(
    r'(?i)\b(cert|certificate|ssl|tls|sha256|sha-256|thumbprint)\b'
)

# 1. Spaced groups of 4 (40-hex: 10 groups; 64-hex: 16 groups)
PGP_SPACED_40 = re.compile(
    r'(?i)(?<![0-9a-fA-F])(?:0x)?([0-9a-f]{4}(?:[\s\u00a0]{1,2}[0-9a-f]{4}){9})(?![0-9a-fA-F])'
)
PGP_SPACED_64 = re.compile(
    r'(?i)(?<![0-9a-fA-F])(?:0x)?([0-9a-f]{4}(?:[\s\u00a0]{1,2}[0-9a-f]{4}){15})(?![0-9a-fA-F])'
)

# 2. Colon-separated (40-hex: 20 pairs or 10 quads; 64-hex: 32 pairs or 16 quads)
PGP_COLON_40 = re.compile(
    r'(?i)(?<![0-9a-fA-F])(?:0x)?([0-9a-f]{2}(?::[0-9a-f]{2}){19}|[0-9a-f]{4}(?::[0-9a-f]{4}){9})(?![0-9a-fA-F])'
)
PGP_COLON_64 = re.compile(
    r'(?i)(?<![0-9a-fA-F])(?:0x)?([0-9a-f]{2}(?::[0-9a-f]{2}){31}|[0-9a-f]{4}(?::[0-9a-f]{4}){15})(?![0-9a-fA-F])'
)

# 3. Continuous hex runs (40 or 64 hex)
PGP_CONTINUOUS = re.compile(
    r'(?i)(?<![0-9a-fA-F])(?:0x)?([0-9a-f]{40}|[0-9a-f]{64})(?![0-9a-fA-F])'
)


def normalise_pgp(raw_value: str) -> str:
    """Normalise PGP fingerprint to uppercase hex with all separators and 0x prefix stripped."""
    cleaned = raw_value.strip()
    if cleaned.lower().startswith("0x"):
        cleaned = cleaned[2:]
    for ch in (" ", "\u00a0", ":", "-", "\t", "\n"):
        cleaned = cleaned.replace(ch, "")
    return cleaned.upper()


def extract_pgp_fingerprints(content: str) -> List[ExtractedIndicator]:
    """Extract PGP fingerprints from text according to contextual and format rules."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    def add_match(m: re.Match, is_continuous: bool = False):
        start = m.start()
        end = m.end()
        raw = content[start:end]
        normalised = normalise_pgp(raw)

        if len(normalised) not in (40, 64):
            return

        # Disambiguate with Certificate Fingerprints:
        nearby_context = content[max(0, start - 40) : min(len(content), end + 40)]
        has_cert_label = bool(CERT_CONFLICT_PATTERN.search(nearby_context))
        has_pgp_explicit = bool(re.search(r'(?i)\b(pgp|gpg)\b', nearby_context))

        if has_cert_label and not has_pgp_explicit:
            # Belongs to Certificate Fingerprints, not PGP
            return

        # Check context if continuous bare run
        if is_continuous:
            has_0x = raw.lower().startswith("0x")
            has_wallet_label = bool(re.search(r'(?i)\b(eth|ether|ethereum|wallet|address|send|pay|payment|escrow|deposit)\b', nearby_context))

            if has_0x:
                if has_wallet_label and not has_pgp_explicit:
                    return
            else:
                preceding_context = content[max(0, start - 40) : start]
                if not PGP_LABEL_PATTERN.search(preceding_context):
                    # Bare unlabeled continuous hex run without 0x is NOT accepted as PGP
                    return

        span_tuple = (start, end)
        if span_tuple not in seen_spans:
            seen_spans.add(span_tuple)
            indicators.append(
                ExtractedIndicator(
                    indicator_type="pgp_fingerprint",
                    raw_value=raw,
                    normalised_value=normalised,
                    span_start=start,
                    span_end=end,
                    extraction_method="regex",
                    is_valid_format=True,
                    confidence="high",
                    details={
                        "length": len(normalised),
                        "has_separators": not is_continuous,
                    },
                )
            )

    # 1. Spaced fingerprints (high confidence even without label)
    for m in PGP_SPACED_40.finditer(content):
        add_match(m, is_continuous=False)
    for m in PGP_SPACED_64.finditer(content):
        add_match(m, is_continuous=False)

    # 2. Colon-separated fingerprints
    for m in PGP_COLON_40.finditer(content):
        add_match(m, is_continuous=False)
    for m in PGP_COLON_64.finditer(content):
        add_match(m, is_continuous=False)

    # 3. Continuous runs (require label in preceding 40 characters)
    for m in PGP_CONTINUOUS.finditer(content):
        # If this span overlaps an already matched spaced/colon pattern, skip
        if any(max(m.start(), s) < min(m.end(), e) for s, e in seen_spans):
            continue
        add_match(m, is_continuous=True)

    return indicators

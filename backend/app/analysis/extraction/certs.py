"""SSL/TLS certificate fingerprint and metadata extraction."""

import re
from typing import List
from app.analysis.extraction.models import ExtractedIndicator

# Nearby certificate labels (checked within 40 characters before or after candidate)
CERT_LABEL_PATTERN = re.compile(
    r'(?i)\b(cert|certificate|ssl|tls|sha256|sha-256|thumbprint)\b'
)
SHA1_LABEL_PATTERN = re.compile(r'(?i)\b(sha1|sha-1)\b')

# 1. Colon-separated certificate fingerprints (32 pairs for 64-hex SHA-256, 20 pairs for 40-hex SHA-1)
CERT_COLON_PATTERN = re.compile(
    r'(?i)(?<![0-9a-fA-F])([0-9a-f]{2}(?::[0-9a-f]{2}){31}|[0-9a-f]{2}(?::[0-9a-f]{2}){19})(?![0-9a-fA-F])'
)

# 2. Continuous hex candidate runs
CERT_CONTINUOUS_PATTERN = re.compile(
    r'(?i)(?<![0-9a-fA-F])([0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-fA-F])'
)

# Certificate Metadata patterns
# CN=... or Subject: ...
META_SUBJECT_CN = re.compile(
    r'(?i)\b(?:Subject:\s*(?:CN\s*=\s*)?|CN\s*=\s*)([^\r\n,;/]+)'
)
# Issuer: ...
META_ISSUER = re.compile(
    r'(?i)\bIssuer:\s*([^\r\n,;/]+)'
)
# Serial: ... or serial number: ...
META_SERIAL = re.compile(
    r'(?i)\b(?:Serial:\s*|serial\s+number:\s*)([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2})+|[0-9a-fA-F]{8,64})\b'
)


def normalise_cert_fingerprint(raw: str) -> str:
    """Normalise certificate fingerprint to uppercase hex without colons or spaces."""
    cleaned = raw.strip()
    for ch in (":", " ", "\u00a0", "-"):
        cleaned = cleaned.replace(ch, "")
    return cleaned.upper()


def extract_cert_fingerprints(content: str) -> List[ExtractedIndicator]:
    """Extract SSL/TLS certificate fingerprints requiring nearby context labels."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    def check_nearby_label(start: int, end: int, is_40_hex: bool) -> bool:
        pre = content[max(0, start - 40) : start]
        post = content[end : min(len(content), end + 40)]
        context = f"{pre} {post}"

        if CERT_LABEL_PATTERN.search(context):
            return True
        if is_40_hex and SHA1_LABEL_PATTERN.search(context):
            return True
        return False

    # 1. Colon-separated (always high confidence if nearby cert label or thumbprint context, or colon syntax)
    for m in CERT_COLON_PATTERN.finditer(content):
        start = m.start()
        end = m.end()
        raw = content[start:end]
        normalised = normalise_cert_fingerprint(raw)
        is_40 = len(normalised) == 40

        # If 40 hex colon-separated, verify it has a cert/sha1 label to avoid ambiguity with PGP
        if is_40 and not check_nearby_label(start, end, is_40_hex=True):
            continue

        seen_spans.add((start, end))
        indicators.append(
            ExtractedIndicator(
                indicator_type="ssl_cert_fingerprint",
                raw_value=raw,
                normalised_value=normalised,
                span_start=start,
                span_end=end,
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"algorithm": "sha256" if len(normalised) == 64 else "sha1"},
            )
        )

    # 2. Continuous hex runs
    for m in CERT_CONTINUOUS_PATTERN.finditer(content):
        start = m.start()
        end = m.end()
        if (start, end) in seen_spans:
            continue

        raw = content[start:end]
        normalised = normalise_cert_fingerprint(raw)
        is_40 = len(normalised) == 40

        # Continuous runs MUST have nearby cert label; bare unlabeled 64-hex is ambiguous and skipped
        if not check_nearby_label(start, end, is_40_hex=is_40):
            continue

        seen_spans.add((start, end))
        indicators.append(
            ExtractedIndicator(
                indicator_type="ssl_cert_fingerprint",
                raw_value=raw,
                normalised_value=normalised,
                span_start=start,
                span_end=end,
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"algorithm": "sha256" if len(normalised) == 64 else "sha1"},
            )
        )

    return indicators


def extract_cert_metadata(content: str) -> List[ExtractedIndicator]:
    """Extract labelled certificate metadata fields (subject_cn, issuer, serial)."""
    indicators: List[ExtractedIndicator] = []

    # Subject CN
    for m in META_SUBJECT_CN.finditer(content):
        raw_val = m.group(1).strip()
        if raw_val.lower().startswith("cn="):
            raw_val = raw_val[3:].strip()
        if not raw_val or len(raw_val) < 2:
            continue
        norm_val = f"subject_cn:{raw_val.lower()}"
        indicators.append(
            ExtractedIndicator(
                indicator_type="cert_metadata",
                raw_value=m.group(0),
                normalised_value=norm_val,
                span_start=m.start(),
                span_end=m.end(),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"field": "subject_cn", "value": raw_val.lower()},
            )
        )

    # Issuer
    for m in META_ISSUER.finditer(content):
        raw_val = m.group(1).strip()
        if not raw_val or len(raw_val) < 2:
            continue
        norm_val = f"issuer:{raw_val.lower()}"
        indicators.append(
            ExtractedIndicator(
                indicator_type="cert_metadata",
                raw_value=m.group(0),
                normalised_value=norm_val,
                span_start=m.start(),
                span_end=m.end(),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"field": "issuer", "value": raw_val.lower()},
            )
        )

    # Serial
    for m in META_SERIAL.finditer(content):
        raw_val = m.group(1).strip()
        cleaned_hex = raw_val.replace(":", "").replace(" ", "").upper()
        if not cleaned_hex or len(cleaned_hex) < 4:
            continue
        norm_val = f"serial:{cleaned_hex}"
        indicators.append(
            ExtractedIndicator(
                indicator_type="cert_metadata",
                raw_value=m.group(0),
                normalised_value=norm_val,
                span_start=m.start(),
                span_end=m.end(),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"field": "serial", "value": cleaned_hex},
            )
        )

    return indicators

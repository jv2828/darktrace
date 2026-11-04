"""Text preparation and indicator masking for stylometric analysis."""

import re
from typing import Any, Dict, List, Optional, Tuple


INDICATOR_PLACEHOLDER_MAP = {
    "pgp_fingerprint": "<PGP>",
    "wallet_btc": "<WALLET>",
    "wallet_eth": "<WALLET>",
    "wallet_xmr": "<WALLET>",
    "wallet_other": "<WALLET>",
    "domain": "<DOMAIN>",
    "onion_domain": "<DOMAIN>",
    "ip_address": "<IP>",
    "ssl_cert_fingerprint": "<CERT>",
    "cert_serial": "<CERT>",
    "cert_subject_cn": "<CERT>",
    "cert_issuer": "<CERT>",
    "server_banner": "<BANNER>",
    "port": "<PORT>",
}


def mask_post_content(content: str, indicators: List[Dict[str, Any]]) -> str:
    """Return a COPY of content with extracted indicator spans replaced with placeholders.
    
    Leaves stored content untouched. Handles overlapping spans by keeping the outermost/first.
    """
    if not indicators or not content:
        return content

    # Filter indicators with valid integer span offsets
    valid_spans: List[Tuple[int, int, str]] = []
    for ind in indicators:
        start = ind.get("span_start")
        end = ind.get("span_end")
        itype = ind.get("indicator_type", "")
        if (
            isinstance(start, int)
            and isinstance(end, int)
            and 0 <= start < end <= len(content)
        ):
            placeholder = INDICATOR_PLACEHOLDER_MAP.get(itype, "<INDICATOR>")
            valid_spans.append((start, end, placeholder))

    if not valid_spans:
        return content

    # Sort descending by start offset, and by length descending for ties
    valid_spans.sort(key=lambda s: (s[0], -(s[1] - s[0])), reverse=True)

    # Discard overlapping spans
    filtered_spans: List[Tuple[int, int, str]] = []
    last_start = len(content) + 1
    for start, end, placeholder in valid_spans:
        if end <= last_start:
            filtered_spans.append((start, end, placeholder))
            last_start = start

    # Reconstruct text
    result = list(content)
    for start, end, placeholder in filtered_spans:
        result[start:end] = list(placeholder)

    return "".join(result)


def tokenize_words(text: str) -> List[str]:
    """Tokenize words matching [A-Za-z0-9']+ runs."""
    return re.findall(r"[A-Za-z0-9']+", text)


def tokenize_sentences(text: str) -> List[str]:
    """Tokenize sentences splitting on [.!?] and newlines."""
    raw_sentences = re.split(r"[.!?\n]+", text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences


def get_text_sufficiency(
    total_words: int,
    min_sufficient: int = 300,
    min_limited: int = 100,
) -> str:
    """Return 'sufficient' (>= min_sufficient), 'limited' (min_limited..min_sufficient-1), or 'insufficient' (< min_limited)."""
    if total_words >= min_sufficient:
        return "sufficient"
    if total_words >= min_limited:
        return "limited"
    return "insufficient"


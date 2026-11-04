"""Span collision resolution and deduplication logic."""

from typing import Any, Dict, List, Tuple
from app.analysis.extraction.models import ExtractedIndicator

# Lower number = higher precedence
PRIORITY_MAP: Dict[str, int] = {
    "ssl_cert_fingerprint": 1,
    "pgp_fingerprint": 1,
    "cert_metadata": 1,
    "wallet_btc": 2,
    "wallet_eth": 2,
    "wallet_xmr": 2,
    "wallet_other": 2,
    "domain": 3,
    "ip_address": 4,
    "port": 5,
    "server_banner": 6,
}


def get_priority(indicator_type: str) -> int:
    return PRIORITY_MAP.get(indicator_type, 10)


def spans_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Return True if two half-open spans [s1, e1) and [s2, e2) intersect."""
    return max(s1, s2) < min(e1, e2)


def resolve_overlaps(
    candidates: List[ExtractedIndicator],
    debug: bool = False,
) -> Tuple[List[ExtractedIndicator], List[Dict[str, Any]]]:
    """Resolve span overlaps among extracted indicators by priority, length, and position.

    Returns:
        (resolved_indicators, dropped_debug_records)
    """
    # Separate indicators without spans (e.g. structured fields) from regex indicators with spans
    spanless = [c for c in candidates if c.span_start is None or c.span_end is None]
    with_spans = [c for c in candidates if c.span_start is not None and c.span_end is not None]

    # Sort with_spans: higher priority first, then longer length first, then earlier start
    with_spans.sort(
        key=lambda c: (
            get_priority(c.indicator_type),
            -(c.span_end - c.span_start),  # Longer length first
            c.span_start,
        )
    )

    accepted: List[ExtractedIndicator] = []
    dropped_records: List[Dict[str, Any]] = []

    for candidate in with_spans:
        c_start = candidate.span_start
        c_end = candidate.span_end
        assert c_start is not None and c_end is not None

        # Check collision with already accepted indicators
        conflict = None
        for acc in accepted:
            assert acc.span_start is not None and acc.span_end is not None
            if spans_overlap(c_start, c_end, acc.span_start, acc.span_end):
                conflict = acc
                break

        if conflict is not None:
            if debug:
                dropped_records.append({
                    "dropped": candidate.to_dict(),
                    "conflicted_with": conflict.to_dict(),
                    "reason": f"Overlaps with higher-priority {conflict.indicator_type}",
                })
        else:
            accepted.append(candidate)

    # Sort accepted regex indicators back into text order
    accepted.sort(key=lambda c: (c.span_start if c.span_start is not None else 0, c.indicator_type))

    return accepted + spanless, dropped_records


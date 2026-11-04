"""Core orchestrator for threat indicator extraction."""

from typing import Any, Dict, List, Optional
from app.analysis.extraction.banners import extract_server_banners
from app.analysis.extraction.certs import extract_cert_fingerprints, extract_cert_metadata
from app.analysis.extraction.models import ExtractedIndicator, ExtractionResult
from app.analysis.extraction.network import (
    extract_domains_and_onions,
    extract_ips,
    extract_ports,
)
from app.analysis.extraction.pgp import extract_pgp_fingerprints
from app.analysis.extraction.spans import resolve_overlaps
from app.analysis.extraction.structured import extract_structured_indicators
from app.analysis.extraction.text_stats import compute_text_stats

EXTRACTOR_VERSION = "1.0.0"


def extract_all(
    content: str,
    structured: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> ExtractionResult:
    """Extract, normalise, resolve, and de-duplicate all technical threat indicators in content."""
    safe_content = content or ""
    # Enforce 20,000 char boundary safety
    if len(safe_content) > 20000:
        safe_content = safe_content[:20000]

    # 1. Text Statistics
    text_stats = compute_text_stats(safe_content)

    # 2. Extract Regex Candidates from Text
    regex_candidates: List[ExtractedIndicator] = []
    regex_candidates.extend(extract_pgp_fingerprints(safe_content))
    regex_candidates.extend(extract_cert_fingerprints(safe_content))
    regex_candidates.extend(extract_cert_metadata(safe_content))
    from app.analysis.extraction.wallets import extract_wallets
    regex_candidates.extend(extract_wallets(safe_content))
    regex_candidates.extend(extract_ips(safe_content))
    regex_candidates.extend(extract_ports(safe_content))
    regex_candidates.extend(extract_domains_and_onions(safe_content))
    regex_candidates.extend(extract_server_banners(safe_content))

    # 3. Resolve Span Overlaps
    resolved_regex, dropped_overlaps = resolve_overlaps(regex_candidates, debug=debug)

    # 4. Extract Structured Indicators
    struct_indicators, struct_warnings = extract_structured_indicators(structured or {})

    # 5. De-duplicate within Post: UNIQUE(indicator_type, normalised_value)
    deduped_map: Dict[tuple, ExtractedIndicator] = {}

    for cand in resolved_regex:
        key = (cand.indicator_type, cand.normalised_value)
        if key not in deduped_map:
            cand.details["occurrences"] = 1
            cand.details["all_spans"] = [[cand.span_start, cand.span_end]]
            deduped_map[key] = cand
        else:
            existing = deduped_map[key]
            existing.details["occurrences"] = existing.details.get("occurrences", 1) + 1
            if "all_spans" not in existing.details:
                existing.details["all_spans"] = [[existing.span_start, existing.span_end]]
            existing.details["all_spans"].append([cand.span_start, cand.span_end])

    for s_cand in struct_indicators:
        key = (s_cand.indicator_type, s_cand.normalised_value)
        if key in deduped_map:
            # Keep regex text row as primary span; flag presence in structured field
            deduped_map[key].details["also_in_structured_field"] = True
        else:
            s_cand.details["occurrences"] = 1
            s_cand.details["all_spans"] = []
            s_cand.details["also_in_structured_field"] = True
            deduped_map[key] = s_cand

    debug_data: Dict[str, Any] = {}
    if debug:
        debug_data["dropped_overlaps"] = dropped_overlaps
        debug_data["raw_candidate_count"] = len(regex_candidates)
        debug_data["resolved_count"] = len(resolved_regex)

    return ExtractionResult(
        indicators=list(deduped_map.values()),
        text_stats=text_stats,
        warnings=struct_warnings,
        debug=debug_data,
    )


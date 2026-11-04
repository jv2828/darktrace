"""Threat actor indicator matching package (cryptographic and infrastructure correlation)."""

from app.analysis.matching.common import (
    calculate_specificity,
    is_common_indicator,
    mask_indicator_value,
    sort_evidence_candidates,
    sort_suppressed_indicators,
)
from app.analysis.matching.crypto import match_cryptographic
from app.analysis.matching.infrastructure import match_infrastructure
from app.analysis.matching.models import EvidenceCandidate, IndicatorRecord, SuppressedIndicator

__all__ = [
    "IndicatorRecord",
    "EvidenceCandidate",
    "SuppressedIndicator",
    "match_cryptographic",
    "match_infrastructure",
    "calculate_specificity",
    "is_common_indicator",
    "mask_indicator_value",
    "sort_evidence_candidates",
    "sort_suppressed_indicators",
]


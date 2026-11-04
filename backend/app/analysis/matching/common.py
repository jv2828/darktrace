"""Common utilities, scoring formulas, and explanation templates for matching engines."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.matching.models import EvidenceCandidate, IndicatorRecord, SuppressedIndicator


def calculate_specificity(n_actors: int, full_strength_max_actors: int) -> float:
    """Compute indicator specificity as min(1.0, full_strength_max_actors / N)."""
    if n_actors <= 0:
        return 0.0
    return min(1.0, float(full_strength_max_actors) / float(n_actors))


def is_common_indicator(n_actors: int, common_indicator_min_actors: int) -> bool:
    """Check if an indicator is so prevalent across actors that it must be suppressed."""
    return n_actors >= common_indicator_min_actors


def mask_indicator_value(value: str) -> str:
    """Mask long indicator values (first 8 and last 4 characters)."""
    val_str = str(value)
    if len(val_str) > 14:
        return f"{val_str[:8]}…{val_str[-4:]}"
    return val_str


def get_lowest_confidence_factor(
    records: List[IndicatorRecord],
    confidence_factors: Dict[str, float],
) -> float:
    """Determine the confidence factor corresponding to the lowest confidence level in records."""
    ranks = {"low": 0, "medium": 1, "high": 2}
    lowest_rank = 2
    lowest_name = "high"

    for r in records:
        conf = (r.confidence or "high").lower().strip()
        rank = ranks.get(conf, 2)
        if rank < lowest_rank:
            lowest_rank = rank
            lowest_name = conf

    return float(confidence_factors.get(lowest_name, 1.0))


def format_actor_usage(
    actor_id: int,
    records: List[IndicatorRecord],
    actors_info: Optional[Dict[int, Dict[str, Any]]] = None,
) -> str:
    """Format plain-English usage of an indicator by an actor."""
    meta = (actors_info or {}).get(actor_id, {})
    username = meta.get("username", f"actor_{actor_id}")
    marketplace = meta.get("marketplace_name", meta.get("marketplace", "Dark Web"))

    valid_dates = [r.posted_at for r in records if r.posted_at is not None]
    post_count = len(records)
    post_word = "post" if post_count == 1 else "posts"

    if valid_dates:
        first_d = min(valid_dates).strftime("%Y-%m-%d")
        last_d = max(valid_dates).strftime("%Y-%m-%d")
        if post_count == 1 or first_d == last_d:
            date_str = f" ({first_d})"
        else:
            date_str = f" (first {first_d}, last {last_d})"
    else:
        date_str = ""

    return f"'{username}' on {marketplace} used it in {post_count} {post_word}{date_str}"


def build_pair_explanation(
    item_label: str,
    masked_value: str,
    actor_a_id: int,
    records_a: List[IndicatorRecord],
    actor_b_id: int,
    records_b: List[IndicatorRecord],
    total_distinct_actors: int,
    caveat_sentence: str,
    actors_info: Optional[Dict[int, Dict[str, Any]]] = None,
) -> str:
    """Generate deterministic, plain-English explanation for a pairwise match."""
    usage_a = format_actor_usage(actor_a_id, records_a, actors_info)
    usage_b = format_actor_usage(actor_b_id, records_b, actors_info)

    if total_distinct_actors == 2:
        prevalence_clause = f"Only these 2 personas in this investigation use it, so this is strong evidence of a shared {item_label}."
    else:
        prevalence_clause = f"Only {total_distinct_actors} personas in this investigation use it, so this is evidence of a shared {item_label}."

    return (
        f"Both personas posted the same {item_label} ({masked_value}). "
        f"{usage_a} and {usage_b}. "
        f"{prevalence_clause} {caveat_sentence}"
    )


def sort_evidence_candidates(candidates: List[EvidenceCandidate]) -> List[EvidenceCandidate]:
    """Deterministically sort evidence candidates by strength desc, then identifiers."""
    return sorted(
        candidates,
        key=lambda c: (
            -c.strength,
            c.actor_a_id,
            c.actor_b_id,
            c.evidence_type,
            c.explanation,
        ),
    )


def sort_suppressed_indicators(suppressed: List[SuppressedIndicator]) -> List[SuppressedIndicator]:
    """Deterministically sort suppressed indicators."""
    return sorted(suppressed, key=lambda s: (s.type, s.normalised_value))


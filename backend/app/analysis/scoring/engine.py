"""Multi-dimensional scoring engine synthesizing cross-dimensional evidence into composite scores."""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


def noisy_or(strengths: List[float]) -> float:
    """Compute independent multi-signal probability: 1 - prod(1 - s)."""
    if not strengths:
        return 0.0
    prod = 1.0
    for s in strengths:
        prod *= (1.0 - max(0.0, min(1.0, s)))
    return max(0.0, min(1.0, 1.0 - prod))


def calculate_pair_score(
    actor_a_id: int,
    actor_b_id: int,
    supporting_by_dimension: Dict[str, List[float]],
    dimension_availability: Dict[str, Dict[str, Any]],
    weights: Dict[str, float],
    thresholds: Dict[str, Any],
    style_z: Optional[float] = None,
    behaviour_z: Optional[float] = None,
    style_profile_data: Optional[Dict[str, Any]] = None,
    behaviour_profile_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate multi-dimensional composite evidence score for an actor pair.
    
    Returns structured correlation record ready for correlation_results storage.
    """
    scoring_thresh = thresholds.get("scoring", {})
    levels_cfg = scoring_thresh.get("levels", {"strong": 0.70, "moderate": 0.45, "weak": 0.25})
    contra_z_thresh = float(scoring_thresh.get("contradiction_z", 1.5))
    contra_min_strength = float(scoring_thresh.get("contradiction_min_strength", 0.30))
    contra_penalty = float(scoring_thresh.get("contradiction_penalty", 0.50))

    # 1. Dimension scores and availability state
    # Dimensions: cryptographic, infrastructure, stylometric, behavioural
    dim_scores: Dict[str, Dict[str, Any]] = {}
    counted_dims: List[str] = []
    missing_dimensions: List[Dict[str, Any]] = []

    # Positive-only dimensions: cryptographic & infrastructure
    for dim in ("cryptographic", "infrastructure"):
        strengths = supporting_by_dimension.get(dim, [])
        avail = dimension_availability.get(dim, {})
        has_actors_data = avail.get("has_data", True)

        if strengths:
            score = noisy_or(strengths)
            state = "matched"
            counted = True
            counted_dims.append(dim)
        elif not has_actors_data:
            score = 0.0
            state = "no_data"
            counted = False
        else:
            score = 0.0
            state = "no_match"
            counted = False

        dim_scores[dim] = {
            "score": round(score, 4),
            "counted": counted,
            "evidence_count": len(strengths),
            "state": state,
        }

    # Bidirectional dimensions: stylometric & behavioural
    # Stylometric
    style_avail = dimension_availability.get("stylometric", {})
    style_strengths = supporting_by_dimension.get("stylometric", [])
    if style_avail.get("is_sufficient", False):
        style_score = style_strengths[0] if style_strengths else 0.0
        counted = True
        counted_dims.append("stylometric")
        state = "scored"
    else:
        style_score = 0.0
        counted = False
        state = "insufficient"
        missing_dimensions.append({
            "dimension": "stylometric",
            "reason": style_avail.get("reason", "insufficient_text"),
        })

    dim_scores["stylometric"] = {
        "score": round(style_score, 4),
        "counted": counted,
        "evidence_count": len(style_strengths),
        "state": state,
    }

    # Behavioural
    behav_avail = dimension_availability.get("behavioural", {})
    behav_strengths = supporting_by_dimension.get("behavioural", [])
    if behav_avail.get("is_sufficient", False):
        behav_score = behav_strengths[0] if behav_strengths else 0.0
        counted = True
        counted_dims.append("behavioural")
        state = "scored"
    else:
        behav_score = 0.0
        counted = False
        state = "insufficient"
        missing_dimensions.append({
            "dimension": "behavioural",
            "reason": behav_avail.get("reason", "insufficient_timestamps"),
        })

    dim_scores["behavioural"] = {
        "score": round(behav_score, 4),
        "counted": counted,
        "evidence_count": len(behav_strengths),
        "state": state,
    }

    # 2. Combined score before penalty
    total_counted_weight = sum(weights.get(d, 0.0) for d in counted_dims)
    contributions: Dict[str, Any] = {}

    if total_counted_weight > 0:
        pre_penalty = sum(
            weights[d] * dim_scores[d]["score"] for d in counted_dims
        ) / total_counted_weight

        for d in counted_dims:
            eff_w = weights[d] / total_counted_weight
            contrib = eff_w * dim_scores[d]["score"]
            contributions[d] = {
                "weight": round(weights[d], 4),
                "effective_weight": round(eff_w, 4),
                "score": round(dim_scores[d]["score"], 4),
                "contribution": round(contrib, 4),
            }
    else:
        pre_penalty = 0.0

    # 3. Contradictions evaluation
    contradictions: List[Dict[str, Any]] = []
    generated_contra_records: List[Dict[str, Any]] = []

    has_shared_indicator = (
        (dim_scores["cryptographic"]["score"] > 0)
        or (dim_scores["infrastructure"]["score"] > 0)
    )

    # Check stylometric contradiction
    if dim_scores["stylometric"]["counted"] and style_z is not None:
        is_style_contra = (style_z <= -contra_z_thresh) or (has_shared_indicator and style_z <= -1.2)
        if is_style_contra:
            if style_z <= -contra_z_thresh:
                c_strength = max(0.0, min(1.0, (-style_z - contra_z_thresh) / 2.0))
            else:
                c_strength = max(0.30, min(1.0, (-style_z - 1.0) / 1.5))
            if c_strength >= contra_min_strength:
                c_strength = round(c_strength, 4)
                expl = (
                    f"The writing styles show significant divergence compared to the baseline (z = {style_z:.2f}). "
                    "This indicates contrasting linguistic habits, weakening common operator hypothesis."
                )
                contra_item = {
                    "dimension": "stylometric",
                    "strength": c_strength,
                    "short_text": expl,
                }
                contradictions.append(contra_item)
                generated_contra_records.append({
                    "actor_a_id": actor_a_id,
                    "actor_b_id": actor_b_id,
                    "dimension": "stylometric",
                    "evidence_type": "stylometric_divergence",
                    "direction": "contradicting",
                    "strength": c_strength,
                    "explanation": expl,
                    "details": {"z": style_z, "contradiction_z": contra_z_thresh},
                })

    # Check behavioural contradiction
    if dim_scores["behavioural"]["counted"]:
        hourly_sim = behaviour_profile_data.get("hourly", 1.0) if behaviour_profile_data else 1.0
        is_behav_contra = (behaviour_z is not None and behaviour_z <= -contra_z_thresh) or (has_shared_indicator and hourly_sim <= 0.20)
        if is_behav_contra:
            if behaviour_z is not None and behaviour_z <= -contra_z_thresh:
                c_strength = max(0.0, min(1.0, (-behaviour_z - contra_z_thresh) / 2.0))
            else:
                c_strength = max(0.30, min(1.0, round(1.0 - hourly_sim, 2)))
            if c_strength >= contra_min_strength:
                c_strength = round(c_strength, 4)
                peak_a = behaviour_profile_data.get("peak_a", "N/A") if behaviour_profile_data else "N/A"
                peak_b = behaviour_profile_data.get("peak_b", "N/A") if behaviour_profile_data else "N/A"
                expl = (
                    f"The two personas post at clearly different hours (peak {peak_a} vs {peak_b} UTC). "
                    "This weakens the link suggested by the other evidence."
                )
                contra_item = {
                    "dimension": "behavioural",
                    "strength": c_strength,
                    "short_text": expl,
                }
                contradictions.append(contra_item)
                generated_contra_records.append({
                    "actor_a_id": actor_a_id,
                    "actor_b_id": actor_b_id,
                    "dimension": "behavioural",
                    "evidence_type": "temporal_divergence",
                    "direction": "contradicting",
                    "strength": c_strength,
                    "explanation": expl,
                    "details": {"z": behaviour_z, "hourly_similarity": hourly_sim, "contradiction_z": contra_z_thresh},
                })

    # 4. Final combined score after contradiction penalty
    max_contra_strength = max([c["strength"] for c in contradictions], default=0.0)
    penalty_factor = max(0.0, 1.0 - (contra_penalty * max_contra_strength))
    final_combined = pre_penalty * penalty_factor
    final_combined = max(0.0, min(1.0, final_combined))
    final_combined = round(final_combined, 4)

    # 5. Coverage
    total_all_weights = sum(weights.values())
    coverage = (total_counted_weight / total_all_weights) if total_all_weights > 0 else 0.0
    coverage = round(max(0.0, min(1.0, coverage)), 4)

    # 6. Confidence Level
    if final_combined >= levels_cfg.get("strong", 0.70):
        level = "strong"
    elif final_combined >= levels_cfg.get("moderate", 0.45):
        level = "moderate"
    elif final_combined >= levels_cfg.get("weak", 0.25):
        level = "weak"
    else:
        level = "none"

    # Rule: single dimension cap
    dimensions_with_positive_score = [
        d for d in counted_dims if dim_scores[d]["score"] > 0
    ]
    if len(dimensions_with_positive_score) == 1:
        single_dim = dimensions_with_positive_score[0]
        # Only uncapped if cryptographic with strength >= 0.90
        if not (single_dim == "cryptographic" and dim_scores["cryptographic"]["score"] >= 0.90):
            if level == "strong":
                level = "moderate"

    # Rule: contradiction with strength >= 0.6 caps at moderate
    if max_contra_strength >= 0.60:
        if level == "strong":
            level = "moderate"

    return {
        "actor_a_id": actor_a_id,
        "actor_b_id": actor_b_id,
        "combined_score": final_combined,
        "level": level,
        "coverage": coverage,
        "dimension_scores": dim_scores,
        "contributions": contributions,
        "missing_dimensions": missing_dimensions,
        "contradictions": contradictions,
        "contradicting_records": generated_contra_records,
    }

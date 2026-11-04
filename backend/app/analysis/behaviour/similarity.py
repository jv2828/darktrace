"""Pairwise behavioral comparison, temporal JSD similarity, and evidence generation."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.spatial.distance import jensenshannon

from app.analysis.behaviour.profile import circular_smooth


def compute_pair_behaviour_similarity(
    profile_a: Dict[str, Any],
    profile_b: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Compute hourly, daily, and posting frequency similarities between two behavioral profiles."""
    w = weights or {"hourly": 0.60, "daily": 0.25, "frequency": 0.15}

    # 1. Hourly JSD with circular smoothing
    raw_h_a = np.array(profile_a["hourly_distribution"], dtype=float)
    raw_h_b = np.array(profile_b["hourly_distribution"], dtype=float)
    smooth_h_a = circular_smooth(raw_h_a)
    smooth_h_b = circular_smooth(raw_h_b)

    jsd_h = float(jensenshannon(smooth_h_a, smooth_h_b, base=2))
    sim_hourly = max(0.0, min(1.0, 1.0 - jsd_h))

    # 2. Daily JSD with circular smoothing
    raw_d_a = np.array(profile_a["daily_distribution"], dtype=float)
    raw_d_b = np.array(profile_b["daily_distribution"], dtype=float)
    smooth_d_a = circular_smooth(raw_d_a)
    smooth_d_b = circular_smooth(raw_d_b)

    jsd_d = float(jensenshannon(smooth_d_a, smooth_d_b, base=2))
    sim_daily = max(0.0, min(1.0, 1.0 - jsd_d))

    # 3. Frequency similarity
    rate_a = max(1e-4, float(profile_a.get("posts_per_active_day", 1.0)))
    rate_b = max(1e-4, float(profile_b.get("posts_per_active_day", 1.0)))
    freq_ratio = abs(np.log(rate_a / rate_b)) / np.log(10.0)
    sim_freq = max(0.0, min(1.0, 1.0 - min(1.0, freq_ratio)))

    # Overall weighted mean
    overall = (
        w["hourly"] * sim_hourly
        + w["daily"] * sim_daily
        + w["frequency"] * sim_freq
    )
    overall = max(0.0, min(1.0, overall))

    return {
        "hourly": round(sim_hourly, 4),
        "daily": round(sim_daily, 4),
        "frequency": round(sim_freq, 4),
        "overall": round(overall, 4),
    }


def compare_actors_behaviour(
    actor_profiles: Dict[int, Dict[str, Any]],
    config_weights: Optional[Dict[str, float]] = None,
    z_support: float = 1.5,
    z_full: float = 3.5,
) -> Tuple[
    List[Dict[str, Any]],  # supporting evidence candidates
    List[Dict[str, Any]],  # all comparable pair records
    Dict[str, Any],        # stage metrics
]:
    """Execute pairwise behavioral cross-comparison with relative z-scoring."""
    # Comparable actors are those with sufficient or limited timestamps
    comparable_actor_ids = sorted([
        aid for aid, prof in actor_profiles.items()
        if prof.get("sufficiency") in ("sufficient", "limited")
    ])

    if len(comparable_actor_ids) < 2:
        return [], [], {
            "actors_compared": len(comparable_actor_ids),
            "baseline": 0.0,
            "spread": 0.02,
            "pairs_compared": 0,
            "pairs_supporting": 0,
        }

    pair_records: List[Dict[str, Any]] = []

    for i in range(len(comparable_actor_ids)):
        aid_a = comparable_actor_ids[i]
        prof_a = actor_profiles[aid_a]
        for j in range(i + 1, len(comparable_actor_ids)):
            aid_b = comparable_actor_ids[j]
            prof_b = actor_profiles[aid_b]

            sims = compute_pair_behaviour_similarity(prof_a, prof_b, weights=config_weights)

            pair_records.append({
                "actor_a_id": min(aid_a, aid_b),
                "actor_b_id": max(aid_a, aid_b),
                "hourly": sims["hourly"],
                "daily": sims["daily"],
                "frequency": sims["frequency"],
                "overall": sims["overall"],
            })

    # Relative z-scoring across comparable pairs
    overall_vals = np.array([p["overall"] for p in pair_records])
    baseline = float(np.median(overall_vals))
    mad = float(np.median(np.abs(overall_vals - baseline)))
    spread = float(max(1.4826 * mad, 0.02))

    baseline_reliable = len(pair_records) >= 6

    evidence_candidates: List[Dict[str, Any]] = []

    for p in pair_records:
        z = (p["overall"] - baseline) / spread
        p["z"] = round(float(z), 4)

        aid_a = p["actor_a_id"]
        aid_b = p["actor_b_id"]
        prof_a = actor_profiles[aid_a]
        prof_b = actor_profiles[aid_b]

        suff_a = prof_a.get("sufficiency", "limited")
        suff_b = prof_b.get("sufficiency", "limited")
        data_factor = 1.0 if (suff_a == "sufficient" and suff_b == "sufficient") else 0.7

        if z >= z_support:
            raw_strength = (z - z_support) / (z_full - z_support)
            raw_strength = max(0.0, min(1.0, raw_strength))
            strength = raw_strength * data_factor
            if not baseline_reliable:
                strength = min(strength, 0.5)

            strength = round(float(strength), 4)

            peak_a = f"{prof_a['peak_hour']:02d}:00 UTC"
            peak_b = f"{prof_b['peak_hour']:02d}:00 UTC"
            window_a = prof_a.get("active_hour_window_str", "N/A")
            window_b = prof_b.get("active_hour_window_str", "N/A")

            explanation = (
                f"The two personas exhibit strongly aligned activity schedules (z = {z:.2f}). "
                f"Peak activity occurs around {peak_a} and {peak_b} with active windows {window_a} and {window_b}. "
                "Caveat: Automated posting tools or standard timezone operating hours can produce coincident activity patterns."
            )

            details = {
                "components": {
                    "hourly": p["hourly"],
                    "daily": p["daily"],
                    "frequency": p["frequency"],
                },
                "overall": p["overall"],
                "z": p["z"],
                "baseline": round(baseline, 4),
                "spread": round(spread, 4),
                "baseline_reliable": baseline_reliable,
                "actor_a_peak_hour": prof_a["peak_hour"],
                "actor_b_peak_hour": prof_b["peak_hour"],
                "actor_a_window": prof_a.get("active_hour_window"),
                "actor_b_window": prof_b.get("active_hour_window"),
                "actor_a_posts": prof_a["total_posts"],
                "actor_b_posts": prof_b["total_posts"],
                "actor_a_sufficiency": suff_a,
                "actor_b_sufficiency": suff_b,
            }

            evidence_candidates.append({
                "actor_a_id": aid_a,
                "actor_b_id": aid_b,
                "dimension": "behavioural",
                "evidence_type": "temporal_distribution_similarity",
                "direction": "supporting",
                "strength": strength,
                "explanation": explanation,
                "details": details,
            })

    run_metrics = {
        "actors_compared": len(comparable_actor_ids),
        "pairs_compared": len(pair_records),
        "baseline": round(baseline, 4),
        "spread": round(spread, 4),
        "baseline_reliable": baseline_reliable,
        "pairs_supporting": len(evidence_candidates),
    }

    return evidence_candidates, pair_records, run_metrics


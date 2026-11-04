"""Cryptographic indicator matching engine (PGP keys and cryptocurrency wallets)."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.matching.common import (
    build_pair_explanation,
    calculate_specificity,
    get_lowest_confidence_factor,
    is_common_indicator,
    mask_indicator_value,
    sort_evidence_candidates,
    sort_suppressed_indicators,
)
from app.analysis.matching.models import EvidenceCandidate, IndicatorRecord, SuppressedIndicator

CRYPTO_INDICATOR_TYPES = {
    "pgp_fingerprint",
    "wallet_btc",
    "wallet_eth",
    "wallet_xmr",
    "wallet_other",
}

CRYPTO_CAVEATS = {
    "pgp_fingerprint": "A shared key can also mean a shared service or leaked key, so it is not proof of identity.",
    "wallet": "A wallet can also be a payment address given to others, so it is not proof of identity.",
}


class CoverageSummary(dict):
    """Coverage container mapping actor IDs to presence and providing aggregate summary metrics."""

    def __init__(self, per_actor: Dict[int, bool]):
        self.per_actor = per_actor
        actors_total = len(per_actor)
        actors_with = sum(1 for v in per_actor.values() if v)
        super().__init__({
            "actors_total": actors_total,
            "actors_with_dimension_indicators": actors_with,
            "per_actor": per_actor,
        })

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self.per_actor.get(key, False)
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, int):
            return key in self.per_actor
        return super().__contains__(key)


def match_cryptographic(
    records: List[IndicatorRecord],
    config: Dict[str, Any],
    actors_info: Optional[Dict[int, Dict[str, Any]]] = None,
    all_actor_ids: Optional[Set[int]] = None,
) -> Tuple[List[EvidenceCandidate], List[SuppressedIndicator], CoverageSummary]:
    """Execute cryptographic matching on extracted indicator records."""
    full_strength_max_actors = int(config.get("full_strength_max_actors", 3))
    common_indicator_min_actors = int(config.get("common_indicator_min_actors", 5))
    confidence_factors = config.get(
        "confidence_factor", {"high": 1.0, "medium": 0.8, "low": 0.6}
    )
    crypto_base_strength = config.get(
        "crypto_base_strength",
        {
            "pgp_fingerprint": 0.95,
            "wallet_btc": 0.85,
            "wallet_eth": 0.85,
            "wallet_xmr": 0.85,
            "wallet_other": 0.60,
        },
    )

    # Establish universe of actors for coverage
    universe_actors: Set[int] = set(all_actor_ids or [])
    for r in records:
        universe_actors.add(r.actor_id)

    # Group indicators strictly by (indicator_type, normalised_value)
    grouped: Dict[Tuple[str, str], List[IndicatorRecord]] = defaultdict(list)
    actors_with_crypto: Set[int] = set()

    for r in records:
        if r.indicator_type in CRYPTO_INDICATOR_TYPES:
            grouped[(r.indicator_type, r.normalised_value)].append(r)
            actors_with_crypto.add(r.actor_id)

    candidates: List[EvidenceCandidate] = []
    suppressed: List[SuppressedIndicator] = []

    for (ind_type, norm_val), rec_list in grouped.items():
        # Group records by actor
        actor_map: Dict[int, List[IndicatorRecord]] = defaultdict(list)
        marketplaces: Set[int] = set()
        for r in rec_list:
            actor_map[r.actor_id].append(r)
            marketplaces.add(r.marketplace_id)

        distinct_actors = sorted(list(actor_map.keys()))
        n_actors = len(distinct_actors)

        # Single actor posting value many times is NOT pairwise evidence
        if n_actors < 2:
            continue

        # Common indicator suppression
        if is_common_indicator(n_actors, common_indicator_min_actors):
            suppressed.append(
                SuppressedIndicator(
                    type=ind_type,
                    normalised_value=norm_val,
                    actor_count=n_actors,
                    marketplace_count=len(marketplaces),
                )
            )
            continue

        # Valid non-common shared indicator
        specificity = calculate_specificity(n_actors, full_strength_max_actors)
        base_strength = float(crypto_base_strength.get(ind_type, 0.60))

        if ind_type == "pgp_fingerprint":
            item_label = "PGP fingerprint"
            evidence_type = "shared_pgp_fingerprint"
            caveat = CRYPTO_CAVEATS["pgp_fingerprint"]
        else:
            chain = ind_type.replace("wallet_", "")
            item_label = f"{chain.upper()} wallet address" if chain != "other" else "cryptocurrency wallet address"
            evidence_type = f"shared_wallet_{chain}"
            caveat = CRYPTO_CAVEATS["wallet"]

        masked_val = mask_indicator_value(norm_val)

        # Generate pairwise candidates for all actor pairs (a < b)
        for i in range(n_actors):
            for j in range(i + 1, n_actors):
                actor_a = distinct_actors[i]
                actor_b = distinct_actors[j]
                recs_a = actor_map[actor_a]
                recs_b = actor_map[actor_b]
                pair_records = recs_a + recs_b

                conf_factor = get_lowest_confidence_factor(pair_records, confidence_factors)
                strength = round(base_strength * conf_factor * specificity, 4)

                explanation = build_pair_explanation(
                    item_label=item_label,
                    masked_value=masked_val,
                    actor_a_id=actor_a,
                    records_a=recs_a,
                    actor_b_id=actor_b,
                    records_b=recs_b,
                    total_distinct_actors=n_actors,
                    caveat_sentence=caveat,
                    actors_info=actors_info,
                )

                # Cap source lists at 20 posts and 20 indicators per side
                source_posts_a = sorted(list(set(r.post_id for r in recs_a)))[:20]
                source_posts_b = sorted(list(set(r.post_id for r in recs_b)))[:20]
                source_posts = sorted(list(set(source_posts_a + source_posts_b)))

                source_inds_a = sorted(list(set(r.indicator_id for r in recs_a)))[:20]
                source_inds_b = sorted(list(set(r.indicator_id for r in recs_b)))[:20]
                source_indicators = sorted(list(set(source_inds_a + source_inds_b)))

                details = {
                    "indicator_type": ind_type,
                    "normalised_value": norm_val,
                    "actor_count": n_actors,
                    "specificity": round(specificity, 4),
                    "base_strength": base_strength,
                    "confidence_factor": conf_factor,
                }

                candidates.append(
                    EvidenceCandidate(
                        actor_a_id=actor_a,
                        actor_b_id=actor_b,
                        dimension="cryptographic",
                        evidence_type=evidence_type,
                        direction="supporting",
                        strength=strength,
                        explanation=explanation,
                        details=details,
                        source_post_ids=source_posts,
                        source_indicator_ids=source_indicators,
                    )
                )

    per_actor_coverage = {aid: (aid in actors_with_crypto) for aid in universe_actors}
    coverage = CoverageSummary(per_actor_coverage)

    return (
        sort_evidence_candidates(candidates),
        sort_suppressed_indicators(suppressed),
        coverage,
    )


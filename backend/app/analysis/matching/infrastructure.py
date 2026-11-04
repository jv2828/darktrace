"""Infrastructure indicator matching engine (domains, IPs, ports, SSL certificates, banners)."""

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
from app.analysis.matching.crypto import CoverageSummary
from app.analysis.matching.models import EvidenceCandidate, IndicatorRecord, SuppressedIndicator

INFRA_INDICATOR_TYPES = {
    "domain",
    "ip_address",
    "port",
    "ssl_cert_fingerprint",
    "cert_metadata",
    "server_banner",
}

INFRA_CAVEATS = {
    "shared_cert_fingerprint": "Shared certificate attributes can arise from default configurations or shared hosting, so it is not proof of identity.",
    "shared_onion_domain": "A shared onion domain can host multiple distinct vendor storefronts, so it is not proof of identity.",
    "shared_domain": "A shared domain can also host multiple independent services, so it is not proof of identity.",
    "shared_ip_address": "A shared IP address can also indicate shared hosting, VPN, or proxy infrastructure, so it is not proof of identity.",
    "shared_cert_serial": "Shared certificate attributes can arise from default configurations or shared hosting, so it is not proof of identity.",
    "shared_cert_subject_cn": "Shared certificate attributes can arise from default configurations or shared hosting, so it is not proof of identity.",
    "shared_cert_issuer": "Shared certificate attributes can arise from default configurations or shared hosting, so it is not proof of identity.",
    "shared_server_banner": "Identical server banners are common across systems running standard software distributions, so this is only weak corroborating evidence.",
    "corroborating_port": "Non-standard ports can be used across multiple services, so this is only corroborating context.",
}


def _resolve_infra_sub_item(record: IndicatorRecord) -> Optional[Tuple[str, str, str, str, Dict[str, Any]]]:
    """Resolve sub-type, evidence_type, base_strength key, item label, and details extra.

    Returns (sub_type, evidence_type, base_strength_key, item_label, extra_details) or None.
    """
    t = record.indicator_type
    v = record.normalised_value

    if t == "ssl_cert_fingerprint":
        return (
            "ssl_cert_fingerprint",
            "shared_cert_fingerprint",
            "ssl_cert_fingerprint",
            "SSL certificate fingerprint",
            {},
        )
    elif t == "domain":
        if v.endswith(".onion"):
            return (
                "onion_domain",
                "shared_onion_domain",
                "onion_domain",
                "Tor .onion domain",
                {"kind": "onion"},
            )
        else:
            return (
                "domain",
                "shared_domain",
                "domain",
                "domain name",
                {"kind": "clearnet"},
            )
    elif t == "ip_address":
        return (
            "ip_address",
            "shared_ip_address",
            "ip_address",
            "IP address",
            {},
        )
    elif t == "server_banner":
        return (
            "server_banner",
            "shared_server_banner",
            "server_banner",
            "server banner",
            {},
        )
    elif t == "cert_metadata":
        field_name = (record.details or {}).get("field", "")
        if field_name == "serial":
            return (
                "cert_serial",
                "shared_cert_serial",
                "cert_serial",
                "SSL certificate serial number",
                {"field": "serial"},
            )
        elif field_name == "subject_cn":
            return (
                "cert_subject_cn",
                "shared_cert_subject_cn",
                "cert_subject_cn",
                "SSL certificate Subject CN",
                {"field": "subject_cn"},
            )
        elif field_name == "issuer":
            return (
                "cert_issuer",
                "shared_cert_issuer",
                "cert_issuer",
                "SSL certificate Issuer",
                {"field": "issuer"},
            )
        return None
    elif t == "port":
        return (
            "port",
            "corroborating_port",
            "port",
            "service port",
            {"corroborating": True},
        )
    return None


def match_infrastructure(
    records: List[IndicatorRecord],
    config: Dict[str, Any],
    actors_info: Optional[Dict[int, Dict[str, Any]]] = None,
    all_actor_ids: Optional[Set[int]] = None,
) -> Tuple[List[EvidenceCandidate], List[SuppressedIndicator], CoverageSummary]:
    """Execute infrastructure matching on extracted indicator records."""
    full_strength_max_actors = int(config.get("full_strength_max_actors", 3))
    common_indicator_min_actors = int(config.get("common_indicator_min_actors", 5))
    confidence_factors = config.get(
        "confidence_factor", {"high": 1.0, "medium": 0.8, "low": 0.6}
    )
    infra_base_strength = config.get(
        "infrastructure_base_strength",
        {
            "ssl_cert_fingerprint": 0.90,
            "onion_domain": 0.90,
            "cert_serial": 0.80,
            "domain": 0.60,
            "ip_address": 0.55,
            "cert_subject_cn": 0.50,
            "server_banner": 0.15,
            "cert_issuer": 0.10,
            "port": 0.10,
        },
    )
    standard_ports_list = config.get(
        "standard_ports",
        [21, 22, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 5432, 8080],
    )
    standard_ports_set: Set[str] = {str(p) for p in standard_ports_list}

    # Establish universe of actors for coverage
    universe_actors: Set[int] = set(all_actor_ids or [])
    for r in records:
        universe_actors.add(r.actor_id)

    actors_with_infra: Set[int] = set()

    # Separate non-port indicators from port indicators
    non_port_grouped: Dict[Tuple[str, str], List[IndicatorRecord]] = defaultdict(list)
    port_grouped: Dict[str, List[IndicatorRecord]] = defaultdict(list)
    sub_type_meta: Dict[str, Tuple[str, str, str, Dict[str, Any]]] = {}

    for r in records:
        if r.indicator_type not in INFRA_INDICATOR_TYPES:
            continue
        actors_with_infra.add(r.actor_id)

        resolved = _resolve_infra_sub_item(r)
        if not resolved:
            continue

        sub_type, evidence_type, base_strength_key, item_label, extra_details = resolved
        sub_type_meta[sub_type] = (evidence_type, base_strength_key, item_label, extra_details)

        if sub_type == "port":
            # Ports in standard_ports are immediately ignored (produce nothing)
            if str(r.normalised_value) not in standard_ports_set:
                port_grouped[r.normalised_value].append(r)
        else:
            non_port_grouped[(sub_type, r.normalised_value)].append(r)

    candidates: List[EvidenceCandidate] = []
    suppressed: List[SuppressedIndicator] = []
    pairs_with_other_infra: Set[Tuple[int, int]] = set()

    # Phase 1: Process all non-port infrastructure indicators
    for (sub_type, norm_val), rec_list in non_port_grouped.items():
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

        orig_type = rec_list[0].indicator_type

        # Check suppression
        if is_common_indicator(n_actors, common_indicator_min_actors):
            suppressed.append(
                SuppressedIndicator(
                    type=orig_type,
                    normalised_value=norm_val,
                    actor_count=n_actors,
                    marketplace_count=len(marketplaces),
                )
            )
            continue

        evidence_type, base_strength_key, item_label, extra_details = sub_type_meta[sub_type]
        specificity = calculate_specificity(n_actors, full_strength_max_actors)
        base_strength = float(infra_base_strength.get(base_strength_key, 0.50))
        caveat = INFRA_CAVEATS.get(evidence_type, "This indicator alone is not proof of identity.")
        masked_val = mask_indicator_value(norm_val)

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

                source_posts_a = sorted(list(set(r.post_id for r in recs_a)))[:20]
                source_posts_b = sorted(list(set(r.post_id for r in recs_b)))[:20]
                source_posts = sorted(list(set(source_posts_a + source_posts_b)))

                source_inds_a = sorted(list(set(r.indicator_id for r in recs_a)))[:20]
                source_inds_b = sorted(list(set(r.indicator_id for r in recs_b)))[:20]
                source_indicators = sorted(list(set(source_inds_a + source_inds_b)))

                details = {
                    "indicator_type": orig_type,
                    "normalised_value": norm_val,
                    "actor_count": n_actors,
                    "specificity": round(specificity, 4),
                    "base_strength": base_strength,
                    "confidence_factor": conf_factor,
                    **extra_details,
                }

                candidates.append(
                    EvidenceCandidate(
                        actor_a_id=actor_a,
                        actor_b_id=actor_b,
                        dimension="infrastructure",
                        evidence_type=evidence_type,
                        direction="supporting",
                        strength=strength,
                        explanation=explanation,
                        details=details,
                        source_post_ids=source_posts,
                        source_indicator_ids=source_indicators,
                    )
                )
                pairs_with_other_infra.add((actor_a, actor_b))

    # Phase 2: Process non-standard ports as corroborating evidence
    for norm_val, rec_list in port_grouped.items():
        actor_map = defaultdict(list)
        marketplaces = set()
        for r in rec_list:
            actor_map[r.actor_id].append(r)
            marketplaces.add(r.marketplace_id)

        distinct_actors = sorted(list(actor_map.keys()))
        n_actors = len(distinct_actors)

        if n_actors < 2:
            continue

        if is_common_indicator(n_actors, common_indicator_min_actors):
            suppressed.append(
                SuppressedIndicator(
                    type="port",
                    normalised_value=norm_val,
                    actor_count=n_actors,
                    marketplace_count=len(marketplaces),
                )
            )
            continue

        specificity = calculate_specificity(n_actors, full_strength_max_actors)
        base_strength = float(infra_base_strength.get("port", 0.10))
        caveat = INFRA_CAVEATS["corroborating_port"]
        masked_val = norm_val

        for i in range(n_actors):
            for j in range(i + 1, n_actors):
                actor_a = distinct_actors[i]
                actor_b = distinct_actors[j]

                # Only emit port evidence if the pair ALREADY has at least one other infrastructure candidate
                if (actor_a, actor_b) not in pairs_with_other_infra:
                    continue

                recs_a = actor_map[actor_a]
                recs_b = actor_map[actor_b]
                pair_records = recs_a + recs_b

                conf_factor = get_lowest_confidence_factor(pair_records, confidence_factors)
                strength = round(base_strength * conf_factor * specificity, 4)

                explanation = build_pair_explanation(
                    item_label="service port",
                    masked_value=masked_val,
                    actor_a_id=actor_a,
                    records_a=recs_a,
                    actor_b_id=actor_b,
                    records_b=recs_b,
                    total_distinct_actors=n_actors,
                    caveat_sentence=caveat,
                    actors_info=actors_info,
                )

                source_posts_a = sorted(list(set(r.post_id for r in recs_a)))[:20]
                source_posts_b = sorted(list(set(r.post_id for r in recs_b)))[:20]
                source_posts = sorted(list(set(source_posts_a + source_posts_b)))

                source_inds_a = sorted(list(set(r.indicator_id for r in recs_a)))[:20]
                source_inds_b = sorted(list(set(r.indicator_id for r in recs_b)))[:20]
                source_indicators = sorted(list(set(source_inds_a + source_inds_b)))

                details = {
                    "indicator_type": "port",
                    "normalised_value": norm_val,
                    "actor_count": n_actors,
                    "specificity": round(specificity, 4),
                    "base_strength": base_strength,
                    "confidence_factor": conf_factor,
                    "corroborating": True,
                }

                candidates.append(
                    EvidenceCandidate(
                        actor_a_id=actor_a,
                        actor_b_id=actor_b,
                        dimension="infrastructure",
                        evidence_type="corroborating_port",
                        direction="supporting",
                        strength=strength,
                        explanation=explanation,
                        details=details,
                        source_post_ids=source_posts,
                        source_indicator_ids=source_indicators,
                    )
                )

    per_actor_coverage = {aid: (aid in actors_with_infra) for aid in universe_actors}
    coverage = CoverageSummary(per_actor_coverage)

    return (
        sort_evidence_candidates(candidates),
        sort_suppressed_indicators(suppressed),
        coverage,
    )


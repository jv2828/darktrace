"""Service for retrieving, provisioning, and upgrading scoring configurations."""

from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import APIException
from app.models.scoring_config import ScoringConfig

DEFAULT_WEIGHTS: Dict[str, float] = {
    "cryptographic": 0.35,
    "infrastructure": 0.20,
    "stylometric": 0.25,
    "behavioural": 0.20,
}

DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "full_strength_max_actors": 3,
    "common_indicator_min_actors": 5,
    "confidence_factor": {"high": 1.0, "medium": 0.8, "low": 0.6},
    "crypto_base_strength": {
        "pgp_fingerprint": 0.95,
        "wallet_btc": 0.85,
        "wallet_eth": 0.85,
        "wallet_xmr": 0.85,
        "wallet_other": 0.60,
    },
    "infrastructure_base_strength": {
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
    "standard_ports": [21, 22, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 5432, 8080],
    "stylometry": {
        "weights": {
            "char_ngram": 0.35,
            "word_ngram": 0.15,
            "function_words": 0.25,
            "feature_vector": 0.25,
        },
        "z_support": 1.5,
        "z_full": 3.5,
        "min_words_sufficient": 300,
        "min_words_limited": 100,
    },
    "behaviour": {
        "weights": {
            "hourly": 0.60,
            "daily": 0.25,
            "frequency": 0.15,
        },
        "z_support": 1.5,
        "z_full": 3.5,
        "min_posts_sufficient": 10,
        "min_posts_limited": 5,
    },
    "scoring": {
        "levels": {
            "strong": 0.70,
            "moderate": 0.45,
            "weak": 0.25,
        },
        "min_report_score": 0.20,
        "contradiction_z": 1.5,
        "contradiction_min_strength": 0.30,
        "contradiction_penalty": 0.50,
        "potential_link": 0.45,
    },
}


def get_or_create_default(db: Session) -> ScoringConfig:
    """Retrieve active scoring configuration or upgrade/initialize default version."""
    active_cfg = db.execute(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True))
    ).scalar_one_or_none()

    if not active_cfg:
        default_cfg = ScoringConfig(
            name="default",
            version=1,
            weights=DEFAULT_WEIGHTS,
            thresholds=DEFAULT_THRESHOLDS,
            is_active=True,
        )
        db.add(default_cfg)
        db.commit()
        db.refresh(default_cfg)
        return default_cfg

    # Check if active config lacks Phase 8 keys (stylometry, behaviour, scoring)
    thresh = active_cfg.thresholds or {}
    needs_upgrade = (
        "stylometry" not in thresh
        or "behaviour" not in thresh
        or "scoring" not in thresh
    )

    if needs_upgrade:
        merged_thresholds = dict(DEFAULT_THRESHOLDS)
        merged_thresholds.update(thresh)
        for sub_key in ("stylometry", "behaviour", "scoring"):
            if sub_key not in merged_thresholds:
                merged_thresholds[sub_key] = DEFAULT_THRESHOLDS[sub_key]
            else:
                sub_dict = dict(DEFAULT_THRESHOLDS[sub_key])
                sub_dict.update(merged_thresholds[sub_key])
                merged_thresholds[sub_key] = sub_dict

        merged_weights = dict(DEFAULT_WEIGHTS)
        if active_cfg.weights:
            merged_weights.update(active_cfg.weights)

        active_cfg.is_active = False
        db.flush()

        new_cfg = ScoringConfig(
            name=active_cfg.name,
            version=active_cfg.version + 1,
            weights=merged_weights,
            thresholds=merged_thresholds,
            is_active=True,
            created_by=active_cfg.created_by,
        )
        db.add(new_cfg)
        db.commit()
        db.refresh(new_cfg)
        return new_cfg

    return active_cfg


def update_active_config(
    db: Session,
    weights: Dict[str, float],
    thresholds: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> ScoringConfig:
    """Validate weights/thresholds and atomically create a new configuration version."""
    expected_dims = {"cryptographic", "infrastructure", "stylometric", "behavioural"}
    provided_dims = set(weights.keys())
    if not expected_dims.issubset(provided_dims):
        raise APIException(
            code="INVALID_WEIGHTS",
            message=f"Weights must specify all required dimensions: {sorted(list(expected_dims))}",
            status_code=422,
        )

    for dim, w in weights.items():
        if not (0.0 <= w <= 1.0):
            raise APIException(
                code="INVALID_WEIGHTS",
                message=f"Weight for dimension '{dim}' must be between 0.0 and 1.0.",
                status_code=422,
            )

    weight_sum = sum(weights[d] for d in expected_dims)
    if abs(weight_sum - 1.0) > 0.001:
        raise APIException(
            code="INVALID_WEIGHTS",
            message=f"Weights must sum to 1.0 (+/- 0.001); provided sum is {weight_sum:.4f}.",
            status_code=422,
        )

    current_active = get_or_create_default(db)

    # Merge thresholds with existing thresholds
    merged_thresholds = dict(current_active.thresholds or DEFAULT_THRESHOLDS)
    if thresholds:
        merged_thresholds.update(thresholds)

    current_active.is_active = False
    db.flush()

    new_cfg = ScoringConfig(
        name=current_active.name,
        version=current_active.version + 1,
        weights={d: float(weights[d]) for d in expected_dims},
        thresholds=merged_thresholds,
        is_active=True,
        created_by=user_id,
    )
    db.add(new_cfg)
    db.commit()
    db.refresh(new_cfg)
    return new_cfg

"""Unit tests for stylometry, behavioral analysis, and scoring engine."""

from decimal import Decimal
import numpy as np
import pytest

from app.analysis.behaviour.profile import circular_smooth, compute_actor_behaviour_profile
from app.analysis.behaviour.similarity import compute_pair_behaviour_similarity
from app.analysis.scoring.engine import calculate_pair_score, noisy_or
from app.analysis.stylometry.features import extract_actor_features
from app.analysis.stylometry.prepare import (
    get_text_sufficiency,
    mask_post_content,
    tokenize_sentences,
    tokenize_words,
)
from app.analysis.stylometry.similarity import compare_actors_stylometry
from app.models.scoring_config import ScoringConfig
from app.services.scoring_config_service import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    get_or_create_default,
)


def test_masking_removes_indicator_spans_in_copy_only():
    original = "Contact vendor at 198.51.100.42 or PGP fingerprint 9a1b2c3d4e5f67890123456789abcdef01234567 for escrow."
    indicators = [
        {"span_start": 18, "span_end": 31, "indicator_type": "ip_address"},
        {"span_start": 51, "span_end": 91, "indicator_type": "pgp_fingerprint"},
    ]

    masked = mask_post_content(original, indicators)

    # Original text must remain untouched
    assert "198.51.100.42" in original
    assert "9a1b2c3d4e5f67890123456789abcdef01234567" in original

    # Masked text must have placeholders
    assert "<IP>" in masked
    assert "<PGP>" in masked
    assert "198.51.100.42" not in masked
    assert "9a1b2c3d4e5f67890123456789abcdef01234567" not in masked


def test_features_are_deterministic_and_in_sane_ranges():
    text = "Hello world! This is a test sentence with numbers 12345. Are you ready? YES WE CAN!  Extra space here."
    words = tokenize_words(text)
    sentences = tokenize_sentences(text)

    feat1, fw1 = extract_actor_features(text, words, sentences, 1)
    feat2, fw2 = extract_actor_features(text, words, sentences, 1)

    assert feat1 == feat2
    assert fw1 == fw2

    assert 0.0 <= feat1["digit_ratio"] <= 1.0
    assert 0.0 <= feat1["uppercase_letter_ratio"] <= 1.0
    assert 0.0 <= feat1["all_caps_word_ratio"] <= 1.0
    assert feat1["double_space_rate"] > 0.0
    assert feat1["mean_sentence_length"] > 0.0


def test_insufficient_text_excluded():
    assert get_text_sufficiency(50, min_sufficient=300, min_limited=100) == "insufficient"
    assert get_text_sufficiency(150, min_sufficient=300, min_limited=100) == "limited"
    assert get_text_sufficiency(350, min_sufficient=300, min_limited=100) == "sufficient"

    actor_docs = {
        1: "Word " * 350,
        2: "Word " * 150,
        3: "Short " * 20,
    }
    actor_words = {1: 350, 2: 150, 3: 20}
    actor_suff = {
        1: "sufficient",
        2: "limited",
        3: "insufficient",
    }
    feat = {k: {"mean_word_length": 4.0} for k in actor_docs}
    fw_feat = {k: {"fw_the": 0.05} for k in actor_docs}

    _, _, pair_records, run_metrics = compare_actors_stylometry(
        actor_docs=actor_docs,
        actor_word_counts=actor_words,
        actor_sufficiencies=actor_suff,
        actor_features=feat,
        actor_fw_features=fw_feat,
    )

    # Actor 3 must be excluded from pairwise comparison
    assert run_metrics["actors_compared"] == 2
    for p in pair_records:
        assert p["actor_a_id"] != 3 and p["actor_b_id"] != 3


def test_similarity_matrix_symmetric_and_within_unit_interval():
    from app.analysis.stylometry.similarity import cosine_sim

    v1 = np.array([0.1, 0.4, 0.8, 0.0])
    v2 = np.array([0.2, 0.3, 0.7, 0.1])

    s12 = cosine_sim(v1, v2)
    s21 = cosine_sim(v2, v1)

    assert abs(s12 - s21) < 1e-7
    assert 0.0 <= s12 <= 1.0


def test_identical_texts_score_near_one_on_every_component():
    doc = (
        "The quick brown fox jumps over the lazy dog. In the dark of the night, we observed the server. "
        "Every single package arrived safely with proper escrow confirmation and verification. "
    ) * 10
    words = tokenize_words(doc)
    sentences = tokenize_sentences(doc)

    feat_a, fw_a = extract_actor_features(doc, words, sentences, 1)
    feat_b, fw_b = extract_actor_features(doc, words, sentences, 1)

    actor_docs = {1: doc, 2: doc}
    actor_words = {1: len(words), 2: len(words)}
    actor_suff = {1: "sufficient", 2: "sufficient"}
    features = {1: feat_a, 2: feat_b}
    fw_features = {1: fw_a, 2: fw_b}

    _, _, pair_records, _ = compare_actors_stylometry(
        actor_docs=actor_docs,
        actor_word_counts=actor_words,
        actor_sufficiencies=actor_suff,
        actor_features=features,
        actor_fw_features=fw_features,
    )

    p = pair_records[0]
    assert p["char_ngram"] >= 0.99
    assert p["word_ngram"] >= 0.99
    assert p["function_words"] >= 0.99
    assert p["feature_vector"] >= 0.99
    assert p["overall"] >= 0.99


def test_hourly_jsd_similarity_identical_and_disjoint():
    # Identical profile
    prof_ident_a = {
        "hourly_distribution": [0.0] * 12 + [1.0 / 12.0] * 12,
        "daily_distribution": [1.0 / 7.0] * 7,
        "posts_per_active_day": 5.0,
    }
    prof_ident_b = {
        "hourly_distribution": [0.0] * 12 + [1.0 / 12.0] * 12,
        "daily_distribution": [1.0 / 7.0] * 7,
        "posts_per_active_day": 5.0,
    }
    sim_ident = compute_pair_behaviour_similarity(prof_ident_a, prof_ident_b)
    assert sim_ident["hourly"] == 1.0
    assert sim_ident["overall"] == 1.0

    # Disjoint profile (opposite 12 hours)
    prof_disjoint_a = {
        "hourly_distribution": [1.0 / 6.0] * 6 + [0.0] * 18,
        "daily_distribution": [1.0 / 7.0] * 7,
        "posts_per_active_day": 5.0,
    }
    prof_disjoint_b = {
        "hourly_distribution": [0.0] * 12 + [1.0 / 6.0] * 6 + [0.0] * 6,
        "daily_distribution": [1.0 / 7.0] * 7,
        "posts_per_active_day": 5.0,
    }
    sim_disjoint = compute_pair_behaviour_similarity(prof_disjoint_a, prof_disjoint_b)
    # Disjoint distributions yield high JSD, so 1 - JSD is near 0
    assert sim_disjoint["hourly"] < 0.20


def test_circular_smoothing_handles_hour_23_and_0():
    # Single impulse at hour 0
    bins = np.zeros(24, dtype=float)
    bins[0] = 1.0

    smoothed = circular_smooth(bins, [0.25, 0.5, 0.25])

    # Mass preserved
    assert abs(np.sum(smoothed) - 1.0) < 1e-6
    # Hour 0 keeps 0.5
    assert abs(smoothed[0] - 0.50) < 1e-6
    # Hour 23 wraps and gets 0.25
    assert abs(smoothed[23] - 0.25) < 1e-6
    # Hour 1 gets 0.25
    assert abs(smoothed[1] - 0.25) < 1e-6
    # All other hours remain 0
    assert np.all(smoothed[2:23] == 0.0)


def test_scoring_hand_computed_numbers():
    # A pair with crypto 0.95, style 0.6, behaviour 0.7 and weights .35/.25/.20
    # Expected: (0.3325 + 0.15 + 0.14) / 0.8 = 0.778125, contributions sum to it
    weights = {
        "cryptographic": 0.35,
        "infrastructure": 0.20,
        "stylometric": 0.25,
        "behavioural": 0.20,
    }
    supporting_by_dim = {
        "cryptographic": [0.95],
        "stylometric": [0.60],
        "behavioural": [0.70],
    }
    dim_avail = {
        "cryptographic": {"has_data": True},
        "infrastructure": {"has_data": True},
        "stylometric": {"is_sufficient": True},
        "behavioural": {"is_sufficient": True},
    }

    res = calculate_pair_score(
        actor_a_id=1,
        actor_b_id=2,
        supporting_by_dimension=supporting_by_dim,
        dimension_availability=dim_avail,
        weights=weights,
        thresholds={"scoring": {"contradiction_z": 1.5, "contradiction_penalty": 0.5}},
    )

    expected_combined = (0.35 * 0.95 + 0.25 * 0.60 + 0.20 * 0.70) / 0.80
    assert abs(res["combined_score"] - round(expected_combined, 4)) < 1e-4

    # Contributions sum to pre-penalty combined
    contrib_sum = sum(c["contribution"] for c in res["contributions"].values())
    assert abs(contrib_sum - round(expected_combined, 4)) < 1e-4


def test_positive_only_dimension_without_match_excluded_from_denominator():
    weights = {
        "cryptographic": 0.35,
        "infrastructure": 0.20,
        "stylometric": 0.25,
        "behavioural": 0.20,
    }
    supporting_by_dim = {
        "cryptographic": [0.90],
    }
    dim_avail = {
        "cryptographic": {"has_data": True},
        "infrastructure": {"has_data": True},  # has data but no match
        "stylometric": {"is_sufficient": False, "reason": "insufficient_text"},
        "behavioural": {"is_sufficient": False, "reason": "insufficient_timestamps"},
    }

    res = calculate_pair_score(
        actor_a_id=1,
        actor_b_id=2,
        supporting_by_dimension=supporting_by_dim,
        dimension_availability=dim_avail,
        weights=weights,
        thresholds={},
    )

    # Denominator only includes cryptographic (0.35). Score = 0.90 * 0.35 / 0.35 = 0.90
    assert abs(res["combined_score"] - 0.90) < 1e-4
    assert res["dimension_scores"]["infrastructure"]["state"] == "no_match"
    assert not res["dimension_scores"]["infrastructure"]["counted"]


def test_contradiction_penalty_and_single_dimension_cap():
    weights = {"cryptographic": 0.35, "infrastructure": 0.20, "stylometric": 0.25, "behavioural": 0.20}

    # Case A: Single dimension capped at moderate unless crypto >= 0.90
    res_single_weak = calculate_pair_score(
        actor_a_id=1,
        actor_b_id=2,
        supporting_by_dimension={"cryptographic": [0.85]},
        dimension_availability={
            "cryptographic": {"has_data": True},
            "infrastructure": {"has_data": False},
            "stylometric": {"is_sufficient": False},
            "behavioural": {"is_sufficient": False},
        },
        weights=weights,
        thresholds={"scoring": {"levels": {"strong": 0.70, "moderate": 0.45, "weak": 0.25}}},
    )
    # Crypto 0.85 >= 0.70 would be strong, but capped at moderate
    assert res_single_weak["level"] == "moderate"

    res_single_strong = calculate_pair_score(
        actor_a_id=1,
        actor_b_id=2,
        supporting_by_dimension={"cryptographic": [0.95]},
        dimension_availability={
            "cryptographic": {"has_data": True},
            "infrastructure": {"has_data": False},
            "stylometric": {"is_sufficient": False},
            "behavioural": {"is_sufficient": False},
        },
        weights=weights,
        thresholds={"scoring": {"levels": {"strong": 0.70, "moderate": 0.45, "weak": 0.25}}},
    )
    # Crypto 0.95 >= 0.90 allows strong
    assert res_single_strong["level"] == "strong"

    # Case B: Contradiction penalty
    res_contra = calculate_pair_score(
        actor_a_id=1,
        actor_b_id=2,
        supporting_by_dimension={"cryptographic": [0.95], "stylometric": [0.70]},
        dimension_availability={
            "cryptographic": {"has_data": True},
            "infrastructure": {"has_data": False},
            "stylometric": {"is_sufficient": True},
            "behavioural": {"is_sufficient": True},
        },
        weights=weights,
        thresholds={"scoring": {"contradiction_z": 1.5, "contradiction_penalty": 0.5}},
        behaviour_z=-2.5,  # Contradiction in behavior!
    )
    # Contradiction generated
    assert len(res_contra["contradictions"]) > 0
    # Score penalized: pre_penalty is penalized by 1 - 0.5 * contra_strength
    assert res_contra["combined_score"] < 0.80


def test_noisy_or_logic():
    assert noisy_or([]) == 0.0
    assert noisy_or([0.8]) == 0.8
    assert abs(noisy_or([0.5, 0.5]) - 0.75) < 1e-6
    assert abs(noisy_or([0.5, 0.5, 0.5]) - 0.875) < 1e-6


def test_config_upgrade_keeps_exactly_one_active_row(db_session):
    # Ensure starting clean
    cfg1 = get_or_create_default(db_session)
    assert cfg1.is_active is True

    # Mutate cfg1 to simulate an older Phase 7 config lacking Phase 8 keys
    cfg1.thresholds = {"full_strength_max_actors": 3}
    db_session.commit()

    # Re-running get_or_create_default must upgrade and keep exactly one active
    cfg2 = get_or_create_default(db_session)
    assert cfg2.version == cfg1.version + 1
    assert cfg2.is_active is True
    assert "stylometry" in cfg2.thresholds
    assert "behaviour" in cfg2.thresholds
    assert "scoring" in cfg2.thresholds

    # Verify in DB there is exactly one active row
    from sqlalchemy import select
    active_rows = db_session.scalars(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True))
    ).all()
    assert len(active_rows) == 1

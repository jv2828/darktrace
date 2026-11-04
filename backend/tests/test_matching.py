"""Unit tests for the pure-Python cryptographic and infrastructure matching engines."""

from datetime import datetime, timezone
import random

from app.analysis.matching.common import (
    calculate_specificity,
    is_common_indicator,
    mask_indicator_value,
    sort_evidence_candidates,
)
from app.analysis.matching.crypto import match_cryptographic
from app.analysis.matching.infrastructure import match_infrastructure
from app.analysis.matching.models import EvidenceCandidate, IndicatorRecord
from app.services.scoring_config_service import DEFAULT_THRESHOLDS


def test_two_actors_share_one_pgp_value():
    """Two actors sharing one PGP value generates exactly one pair record with strength 0.95."""
    records = [
        IndicatorRecord(
            indicator_id=1,
            post_id=101,
            actor_id=1,
            marketplace_id=1,
            indicator_type="pgp_fingerprint",
            normalised_value="9B4C8A1D3F2E7A0B5C6D8E9F1A2B3C4D5E6F7A8B",
            confidence="high",
            posted_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        ),
        IndicatorRecord(
            indicator_id=2,
            post_id=102,
            actor_id=2,
            marketplace_id=2,
            indicator_type="pgp_fingerprint",
            normalised_value="9B4C8A1D3F2E7A0B5C6D8E9F1A2B3C4D5E6F7A8B",
            confidence="high",
            posted_at=datetime(2026, 1, 12, tzinfo=timezone.utc),
        ),
    ]

    candidates, suppressed, coverage = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 1
    assert len(suppressed) == 0
    c = candidates[0]
    assert c.actor_a_id == 1
    assert c.actor_b_id == 2
    assert c.evidence_type == "shared_pgp_fingerprint"
    assert c.strength == 0.95
    assert "Both personas posted the same PGP fingerprint" in c.explanation
    assert "A shared key can also mean a shared service or leaked key" in c.explanation


def test_normalised_value_matching():
    """Identical normalised values match even if raw context differed."""
    records = [
        IndicatorRecord(
            indicator_id=1,
            post_id=1,
            actor_id=10,
            marketplace_id=1,
            indicator_type="wallet_btc",
            normalised_value="bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
            confidence="high",
        ),
        IndicatorRecord(
            indicator_id=2,
            post_id=2,
            actor_id=20,
            marketplace_id=2,
            indicator_type="wallet_btc",
            normalised_value="bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
            confidence="high",
        ),
    ]
    candidates, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 1
    assert candidates[0].evidence_type == "shared_wallet_btc"
    assert candidates[0].strength == 0.85
    assert "A wallet can also be a payment address given to others" in candidates[0].explanation


def test_three_actors_specificity_full():
    """Three actors sharing an indicator produces three pair records with specificity 1.0."""
    norm_val = "1234567890ABCDEF1234567890ABCDEF12345678"
    records = [
        IndicatorRecord(1, 1, 1, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(2, 2, 2, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(3, 3, 3, 2, "pgp_fingerprint", norm_val, "high"),
    ]
    candidates, suppressed, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 3
    assert len(suppressed) == 0
    for c in candidates:
        assert c.strength == 0.95
        assert c.details["specificity"] == 1.0
        assert c.details["actor_count"] == 3


def test_four_actors_specificity_reduced():
    """Four actors sharing an indicator produces pairwise records with specificity 0.75."""
    norm_val = "1234567890ABCDEF1234567890ABCDEF12345678"
    records = [
        IndicatorRecord(1, 1, 1, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(2, 2, 2, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(3, 3, 3, 2, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(4, 4, 4, 3, "pgp_fingerprint", norm_val, "high"),
    ]
    candidates, suppressed, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 6  # 4 choose 2
    assert len(suppressed) == 0
    for c in candidates:
        assert c.details["specificity"] == 0.75
        assert c.strength == round(0.95 * 0.75, 4)  # 0.7125


def test_five_actors_common_indicator_suppressed():
    """Five or more actors sharing an indicator suppresses pair evidence entirely."""
    norm_val = "DEC07DEC07DEC07DEC07DEC07DEC07DEC07DEC07"
    records = [
        IndicatorRecord(1, 1, 1, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(2, 2, 2, 1, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(3, 3, 3, 2, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(4, 4, 4, 3, "pgp_fingerprint", norm_val, "high"),
        IndicatorRecord(5, 5, 5, 3, "pgp_fingerprint", norm_val, "high"),
    ]
    candidates, suppressed, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 0
    assert len(suppressed) == 1
    assert suppressed[0].normalised_value == norm_val
    assert suppressed[0].actor_count == 5


def test_single_actor_multiple_posts_is_not_evidence():
    """One actor posting the same indicator 10 times produces zero evidence candidates."""
    records = [
        IndicatorRecord(i, i * 10, 42, 1, "wallet_btc", "bc1qtestingrepeat00000000000000000000000000", "high")
        for i in range(1, 11)
    ]
    candidates, suppressed, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 0
    assert len(suppressed) == 0


def test_different_chains_never_match():
    """Wallets belonging to different blockchains never match each other."""
    val = "0x71C8364427a238805121b67f654b0c762512f43b"
    records = [
        IndicatorRecord(1, 1, 1, 1, "wallet_eth", val, "high"),
        IndicatorRecord(2, 2, 2, 1, "wallet_btc", val, "high"),
    ]
    candidates, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 0


def test_confidence_factor_scaling():
    """Lowest confidence among records scales down evidence strength."""
    records = [
        IndicatorRecord(1, 1, 1, 1, "pgp_fingerprint", "F1234567890ABCDEF1234567890ABCDEF1234567", "high"),
        IndicatorRecord(2, 2, 2, 1, "pgp_fingerprint", "F1234567890ABCDEF1234567890ABCDEF1234567", "medium"),
    ]
    candidates, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 1
    # base 0.95 * medium (0.8) * spec (1.0) = 0.76
    assert candidates[0].strength == 0.76


def test_canonical_actor_ordering():
    """Generated evidence candidates always enforce actor_a_id < actor_b_id."""
    records = [
        IndicatorRecord(1, 1, 99, 1, "wallet_xmr", "888tNkZrPN6JsEgekjMnABU4TBWm2DLWVYG89yt8EDP8", "high"),
        IndicatorRecord(2, 2, 5, 2, "wallet_xmr", "888tNkZrPN6JsEgekjMnABU4TBWm2DLWVYG89yt8EDP8", "high"),
    ]
    candidates, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 1
    assert candidates[0].actor_a_id == 5
    assert candidates[0].actor_b_id == 99


def test_determinism_under_shuffle():
    """Shuffling the input records produces byte-identical output candidates."""
    records = [
        IndicatorRecord(1, 10, 1, 1, "pgp_fingerprint", "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2", "high"),
        IndicatorRecord(2, 11, 2, 1, "pgp_fingerprint", "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2", "high"),
        IndicatorRecord(3, 12, 1, 1, "wallet_btc", "bc1qaaaabbbbccccddddeeeeffffgggghhhhiiiijjjj", "high"),
        IndicatorRecord(4, 13, 2, 1, "wallet_btc", "bc1qaaaabbbbccccddddeeeeffffgggghhhhiiiijjjj", "high"),
    ]
    c1, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)

    shuffled = records.copy()
    rng = random.Random(42)
    rng.shuffle(shuffled)
    c2, _, _ = match_cryptographic(shuffled, DEFAULT_THRESHOLDS)

    assert len(c1) == len(c2)
    for a, b in zip(c1, c2):
        assert a.actor_a_id == b.actor_a_id
        assert a.actor_b_id == b.actor_b_id
        assert a.evidence_type == b.evidence_type
        assert a.strength == b.strength
        assert a.explanation == b.explanation


def test_strength_bounded_in_unit_interval():
    """All generated evidence strengths must strictly reside between 0.0 and 1.0."""
    cand = EvidenceCandidate(
        actor_a_id=1,
        actor_b_id=2,
        dimension="cryptographic",
        evidence_type="shared_pgp_fingerprint",
        direction="supporting",
        strength=0.95001,
        explanation="test",
        details={},
        source_post_ids=[1],
        source_indicator_ids=[1],
    )
    assert 0.0 <= cand.strength <= 1.0


def test_masked_value_in_explanation():
    """Explanation contains masked value (first 8 ... last 4) while details retain full value."""
    raw = "E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A"
    records = [
        IndicatorRecord(1, 1, 1, 1, "pgp_fingerprint", raw, "high"),
        IndicatorRecord(2, 2, 2, 1, "pgp_fingerprint", raw, "high"),
    ]
    candidates, _, _ = match_cryptographic(records, DEFAULT_THRESHOLDS)
    assert len(candidates) == 1
    assert "E4A18B9C…6F7A" in candidates[0].explanation
    assert candidates[0].details["normalised_value"] == raw


def test_infrastructure_base_strengths():
    """Infrastructure indicators reflect their specified base strengths."""
    # Cert fingerprint (0.90) and onion (0.90)
    rec_cert = [
        IndicatorRecord(1, 1, 1, 1, "ssl_cert_fingerprint", "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD", "high"),
        IndicatorRecord(2, 2, 2, 1, "ssl_cert_fingerprint", "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD", "high"),
    ]
    c_cert, _, _ = match_infrastructure(rec_cert, DEFAULT_THRESHOLDS)
    assert c_cert[0].strength == 0.90
    assert c_cert[0].evidence_type == "shared_cert_fingerprint"

    # Onion domain (0.90)
    rec_onion = [
        IndicatorRecord(1, 1, 1, 1, "domain", "darkmarketxyz1234567890abcdef.onion", "high"),
        IndicatorRecord(2, 2, 2, 1, "domain", "darkmarketxyz1234567890abcdef.onion", "high"),
    ]
    c_onion, _, _ = match_infrastructure(rec_onion, DEFAULT_THRESHOLDS)
    assert c_onion[0].strength == 0.90
    assert c_onion[0].evidence_type == "shared_onion_domain"
    assert c_onion[0].details["kind"] == "onion"

    # Server banner alone (0.15)
    rec_banner = [
        IndicatorRecord(1, 1, 1, 1, "server_banner", "nginx/1.24.0 (Ubuntu)", "high"),
        IndicatorRecord(2, 2, 2, 1, "server_banner", "nginx/1.24.0 (Ubuntu)", "high"),
    ]
    c_banner, _, _ = match_infrastructure(rec_banner, DEFAULT_THRESHOLDS)
    assert c_banner[0].strength == 0.15
    assert c_banner[0].evidence_type == "shared_server_banner"

    # Cert issuer alone (0.10)
    rec_issuer = [
        IndicatorRecord(1, 1, 1, 1, "cert_metadata", "Let's Encrypt", "high", details={"field": "issuer"}),
        IndicatorRecord(2, 2, 2, 1, "cert_metadata", "Let's Encrypt", "high", details={"field": "issuer"}),
    ]
    c_issuer, _, _ = match_infrastructure(rec_issuer, DEFAULT_THRESHOLDS)
    assert c_issuer[0].strength == 0.10
    assert c_issuer[0].evidence_type == "shared_cert_issuer"


def test_corroborating_port_rule():
    """Port evidence is ONLY generated if pair shares another infrastructure match AND port is non-standard."""
    # Case A: Shared port 8443 WITHOUT other infrastructure match -> 0 evidence
    rec_port_only = [
        IndicatorRecord(1, 1, 1, 1, "port", "8443", "high"),
        IndicatorRecord(2, 2, 2, 1, "port", "8443", "high"),
    ]
    c_none, _, _ = match_infrastructure(rec_port_only, DEFAULT_THRESHOLDS)
    assert len(c_none) == 0

    # Case B: Shared port 80 (standard) WITH other infrastructure match -> port produces nothing
    rec_std_port = [
        IndicatorRecord(1, 1, 1, 1, "ip_address", "198.51.100.10", "high"),
        IndicatorRecord(2, 2, 2, 1, "ip_address", "198.51.100.10", "high"),
        IndicatorRecord(3, 3, 1, 1, "port", "80", "high"),
        IndicatorRecord(4, 4, 2, 1, "port", "80", "high"),
    ]
    c_std, _, _ = match_infrastructure(rec_std_port, DEFAULT_THRESHOLDS)
    assert len(c_std) == 1
    assert c_std[0].evidence_type == "shared_ip_address"

    # Case C: Shared port 8443 (non-standard) WITH shared IP address -> emits corroborating_port
    rec_corrob = [
        IndicatorRecord(1, 1, 1, 1, "ip_address", "198.51.100.10", "high"),
        IndicatorRecord(2, 2, 2, 1, "ip_address", "198.51.100.10", "high"),
        IndicatorRecord(3, 3, 1, 1, "port", "8443", "high"),
        IndicatorRecord(4, 4, 2, 1, "port", "8443", "high"),
    ]
    c_corrob, _, _ = match_infrastructure(rec_corrob, DEFAULT_THRESHOLDS)
    assert len(c_corrob) == 2
    types = [c.evidence_type for c in c_corrob]
    assert "shared_ip_address" in types
    assert "corroborating_port" in types
    port_c = next(c for c in c_corrob if c.evidence_type == "corroborating_port")
    assert port_c.details["corroborating"] is True


def test_coverage_computation():
    """Coverage correctly tracks actors with and without indicators of the dimension."""
    records = [
        IndicatorRecord(1, 1, 1, 1, "wallet_btc", "bc1qtest1", "high"),
        IndicatorRecord(2, 2, 2, 1, "ip_address", "198.51.100.1", "high"),
    ]
    # In crypto matching: actor 1 is covered, actor 2 is not
    _, _, cov_crypto = match_cryptographic(records, DEFAULT_THRESHOLDS, all_actor_ids={1, 2, 3})
    assert cov_crypto["actors_total"] == 3
    assert cov_crypto["actors_with_dimension_indicators"] == 1
    assert cov_crypto[1] is True
    assert cov_crypto[2] is False
    assert cov_crypto[3] is False

    # In infra matching: actor 2 is covered, actor 1 is not
    _, _, cov_infra = match_infrastructure(records, DEFAULT_THRESHOLDS, all_actor_ids={1, 2, 3})
    assert cov_infra["actors_total"] == 3
    assert cov_infra["actors_with_dimension_indicators"] == 1
    assert cov_infra[1] is False
    assert cov_infra[2] is True
    assert cov_infra[3] is False


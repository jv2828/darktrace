"""Tests for synthetic data generator determinism, safety, and ground truth integrity."""

from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import pytest

from tools.generate_sample_data import build_alpha_dataset, build_beta_dataset

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATASETS_DIR = BACKEND_DIR / "datasets"

RFC5737_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
]

ALLOWED_SAMPLE_POST_KEYS = {
    "marketplace",
    "username",
    "timestamp",
    "content",
    "source_reference",
    "structured_indicators",
}


def test_generator_determinism():
    """Generating Alpha and Beta datasets twice produces byte-identical output."""
    alpha1_sample, alpha1_truth = build_alpha_dataset()
    alpha2_sample, alpha2_truth = build_alpha_dataset()

    assert json.dumps(alpha1_sample, sort_keys=True) == json.dumps(alpha2_sample, sort_keys=True)
    assert json.dumps(alpha1_truth, sort_keys=True) == json.dumps(alpha2_truth, sort_keys=True)

    beta1_sample, beta1_truth = build_beta_dataset()
    beta2_sample, beta2_truth = build_beta_dataset()

    assert json.dumps(beta1_sample, sort_keys=True) == json.dumps(beta2_sample, sort_keys=True)
    assert json.dumps(beta1_truth, sort_keys=True) == json.dumps(beta2_truth, sort_keys=True)


def test_ground_truth_pair_coverage_and_completeness():
    """Ground truth covers every persona pair exactly once and matches all sample personas."""
    for dataset_func, name in [(build_alpha_dataset, "Alpha"), (build_beta_dataset, "Beta")]:
        sample, truth = dataset_func()

        sample_personas = {
            (p["marketplace"], p["username"]) for p in sample["posts"]
        }

        # Check all sample personas exist in truth operators
        truth_personas = set()
        for op in truth["operators"]:
            for persona in op["personas"]:
                truth_personas.add((persona["marketplace"], persona["username"]))

        assert sample_personas == truth_personas, f"{name}: Mismatch between sample and truth personas"

        n = len(truth_personas)
        expected_pairs_count = n * (n - 1) // 2

        pairs = truth["pairs"]
        assert len(pairs) == expected_pairs_count, f"{name}: Expected {expected_pairs_count} pairs, got {len(pairs)}"

        # Verify each pair is unique and covers distinct personas
        seen_pairs = set()
        for pair in pairs:
            p_a = (pair["a"]["marketplace"], pair["a"]["username"])
            p_b = (pair["b"]["marketplace"], pair["b"]["username"])
            assert p_a != p_b, f"{name}: Self-comparison pair found"

            canonical = tuple(sorted([p_a, p_b]))
            assert canonical not in seen_pairs, f"{name}: Duplicate pair found: {canonical}"
            seen_pairs.add(canonical)


def test_rfc5737_and_domain_safety():
    """All IP addresses are strictly within RFC 5737 and domains are strictly safe."""
    for dataset_func in [build_alpha_dataset, build_beta_dataset]:
        sample, _ = dataset_func()
        for post in sample["posts"]:
            structured = post.get("structured_indicators") or {}

            # Check IP address
            ip_str = structured.get("ip_address")
            if ip_str:
                ip_obj = ipaddress.ip_address(ip_str)
                in_rfc = any(ip_obj in net for net in RFC5737_NETWORKS)
                assert in_rfc, f"Disallowed IP address found: {ip_str}"

            # Check domain
            domain_str = structured.get("domain")
            if domain_str:
                is_safe_domain = (
                    domain_str.endswith(".example")
                    or domain_str.endswith(".invalid")
                    or (domain_str.startswith("fictional") and domain_str.endswith(".onion"))
                )
                assert is_safe_domain, f"Disallowed domain found: {domain_str}"


def test_sample_hygiene_no_ground_truth_leakage():
    """Sample files contain ONLY whitelisted keys with zero operator/cluster annotations."""
    for dataset_func in [build_alpha_dataset, build_beta_dataset]:
        sample, _ = dataset_func()
        assert set(sample.keys()) == {
            "key",
            "name",
            "description",
            "version",
            "is_fictional",
            "generator_seed",
            "posts",
        }

        for post in sample["posts"]:
            post_keys = set(post.keys())
            extra_keys = post_keys - ALLOWED_SAMPLE_POST_KEYS
            assert not extra_keys, f"Forbidden keys in sample post: {extra_keys}"

            # Ensure no operator leakage in content or references
            assert "op_" not in post.get("source_reference", "")
            assert "operator" not in post.get("source_reference", "")


def test_positive_and_negative_pair_indicator_fidelity():
    """Positive pairs in truth share declared indicators; negative pairs do not."""
    alpha_sample, alpha_truth = build_alpha_dataset()

    # Collect indicators per persona
    persona_pgp = {}
    persona_wallets = {}
    for post in alpha_sample["posts"]:
        persona = (post["marketplace"], post["username"])
        structured = post.get("structured_indicators") or {}
        if "pgp_fingerprint" in structured:
            persona_pgp.setdefault(persona, set()).add(structured["pgp_fingerprint"])
        if "wallet" in structured:
            persona_wallets.setdefault(persona, set()).add(structured["wallet"])

    for pair in alpha_truth["pairs"]:
        p_a = (pair["a"]["marketplace"], pair["a"]["username"])
        p_b = (pair["b"]["marketplace"], pair["b"]["username"])
        label = pair["label"]
        case_type = pair["case_type"]

        if case_type == "strong_positive":
            # Must share PGP and wallet
            shared_pgp = persona_pgp.get(p_a, set()) & persona_pgp.get(p_b, set())
            shared_wallet = persona_wallets.get(p_a, set()) & persona_wallets.get(p_b, set())
            assert len(shared_pgp) > 0, f"Strong positive pair {p_a} and {p_b} missing shared PGP"
            assert len(shared_wallet) > 0, f"Strong positive pair {p_a} and {p_b} missing shared wallet"

        elif label == "different_operator" and case_type == "control":
            # Must NOT share PGP or wallet
            shared_pgp = persona_pgp.get(p_a, set()) & persona_pgp.get(p_b, set())
            shared_wallet = persona_wallets.get(p_a, set()) & persona_wallets.get(p_b, set())
            assert len(shared_pgp) == 0, f"Control negative pair {p_a} and {p_b} unexpectedly shares PGP"
            assert len(shared_wallet) == 0, f"Control negative pair {p_a} and {p_b} unexpectedly shares wallet"


def test_operator_active_window_statistical_fidelity():
    """Posts for each operator fall strictly inside their declared diurnal active window."""
    sample, truth = build_alpha_dataset()

    # Map persona to operator active window
    persona_to_window = {}
    for op in truth["operators"]:
        desc = op["description"]
        for p in op["personas"]:
            key = (p["marketplace"], p["username"])
            if op["operator_id"] == "op_alpha_1":
                persona_to_window[key] = (8, 15)
            elif op["operator_id"] == "op_alpha_2":
                persona_to_window[key] = (22, 4)
            elif op["operator_id"] == "op_alpha_3":
                persona_to_window[key] = (6, 12)
            elif op["operator_id"] in ["op_alpha_4", "op_alpha_5"]:
                persona_to_window[key] = (13, 19)
            elif op["operator_id"] == "op_alpha_6":
                persona_to_window[key] = (10, 17)

    for post in sample["posts"]:
        ts_str = post.get("timestamp")
        if not ts_str:
            continue
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        persona = (post["marketplace"], post["username"])
        if persona in persona_to_window:
            start_h, end_h = persona_to_window[persona]
            post_h = dt.hour
            if start_h <= end_h:
                in_window = start_h <= post_h <= end_h
            else:
                in_window = post_h >= start_h or post_h <= end_h
            assert in_window, f"Post at hour {post_h} outside window {start_h}-{end_h} for {persona}"


def test_beta_contradictory_and_decoy_cases_exist():
    """Beta dataset contains contradictory cryptographic evidence and common indicator decoys."""
    _, truth_beta = build_beta_dataset()

    case_types = {pair["case_type"] for pair in truth_beta["pairs"]}
    assert "contradictory_crypto" in case_types, "Beta truth missing 'contradictory_crypto' case"
    assert "common_indicator_decoy" in case_types, "Beta truth missing 'common_indicator_decoy' case"
    assert "short_text" in case_types, "Beta truth missing 'short_text' case"
    assert "missing_timestamps" in case_types, "Beta truth missing 'missing_timestamps' case"


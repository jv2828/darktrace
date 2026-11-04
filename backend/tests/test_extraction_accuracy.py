"""Accuracy evaluation of indicator extraction against deterministic ground-truth manifests."""

import hashlib
import json
from pathlib import Path
import pytest

from app.analysis.extraction import extract_all
from app.core.config import ROOT_DIR


def evaluate_dataset_accuracy(dataset_name: str):
    """Evaluate extraction accuracy against indicator_manifest for a dataset."""
    sample_file = ROOT_DIR / "backend" / "datasets" / "sample" / f"{dataset_name}.json"
    truth_file = ROOT_DIR / "backend" / "datasets" / "ground_truth" / f"{dataset_name}_truth.json"

    with open(sample_file, "r", encoding="utf-8") as f:
        sample_data = json.load(f)
    with open(truth_file, "r", encoding="utf-8") as f:
        truth_data = json.load(f)

    manifest = truth_data.get("indicator_manifest", [])
    manifest_by_key = {
        (
            m["timestamp"],
            m["marketplace"],
            m["username"],
            m["content_hash"],
        ): m["indicators"]
        for m in manifest
    }

    tp_by_type = {}
    fp_by_type = {}
    fn_by_type = {}
    mismatches = []

    for post in sample_data["posts"]:
        content = post["content"]
        c_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        key = (post["timestamp"], post["marketplace"], post["username"], c_hash)

        planted_list = manifest_by_key.get(key, [])
        expected_set = {(p["indicator_type"], p["normalised_value"]) for p in planted_list}

        res = extract_all(content, structured=post.get("structured_indicators"))
        extracted_set = {(ind.indicator_type, ind.normalised_value) for ind in res.indicators}

        # True Positives & False Negatives
        for item in expected_set:
            t = item[0]
            if item in extracted_set:
                tp_by_type[t] = tp_by_type.get(t, 0) + 1
            else:
                fn_by_type[t] = fn_by_type.get(t, 0) + 1
                mismatches.append(f"FN in post {key}: missing expected {item}")

        # False Positives
        for item in extracted_set:
            t = item[0]
            if item not in expected_set:
                fp_by_type[t] = fp_by_type.get(t, 0) + 1
                mismatches.append(f"FP in post {key}: unexpected {item}")

    all_types = sorted(set(list(tp_by_type.keys()) + list(fn_by_type.keys())))

    print(f"\n==================== {dataset_name.upper()} ACCURACY EVALUATION ====================")
    print(f"{'Indicator Type':25s} | {'TP':>4s} | {'FP':>4s} | {'FN':>4s} | {'Precision':>9s} | {'Recall':>9s}")
    print("-" * 70)

    for t in all_types:
        tp = tp_by_type.get(t, 0)
        fp = fp_by_type.get(t, 0)
        fn = fn_by_type.get(t, 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        print(f"{t:25s} | {tp:4d} | {fp:4d} | {fn:4d} | {precision:9.4f} | {recall:9.4f}")
        assert precision >= 0.98, f"Precision below 0.98 for {t} in {dataset_name}: {precision}"
        assert recall >= 0.98, f"Recall below 0.98 for {t} in {dataset_name}: {recall}"

    if mismatches:
        print("\nMismatches observed:")
        for m in mismatches[:20]:
            print(" ", m)


def test_alpha_extraction_accuracy():
    """Verify Alpha benchmark achieves >= 0.98 precision and recall per type."""
    evaluate_dataset_accuracy("alpha")


def test_beta_extraction_accuracy():
    """Verify Beta benchmark achieves >= 0.98 precision and recall per type."""
    evaluate_dataset_accuracy("beta")


def test_cryptographic_linkage_scientific_meaning():
    """Verify that same_operator pairs with cryptographic dimensions share extracted crypto keys."""
    sample_file = ROOT_DIR / "backend" / "datasets" / "sample" / "beta.json"
    truth_file = ROOT_DIR / "backend" / "datasets" / "ground_truth" / "beta_truth.json"

    with open(sample_file, "r", encoding="utf-8") as f:
        sample_data = json.load(f)
    with open(truth_file, "r", encoding="utf-8") as f:
        truth_data = json.load(f)

    # Collect extracted crypto indicators per persona (mkt, username)
    persona_crypto = {}
    for post in sample_data["posts"]:
        mkt = post["marketplace"]
        user = post["username"]
        key = (mkt, user)
        if key not in persona_crypto:
            persona_crypto[key] = set()

        res = extract_all(post["content"], structured=post.get("structured_indicators"))
        for ind in res.indicators:
            if ind.indicator_type in ("pgp_fingerprint", "wallet_btc", "wallet_eth", "wallet_xmr"):
                persona_crypto[key].add(ind.normalised_value)

    decoy_pgp = "DEC07DEC07DEC07DEC07DEC07DEC07DEC07DEC07"
    decoy_wallet = "bc1qdecoymarketescrow00000000000000000000"
    decoy_values = {decoy_pgp, decoy_wallet}

    decoy_observed_personas = set()

    for pair in truth_data["pairs"]:
        p_a = (pair["a"]["marketplace"], pair["a"]["username"])
        p_b = (pair["b"]["marketplace"], pair["b"]["username"])
        shared_dims = pair.get("shared_dimensions", [])
        label = pair.get("label")

        crypto_a = persona_crypto.get(p_a, set())
        crypto_b = persona_crypto.get(p_b, set())

        # Track decoy appearances
        if decoy_values & crypto_a:
            decoy_observed_personas.add(p_a)
        if decoy_values & crypto_b:
            decoy_observed_personas.add(p_b)

        if label == "same_operator" and "cryptographic" in shared_dims:
            # Personas under same operator with cryptographic link MUST share keys
            intersection = crypto_a & crypto_b
            # Exclude decoys from verification of true link
            real_intersection = intersection - decoy_values
            assert len(real_intersection) > 0, (
                f"Expected shared crypto between same_operator personas {p_a} and {p_b}, got none."
            )

        elif label == "different_operator" and "cryptographic" not in shared_dims:
            # Personas under different operators with no shared crypto MUST NOT intersect (except decoys)
            intersection = crypto_a & crypto_b
            non_decoy_intersection = intersection - decoy_values
            assert len(non_decoy_intersection) == 0, (
                f"Unexpected crypto collision between different_operator personas {p_a} and {p_b}: {non_decoy_intersection}"
            )

    # Assert decoy value appears across multiple unrelated personas
    assert len(decoy_observed_personas) >= 3, (
        f"Common decoy values should appear across multiple personas, got {len(decoy_observed_personas)}"
    )


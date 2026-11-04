"""Ground-truth evaluation of cryptographic and infrastructure matching against Alpha and Beta benchmarks."""

import json
from pathlib import Path
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.evidence_record import EvidenceRecord
from app.models.investigation import Investigation, InvestigationStatus
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStage, PipelineStageRun
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.ingestion_service import load_sample_to_investigation
from app.services.pipeline_service import create_pipeline_run, run_pipeline_job

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets" / "ground_truth"


def _format_table(title: str, headers: list, rows: list) -> str:
    """Format an ASCII alignment table for terminal output."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"

    lines = [f"\n{title}", sep, header_line, sep]
    for row in rows:
        r_line = "| " + " | ".join(f"{str(v):<{col_widths[i]}}" for i, v in enumerate(row)) + " |"
        lines.append(r_line)
    lines.append(sep)
    return "\n".join(lines)


@pytest.mark.parametrize("dataset_key", ["alpha", "beta"])
def test_ground_truth_accuracy(db_session, dataset_key):
    """Verify cryptographic and infrastructure matching achieve >=0.95 precision and recall on ground truth."""
    truth_file = DATASETS_DIR / f"{dataset_key}_truth.json"
    assert truth_file.exists(), f"Ground truth file missing: {truth_file}"

    with open(truth_file, "r", encoding="utf-8") as f:
        truth = json.load(f)

    # Provision user and investigation
    user = User(
        email=f"gt_{dataset_key}@darktrace.test",
        username=f"gt_{dataset_key}_user",
        full_name="Ground Truth Evaluator",
        role=UserRole.ADMIN,
        password_hash=hash_password("Pass1234!"),
    )
    db_session.add(user)
    db_session.commit()

    inv = Investigation(
        title=f"Benchmark Evaluation: {dataset_key.upper()}",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()

    # Load dataset sample and run pipeline
    load_sample_to_investigation(db_session, user, inv.id, dataset_key)
    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id, session=db_session)

    db_session.refresh(run)
    assert run.status == PipelineRunStatus.COMPLETED

    # Build actor mapping: actor_id -> (username, marketplace_name)
    actors = (
        db_session.execute(
            select(ThreatActor).join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        )
        .scalars()
        .all()
    )
    actor_map = {a.id: (a.username, a.marketplace.name) for a in actors}

    # Query all evidence records produced
    evidence_records = (
        db_session.execute(
            select(EvidenceRecord).where(EvidenceRecord.pipeline_run_id == run.id)
        )
        .scalars()
        .all()
    )

    crypto_evidence = {}
    infra_evidence = {}
    all_crypto_evidence = {}

    for ev in evidence_records:
        a_key = actor_map[ev.actor_a_id]
        b_key = actor_map[ev.actor_b_id]
        pair_key = (min(a_key, b_key), max(a_key, b_key))
        strength_val = float(ev.strength)

        if ev.dimension.value == "cryptographic":
            all_crypto_evidence[pair_key] = max(
                all_crypto_evidence.get(pair_key, 0.0), strength_val
            )
            if strength_val >= 0.30:
                crypto_evidence[pair_key] = max(
                    crypto_evidence.get(pair_key, 0.0), strength_val
                )
        elif ev.dimension.value == "infrastructure":
            if strength_val >= 0.30:
                infra_evidence[pair_key] = max(
                    infra_evidence.get(pair_key, 0.0), strength_val
                )

    # 1. Evaluate Cryptographic Dimension
    tp_c, fp_c, fn_c = 0, 0, 0
    misses_c = []
    for p in truth["pairs"]:
        k1 = (p["a"]["username"], p["a"]["marketplace"])
        k2 = (p["b"]["username"], p["b"]["marketplace"])
        pair_key = (min(k1, k2), max(k1, k2))

        has_truth = "cryptographic" in p.get("shared_dimensions", [])
        has_pred = pair_key in crypto_evidence

        if has_truth and has_pred:
            tp_c += 1
        elif has_truth and not has_pred:
            fn_c += 1
            misses_c.append(("FN", pair_key, p.get("case_type")))
        elif not has_truth and has_pred:
            # Only count as false positive if unrelated personas (not decoy)
            if p["label"] == "different_operator" and p.get("case_type") != "common_indicator_decoy":
                fp_c += 1
                misses_c.append(("FP", pair_key, p.get("case_type"), crypto_evidence[pair_key]))

    prec_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 1.0
    rec_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 1.0

    # 2. Evaluate Infrastructure Dimension
    tp_i, fp_i, fn_i = 0, 0, 0
    misses_i = []
    for p in truth["pairs"]:
        k1 = (p["a"]["username"], p["a"]["marketplace"])
        k2 = (p["b"]["username"], p["b"]["marketplace"])
        pair_key = (min(k1, k2), max(k1, k2))

        has_truth = "infrastructure" in p.get("shared_dimensions", [])
        has_pred = pair_key in infra_evidence

        if has_truth and has_pred:
            tp_i += 1
        elif has_truth and not has_pred:
            fn_i += 1
            misses_i.append(("FN", pair_key, p.get("case_type")))
        elif not has_truth and has_pred:
            if p["label"] == "different_operator":
                fp_i += 1
                misses_i.append(("FP", pair_key, p.get("case_type"), infra_evidence[pair_key]))

    prec_i = tp_i / (tp_i + fp_i) if (tp_i + fp_i) > 0 else 1.0
    rec_i = tp_i / (tp_i + fn_i) if (tp_i + fn_i) > 0 else 1.0

    # Print Evaluation Table
    table_headers = [
        "Dataset",
        "Dimension",
        "Pairs Evaluated",
        "True Positives",
        "False Positives",
        "False Negatives",
        "Precision",
        "Recall",
    ]
    total_pairs = len(truth["pairs"])
    table_rows = [
        [dataset_key.upper(), "Cryptographic", total_pairs, tp_c, fp_c, fn_c, f"{prec_c:.4f}", f"{rec_c:.4f}"],
        [dataset_key.upper(), "Infrastructure", total_pairs, tp_i, fp_i, fn_i, f"{prec_i:.4f}", f"{rec_i:.4f}"],
    ]
    print(_format_table(f"=== Ground-Truth Performance: {dataset_key.upper()} ===", table_headers, table_rows))

    if misses_c:
        print(f"Cryptographic misses: {misses_c}")
    if misses_i:
        print(f"Infrastructure misses: {misses_i}")

    # Specific assertions per prompt requirements:
    # A. Meaningful evidence precision >= 0.95 and recall >= 0.95
    assert prec_c >= 0.95, f"Crypto precision below 0.95: {prec_c}"
    assert rec_c >= 0.95, f"Crypto recall below 0.95: {rec_c}"
    assert prec_i >= 0.95, f"Infra precision below 0.95: {prec_i}"
    assert rec_i >= 0.95, f"Infra recall below 0.95: {rec_i}"

    # B. For every pair labelled different_operator that is NOT a common_indicator_decoy
    # or contradictory_crypto case, no cryptographic evidence >= 0.30 exists.
    for p in truth["pairs"]:
        k1 = (p["a"]["username"], p["a"]["marketplace"])
        k2 = (p["b"]["username"], p["b"]["marketplace"])
        pair_key = (min(k1, k2), max(k1, k2))
        if p["label"] == "different_operator" and p.get("case_type") not in (
            "common_indicator_decoy",
            "contradictory_crypto",
        ):
            assert (
                pair_key not in crypto_evidence
            ), f"Unexpected crypto evidence for different_operator: {pair_key}"

    # C. For decoy pairs there is no cryptographic evidence at all (they are suppressed)
    decoy_pairs = [p for p in truth["pairs"] if p.get("case_type") == "common_indicator_decoy"]
    for dp in decoy_pairs:
        k1 = (dp["a"]["username"], dp["a"]["marketplace"])
        k2 = (dp["b"]["username"], dp["b"]["marketplace"])
        pair_key = (min(k1, k2), max(k1, k2))
        assert pair_key not in all_crypto_evidence, f"Decoy pair leaked unsuppressed crypto evidence: {pair_key}"

    # Verify decoy values appear in the stage's suppressed list
    if decoy_pairs:
        crypto_stage = next(
            s for s in run.stage_runs if s.stage == PipelineStage.CRYPTO_MATCHING
        )
        suppressed_vals = [
            item["normalised_value"]
            for item in crypto_stage.summary.get("suppressed_common_indicators", [])
        ]
        assert any("DEC07" in val for val in suppressed_vals), "Decoy PGP fingerprint was not suppressed!"
        assert any("bc1qdecoy" in val for val in suppressed_vals), "Decoy escrow wallet was not suppressed!"

    # D. Contradictory crypto pair has cryptographic evidence
    contra_pairs = [p for p in truth["pairs"] if p.get("case_type") == "contradictory_crypto"]
    for cp in contra_pairs:
        k1 = (cp["a"]["username"], cp["a"]["marketplace"])
        k2 = (cp["b"]["username"], cp["b"]["marketplace"])
        pair_key = (min(k1, k2), max(k1, k2))
        assert pair_key in crypto_evidence, f"Contradictory crypto pair missing evidence: {pair_key}"

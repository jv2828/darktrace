"""Ground-truth evaluation of stylometric, behavioural, and multi-dimensional scoring systems."""

from collections import defaultdict
import json
from pathlib import Path
import pytest
from sklearn.metrics import roc_auc_score
from sqlalchemy import select

from app.core.security import hash_password
from app.models.analysis_result import AnalysisResult, AnalysisType
from app.models.correlation_result import CorrelationResult
from app.models.investigation import Investigation, InvestigationStatus
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
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
    """Evaluate pipeline scoring performance against Alpha and Beta ground truth benchmarks."""
    truth_file = DATASETS_DIR / f"{dataset_key}_truth.json"
    assert truth_file.exists(), f"Ground truth file missing: {truth_file}"

    with open(truth_file, "r", encoding="utf-8") as f:
        truth = json.load(f)

    # 1. Provision user and investigation
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

    # 2. Ingest benchmark dataset and execute complete 5-stage pipeline
    load_sample_to_investigation(db_session, user, inv.id, dataset_key)
    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id, session=db_session)

    db_session.refresh(run)
    assert run.status == PipelineRunStatus.COMPLETED

    # 3. Build actor mapping: (marketplace_name, username) -> actor_id
    actors = (
        db_session.execute(
            select(ThreatActor).join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        )
        .scalars()
        .all()
    )
    actor_lookup = {(a.marketplace.name, a.username): a.id for a in actors}

    # 4. Extract pairwise results from analysis_results
    style_res = db_session.scalar(
        select(AnalysisResult.result).where(
            AnalysisResult.pipeline_run_id == run.id,
            AnalysisResult.analysis_type == AnalysisType.OTHER,
            AnalysisResult.result["kind"].astext == "stylometry_pairs",
        )
    )
    style_sims = {}
    if style_res and "pairs" in style_res:
        for p in style_res["pairs"]:
            style_sims[(p["actor_a_id"], p["actor_b_id"])] = p["overall"]

    behav_res = db_session.scalar(
        select(AnalysisResult.result).where(
            AnalysisResult.pipeline_run_id == run.id,
            AnalysisResult.analysis_type == AnalysisType.OTHER,
            AnalysisResult.result["kind"].astext == "behaviour_pairs",
        )
    )
    behav_sims = {}
    if behav_res and "pairs" in behav_res:
        for p in behav_res["pairs"]:
            behav_sims[(p["actor_a_id"], p["actor_b_id"])] = p["overall"]

    # 5. Extract correlation_results
    corrs = db_session.scalars(
        select(CorrelationResult).where(CorrelationResult.pipeline_run_id == run.id)
    ).all()
    corr_map = {(c.actor_a_id, c.actor_b_id): c for c in corrs}

    # 6. Accumulate Ground Truth evaluations
    y_true_all = []
    y_score_comb = []
    y_true_style = []
    y_score_style = []
    y_true_behav = []
    y_score_behav = []

    case_stats = defaultdict(lambda: {"scores": [], "levels": []})
    special_pairs_log = []

    for p in truth["pairs"]:
        aid_a = actor_lookup[(p["a"]["marketplace"], p["a"]["username"])]
        aid_b = actor_lookup[(p["b"]["marketplace"], p["b"]["username"])]
        pair_key = (min(aid_a, aid_b), max(aid_a, aid_b))
        y = 1 if p["label"] == "same_operator" else 0
        case_type = p.get("case_type", "control")

        # Stored correlation or 0
        c = corr_map.get(pair_key)
        comb_score = float(c.combined_score) if c else 0.0

        if comb_score >= 0.70:
            level = "strong"
        elif comb_score >= 0.45:
            level = "moderate"
        elif comb_score >= 0.25:
            level = "weak"
        else:
            level = "none"

        y_true_all.append(y)
        y_score_comb.append(comb_score)

        # Dimension scores
        if pair_key in style_sims:
            y_true_style.append(y)
            y_score_style.append(style_sims[pair_key])

        if pair_key in behav_sims:
            y_true_behav.append(y)
            y_score_behav.append(behav_sims[pair_key])

        case_stats[case_type]["scores"].append(comb_score)
        case_stats[case_type]["levels"].append(level)

        if case_type in ("common_indicator_decoy", "contradictory_crypto"):
            contradictions_list = c.contradictions if (c and c.contradictions) else []
            contra_str = "; ".join(f"{item['dimension']} ({item['strength']})" for item in contradictions_list) or "None"
            special_pairs_log.append([
                case_type,
                f"{p['a']['username']} vs {p['b']['username']}",
                f"{comb_score:.4f}",
                level,
                contra_str,
            ])

    # 7. Compute ROC AUC
    style_auc = roc_auc_score(y_true_style, y_score_style) if len(set(y_true_style)) > 1 else 1.0
    behav_auc = roc_auc_score(y_true_behav, y_score_behav) if len(set(y_true_behav)) > 1 else 1.0
    comb_auc = roc_auc_score(y_true_all, y_score_comb) if len(set(y_true_all)) > 1 else 1.0

    total_pairs = len(truth["pairs"])
    style_skipped = total_pairs - len(y_true_style)
    behav_skipped = total_pairs - len(y_true_behav)

    # -------------------------------------------------------------
    # Table 1: ROC AUC Overview
    # -------------------------------------------------------------
    table_1_headers = ["Metric Dimension", "ROC AUC", "Pairs Evaluated", "Pairs Skipped (Lacking Data)"]
    table_1_rows = [
        ["Stylometry Overall", f"{style_auc:.4f}", str(len(y_true_style)), str(style_skipped)],
        ["Behaviour Overall", f"{behav_auc:.4f}", str(len(y_true_behav)), str(behav_skipped)],
        ["Final Combined Score", f"{comb_auc:.4f}", str(total_pairs), "0"],
    ]
    print(_format_table(f"TABLE 1: ROC AUC Performance ({dataset_key.upper()} Benchmark)", table_1_headers, table_1_rows))

    # -------------------------------------------------------------
    # Table 2: Per Case Type Breakdown
    # -------------------------------------------------------------
    table_2_headers = ["Case Type", "Pair Count", "Mean Combined Score", "Share Moderate/Strong"]
    table_2_rows = []
    for ct in sorted(case_stats.keys()):
        st = case_stats[ct]
        count = len(st["scores"])
        mean_s = sum(st["scores"]) / count if count > 0 else 0.0
        mod_strong_count = sum(1 for lvl in st["levels"] if lvl in ("moderate", "strong"))
        share_mod_strong = (mod_strong_count / count) * 100.0 if count > 0 else 0.0
        table_2_rows.append([ct, str(count), f"{mean_s:.4f}", f"{share_mod_strong:.1f}%"])
    print(_format_table(f"TABLE 2: Breakdown by Case Type ({dataset_key.upper()} Benchmark)", table_2_headers, table_2_rows))

    # -------------------------------------------------------------
    # Table 3: Hard Negatives Analysis
    # -------------------------------------------------------------
    hard_neg_types = [ct for ct in case_stats.keys() if "hard_negative" in ct]
    table_3_headers = ["Hard Negative Type", "Pair Count", "Mean Combined Score", "Share Moderate or Higher"]
    table_3_rows = []
    for hnt in sorted(hard_neg_types):
        st = case_stats[hnt]
        count = len(st["scores"])
        mean_s = sum(st["scores"]) / count if count > 0 else 0.0
        mod_or_higher = sum(1 for lvl in st["levels"] if lvl in ("moderate", "strong"))
        share = (mod_or_higher / count) * 100.0 if count > 0 else 0.0
        table_3_rows.append([hnt, str(count), f"{mean_s:.4f}", f"{share:.1f}%"])
    if not table_3_rows:
        table_3_rows.append(["None in benchmark", "0", "0.0000", "0.0%"])
    print(_format_table(f"TABLE 3: Hard Negatives Resilience ({dataset_key.upper()} Benchmark)", table_3_headers, table_3_rows))

    # -------------------------------------------------------------
    # Table 4: Special Decoy & Contradiction Handling
    # -------------------------------------------------------------
    table_4_headers = ["Special Case Type", "Pair Personas", "Combined Score", "Assigned Level", "Detected Contradictions"]
    if not special_pairs_log:
        special_pairs_log.append(["None in benchmark", "N/A", "0.0000", "none", "None"])
    print(_format_table(f"TABLE 4: Decoy & Contradiction Inspection ({dataset_key.upper()} Benchmark)", table_4_headers, special_pairs_log))

    # Assertions on benchmark expectations
    assert comb_auc >= 0.85, f"Combined ROC AUC ({comb_auc:.4f}) fell below expected 0.85 threshold"
    assert style_auc >= 0.85, f"Stylometry ROC AUC ({style_auc:.4f}) fell below expected 0.85 threshold"
    assert behav_auc >= 0.85, f"Behaviour ROC AUC ({behav_auc:.4f}) fell below expected 0.85 threshold"

    # Verify hard negatives did not reach moderate or strong
    for hnt in hard_neg_types:
        mod_or_higher = sum(1 for lvl in case_stats[hnt]["levels"] if lvl in ("moderate", "strong"))
        assert mod_or_higher == 0, f"Hard negative {hnt} reached moderate/strong link level!"


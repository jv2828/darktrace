"""Dossier export service generating forensic investigation reports in PDF, CSV, and JSON formats."""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.correlation_result import CorrelationResult
from app.models.evidence_record import EvidenceRecord
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.investigation_report import InvestigationReport, ReportFormat
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.post import Post
from app.models.scoring_config import ScoringConfig
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.correlation_service import (
    compute_correlation_level_and_coverage,
    get_latest_completed_run_id,
)

REPORTS_BASE_DIR = Path(__file__).resolve().parents[2] / "reports"

LIMITATIONS_STATEMENTS = [
    "Scores are heuristic evidence strengths, not probabilities of physical identity.",
    "Linguistic and behavioral similarity does not identify real-world individuals.",
    "Analysis is performed exclusively on synthetic or authorized stored data; no live network probing or DNS scanning is performed.",
    "Exact matching only: indicators are compared purely as extracted text without external active reconnaissance.",
    "Short text samples (< 300 words) and limited activity profiles (< 10 posts) are statistically volatile and cannot support conclusive attribution.",
]

ETHICS_NOTICE = (
    "FORENSIC INTELLIGENCE ASSESSMENT NOTICE: The indicators, similarities, and linkages "
    "presented in this dossier are calculated strictly from observable behavioral patterns "
    "and recorded cryptographic/infrastructure artifacts. Evidence scores are heuristic "
    "confidence measures and MUST NOT be construed as mathematical proof of identity or "
    "legal certainty. Persona attribution requires independent human corroboration."
)


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Check existence and verify investigator ownership (404 for other investigators)."""
    inv = db.scalar(select(Investigation).where(Investigation.id == investigation_id))
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def escape_csv_cell(val: Any) -> str:
    """Mitigate formula injection in spreadsheets by escaping =, +, -, @."""
    s = str(val if val is not None else "")
    if s and s[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


class NumberedCanvas(canvas.Canvas):
    """Canvas that performs a two-pass rendering to display total page count and header/footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header
        self.drawString(54, 750, "DARKTRACE — THREAT INTELLIGENCE & ACTOR CORRELATION PLATFORM")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 744, 612 - 54, 744)

        # Footer
        self.line(54, 46, 612 - 54, 46)
        self.drawString(54, 34, "CONFIDENTIAL // LAW ENFORCEMENT & CYBER DEFENSE USE ONLY // HEURISTIC EVALUATION")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 34, page_str)
        self.restoreState()


def _gather_dossier_data(db: Session, investigation_id: int, run_id: Optional[int]) -> Dict[str, Any]:
    """Gather all investigation artifacts, datasets, personas, indicators, and correlations."""
    inv = db.scalar(select(Investigation).where(Investigation.id == investigation_id))
    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)

    # Investigation datasets
    dataset_rows = db.execute(
        select(InvestigationDataset)
        .options(joinedload(InvestigationDataset.dataset))
        .where(InvestigationDataset.investigation_id == investigation_id)
    ).scalars().all()

    dataset_ids = [d.dataset_id for d in dataset_rows]

    datasets_summary = []
    for d_row in dataset_rows:
        ds = d_row.dataset
        p_count = db.scalar(select(func.count(Post.id)).where(Post.dataset_id == ds.id)) or 0
        i_count = (
            db.scalar(
                select(func.count(ExtractedIndicator.id))
                .join(Post, ExtractedIndicator.post_id == Post.id)
                .where(Post.dataset_id == ds.id)
            )
            or 0
        )
        datasets_summary.append({
            "id": ds.id,
            "name": ds.name,
            "source_type": ds.source_type.value if hasattr(ds.source_type, "value") else str(ds.source_type),
            "posts_count": p_count,
            "indicators_count": i_count,
        })

    # Pipeline run details
    run_info = None
    config_info = None
    if target_run_id:
        p_run = db.execute(
            select(PipelineRun)
            .options(joinedload(PipelineRun.scoring_config))
            .where(PipelineRun.id == target_run_id)
        ).scalar_one_or_none()
        if p_run:
            run_info = {
                "id": p_run.id,
                "status": p_run.status.value if hasattr(p_run.status, "value") else str(p_run.status),
                "started_at": p_run.started_at.isoformat() if p_run.started_at else None,
                "finished_at": p_run.finished_at.isoformat() if p_run.finished_at else None,
            }
            if p_run.scoring_config:
                config_info = {
                    "id": p_run.scoring_config.id,
                    "version": p_run.scoring_config.version,
                    "weights": p_run.scoring_config.weights,
                    "thresholds": p_run.scoring_config.thresholds,
                }

    # Threat Personas in these datasets
    persona_rows = db.execute(
        select(
            ThreatActor.id,
            ThreatActor.username,
            Marketplace.name.label("marketplace"),
            func.count(Post.id).label("post_count"),
            func.min(Post.posted_at).label("first_seen"),
            func.max(Post.posted_at).label("last_seen"),
        )
        .join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        .join(Post, Post.actor_id == ThreatActor.id)
        .where(Post.dataset_id.in_(dataset_ids))
        .group_by(ThreatActor.id, ThreatActor.username, Marketplace.name)
        .order_by(ThreatActor.username.asc())
    ).all()

    personas = [
        {
            "id": r[0],
            "username": r[1],
            "marketplace": r[2],
            "post_count": r[3],
            "first_seen": r[4].isoformat() if r[4] else None,
            "last_seen": r[5].isoformat() if r[5] else None,
        }
        for r in persona_rows
    ]

    # Extracted Indicators
    ind_rows = db.execute(
        select(
            ExtractedIndicator.id,
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.raw_value,
            ExtractedIndicator.normalised_value,
            ExtractedIndicator.confidence,
            ExtractedIndicator.post_id,
            ThreatActor.username,
            Marketplace.name.label("marketplace"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(ThreatActor, Post.actor_id == ThreatActor.id)
        .join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        .where(Post.dataset_id.in_(dataset_ids))
        .order_by(ExtractedIndicator.indicator_type, ExtractedIndicator.normalised_value)
    ).all()

    indicators = [
        {
            "id": r[0],
            "type": r[1].value if hasattr(r[1], "value") else str(r[1]),
            "raw_value": r[2],
            "normalised_value": r[3],
            "confidence": r[4],
            "post_id": r[5],
            "persona": r[6],
            "marketplace": r[7],
        }
        for r in ind_rows
    ]

    # Correlations
    correlations = []
    if target_run_id:
        c_records = db.execute(
            select(CorrelationResult)
            .options(
                joinedload(CorrelationResult.actor_a).joinedload(ThreatActor.marketplace),
                joinedload(CorrelationResult.actor_b).joinedload(ThreatActor.marketplace),
            )
            .where(CorrelationResult.pipeline_run_id == target_run_id)
            .order_by(CorrelationResult.combined_score.desc())
        ).scalars().all()

        for c in c_records:
            lvl, cov = compute_correlation_level_and_coverage(c)
            correlations.append({
                "actor_a": {
                    "id": c.actor_a_id,
                    "username": c.actor_a.username if c.actor_a else "Unknown",
                    "marketplace": c.actor_a.marketplace.name if (c.actor_a and c.actor_a.marketplace) else "Unknown",
                },
                "actor_b": {
                    "id": c.actor_b_id,
                    "username": c.actor_b.username if c.actor_b else "Unknown",
                    "marketplace": c.actor_b.marketplace.name if (c.actor_b and c.actor_b.marketplace) else "Unknown",
                },
                "combined_score": float(c.combined_score),
                "level": lvl,
                "coverage": float(cov),
                "dimension_scores": c.dimension_scores,
                "contributions": c.contributions,
                "missing_dimensions": c.missing_dimensions,
                "contradictions": c.contradictions,
                "contradiction_count": len(c.contradictions),
            })

    # Evidence Records (Supporting & Contradicting)
    evidence_records = []
    if target_run_id:
        ev_rows = db.execute(
            select(EvidenceRecord)
            .options(
                joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
                joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
                joinedload(EvidenceRecord.sources),
            )
            .where(EvidenceRecord.pipeline_run_id == target_run_id)
            .order_by(EvidenceRecord.strength.desc())
        ).unique().scalars().all()

        for ev in ev_rows:
            source_pids = list({s.post_id for s in ev.sources if s.post_id is not None})
            evidence_records.append({
                "id": ev.id,
                "actor_a": {
                    "id": ev.actor_a_id,
                    "username": ev.actor_a.username if ev.actor_a else "Unknown",
                    "marketplace": ev.actor_a.marketplace.name if (ev.actor_a and ev.actor_a.marketplace) else "Unknown",
                },
                "actor_b": {
                    "id": ev.actor_b_id,
                    "username": ev.actor_b.username if ev.actor_b else "Unknown",
                    "marketplace": ev.actor_b.marketplace.name if (ev.actor_b and ev.actor_b.marketplace) else "Unknown",
                },
                "dimension": ev.dimension.value if hasattr(ev.dimension, "value") else str(ev.dimension),
                "direction": ev.direction.value if hasattr(ev.direction, "value") else str(ev.direction),
                "evidence_type": ev.evidence_type,
                "strength": float(ev.strength),
                "explanation": ev.explanation,
                "source_post_ids": source_pids,
                "details": ev.details or {},
            })

    # Contradictions & Missing Data summary
    contradictions_list = []
    for c in correlations:
        if c.get("contradictions"):
            for contra in c["contradictions"]:
                contradictions_list.append({
                    "pair": f"{c['actor_a']['username']} <-> {c['actor_b']['username']}",
                    "dimension": contra.get("dimension"),
                    "strength": contra.get("strength"),
                    "short_text": contra.get("short_text"),
                })

    return {
        "investigation": {
            "id": inv.id,
            "title": inv.title,
            "description": inv.description,
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        },
        "pipeline_run": run_info,
        "scoring_config": config_info,
        "data_sources": datasets_summary,
        "personas": personas,
        "indicators": indicators,
        "correlated_pairs": correlations,
        "evidence_records": evidence_records,
        "contradictions_and_missing_data": contradictions_list,
        "limitations": LIMITATIONS_STATEMENTS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _generate_pdf_report(data: Dict[str, Any], output_path: Path) -> int:
    """Generate professional PDF forensic dossier using ReportLab."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    notice_style = ParagraphStyle(
        "NoticeBox",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#7c2d12"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    story: List[Any] = []

    # Title Block
    story.append(Paragraph("DARKTRACE THREAT INTELLIGENCE DOSSIER", title_style))
    inv = data["investigation"]
    meta_line = (
        f"<b>Case Title:</b> {inv['title']} (ID: #{inv['id']}) | "
        f"<b>Status:</b> {inv['status'].upper()} | "
        f"<b>Exported:</b> {data['generated_at'][:19]} UTC"
    )
    story.append(Paragraph(meta_line, body_style))
    story.append(Spacer(1, 8))

    # Ethics & Forensic Notice Box at top
    notice_table = Table(
        [[Paragraph(ETHICS_NOTICE, notice_style)]],
        colWidths=[504],
    )
    notice_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#fdba74")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(notice_table)
    story.append(Spacer(1, 10))

    # Run and Configuration Details
    p_run = data["pipeline_run"]
    p_cfg = data["scoring_config"]
    if p_run and p_cfg:
        weights_str = ", ".join(f"{k}: {v}" for k, v in p_cfg["weights"].items())
        run_text = (
            f"<b>Pipeline Run:</b> #{p_run['id']} ({p_run['status'].upper()}) | "
            f"<b>Scoring Config Version:</b> {p_cfg['version']} | "
            f"<b>Dimension Weights:</b> {weights_str}"
        )
        story.append(Paragraph(run_text, body_style))
        story.append(Spacer(1, 10))

    # Data Sources Table
    story.append(Paragraph("1. INVESTIGATION DATA SOURCES", h1_style))
    ds_data = [
        [
            Paragraph("Dataset Name", table_cell_bold),
            Paragraph("Type", table_cell_bold),
            Paragraph("Posts", table_cell_bold),
            Paragraph("Indicators", table_cell_bold),
        ]
    ]
    for ds in data["data_sources"]:
        ds_data.append([
            Paragraph(ds["name"], table_cell),
            Paragraph(ds["source_type"], table_cell),
            Paragraph(str(ds["posts_count"]), table_cell),
            Paragraph(str(ds["indicators_count"]), table_cell),
        ])
    ds_table = Table(ds_data, colWidths=[240, 100, 80, 84])
    ds_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ])
    )
    story.append(ds_table)
    story.append(Spacer(1, 12))

    # Summary Table of Top 20 Pairs
    story.append(Paragraph("2. TOP CORRELATED PERSONA PAIRS (UP TO 20)", h1_style))
    top_pairs = data["correlated_pairs"][:20]
    if not top_pairs:
        story.append(Paragraph("No persona linkages were identified meeting threshold criteria.", body_style))
    else:
        pairs_table_data = [
            [
                Paragraph("#", table_cell_bold),
                Paragraph("Persona A", table_cell_bold),
                Paragraph("Persona B", table_cell_bold),
                Paragraph("Score", table_cell_bold),
                Paragraph("Level", table_cell_bold),
                Paragraph("Coverage", table_cell_bold),
                Paragraph("Contradictions", table_cell_bold),
            ]
        ]
        for idx, cp in enumerate(top_pairs, 1):
            a_label = f"{cp['actor_a']['username']}<br/><font color='#64748b'>{cp['actor_a']['marketplace']}</font>"
            b_label = f"{cp['actor_b']['username']}<br/><font color='#64748b'>{cp['actor_b']['marketplace']}</font>"
            pairs_table_data.append([
                Paragraph(str(idx), table_cell),
                Paragraph(a_label, table_cell),
                Paragraph(b_label, table_cell),
                Paragraph(f"<b>{cp['combined_score']:.4f}</b>", table_cell),
                Paragraph(cp["level"].upper(), table_cell),
                Paragraph(f"{cp['coverage']*100:.0f}%", table_cell),
                Paragraph(str(cp["contradiction_count"]), table_cell),
            ])
        pairs_table = Table(pairs_table_data, colWidths=[24, 120, 120, 60, 60, 60, 60])
        pairs_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ])
        )
        story.append(pairs_table)

    story.append(Spacer(1, 12))

    # Detailed Blocks for Top Pairs
    story.append(Paragraph("3. MULTI-DIMENSIONAL EVIDENCE BREAKDOWN (TOP CORRELATED PAIRS)", h1_style))
    for idx, cp in enumerate(top_pairs[:5], 1):
        pair_header = (
            f"<b>Pair #{idx}:</b> {cp['actor_a']['username']} ({cp['actor_a']['marketplace']}) &lt;---&gt; "
            f"{cp['actor_b']['username']} ({cp['actor_b']['marketplace']}) | "
            f"Evidence Score: <b>{cp['combined_score']:.4f}</b> ({cp['level'].upper()}) | "
            f"Coverage: {cp['coverage']*100:.0f}%"
        )
        pair_block: List[Any] = [
            Paragraph(pair_header, table_cell_bold),
            Spacer(1, 4),
        ]

        # Contributions breakdown
        contrib_lines = []
        for dim, c_info in cp.get("contributions", {}).items():
            contrib_lines.append(
                f"{dim.title()}: score={c_info['score']:.4f}, weight={c_info['weight']}, contribution={c_info['contribution']:.4f}"
            )
        if contrib_lines:
            pair_block.append(Paragraph("<b>Dimension Contributions:</b> " + " | ".join(contrib_lines), body_style))
            pair_block.append(Spacer(1, 4))

        # Evidence records for this pair
        pair_a_id = cp["actor_a"]["id"]
        pair_b_id = cp["actor_b"]["id"]
        matching_evs = [
            ev
            for ev in data["evidence_records"]
            if (ev["actor_a"]["id"] == pair_a_id and ev["actor_b"]["id"] == pair_b_id)
            or (ev["actor_a"]["id"] == pair_b_id and ev["actor_b"]["id"] == pair_a_id)
        ]
        for ev in matching_evs:
            dir_color = "#15803d" if ev["direction"] == "supporting" else "#b91c1c"
            posts_str = f" [Posts: {', '.join(map(str, ev['source_post_ids']))}]" if ev["source_post_ids"] else ""
            ev_line = (
                f"<font color='{dir_color}'><b>[{ev['direction'].upper()}]</b></font> "
                f"<b>{ev['dimension'].title()} ({ev['evidence_type']}) - strength {ev['strength']:.4f}:</b> "
                f"{ev['explanation']}{posts_str}"
            )
            pair_block.append(Paragraph(ev_line, body_style))
            pair_block.append(Spacer(1, 2))

        pair_block.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))
        story.append(KeepTogether(pair_block))

    # Contradictory Evidence and Missing Data Section
    story.append(Paragraph("4. CONTRADICTORY EVIDENCE AND MISSING DATA", h1_style))
    contra_items = data["contradictions_and_missing_data"]
    if not contra_items:
        story.append(Paragraph("No analytical contradictions were detected among evaluated candidate pairs.", body_style))
    else:
        for c_item in contra_items:
            story.append(
                Paragraph(
                    f"<b>[CONTRADICTION] {c_item['pair']}</b> ({c_item['dimension']} dimension, strength {c_item['strength']}): "
                    f"{c_item['short_text']}",
                    body_style,
                )
            )
            story.append(Spacer(1, 2))

    story.append(Spacer(1, 10))

    # Indicators Appendix
    story.append(Paragraph("5. EXTRACTED INDICATORS APPENDIX (SAMPLE)", h1_style))
    ind_sample = data["indicators"][:25]
    if not ind_sample:
        story.append(Paragraph("No extracted indicators in this investigation.", body_style))
    else:
        ind_table_data = [
            [
                Paragraph("Persona", table_cell_bold),
                Paragraph("Type", table_cell_bold),
                Paragraph("Normalised Indicator Value", table_cell_bold),
                Paragraph("Confidence", table_cell_bold),
                Paragraph("Post ID", table_cell_bold),
            ]
        ]
        for ind in ind_sample:
            ind_table_data.append([
                Paragraph(ind["persona"], table_cell),
                Paragraph(ind["type"], table_cell),
                Paragraph(ind["normalised_value"], table_cell),
                Paragraph(ind["confidence"], table_cell),
                Paragraph(str(ind["post_id"]), table_cell),
            ])
        ind_table = Table(ind_table_data, colWidths=[100, 90, 214, 50, 50])
        ind_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ])
        )
        story.append(ind_table)

    story.append(Spacer(1, 12))

    # Forensic Limitations Section
    story.append(Paragraph("6. METHODOLOGICAL LIMITATIONS & DISCLAIMERS", h1_style))
    for lim in data["limitations"]:
        story.append(Paragraph(f"• {lim}", body_style))
        story.append(Spacer(1, 2))

    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path.stat().st_size


def _generate_csv_report(data: Dict[str, Any], csv_kind: str, output_path: Path) -> int:
    """Generate CSV export with formula-injection escaping."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if csv_kind == "evidence":
            writer.writerow([
                "actor_a", "actor_a_marketplace",
                "actor_b", "actor_b_marketplace",
                "dimension", "direction", "strength",
                "evidence_type", "explanation", "source_post_ids"
            ])
            for ev in data["evidence_records"]:
                writer.writerow([
                    escape_csv_cell(ev["actor_a"]["username"]),
                    escape_csv_cell(ev["actor_a"]["marketplace"]),
                    escape_csv_cell(ev["actor_b"]["username"]),
                    escape_csv_cell(ev["actor_b"]["marketplace"]),
                    escape_csv_cell(ev["dimension"]),
                    escape_csv_cell(ev["direction"]),
                    escape_csv_cell(ev["strength"]),
                    escape_csv_cell(ev["evidence_type"]),
                    escape_csv_cell(ev["explanation"]),
                    escape_csv_cell(";".join(map(str, ev["source_post_ids"]))),
                ])

        elif csv_kind == "indicators":
            writer.writerow([
                "persona", "marketplace", "type",
                "raw_value", "normalised_value", "post_id", "confidence"
            ])
            for ind in data["indicators"]:
                writer.writerow([
                    escape_csv_cell(ind["persona"]),
                    escape_csv_cell(ind["marketplace"]),
                    escape_csv_cell(ind["type"]),
                    escape_csv_cell(ind["raw_value"]),
                    escape_csv_cell(ind["normalised_value"]),
                    escape_csv_cell(ind["post_id"]),
                    escape_csv_cell(ind["confidence"]),
                ])

        else:  # default "pairs"
            writer.writerow([
                "actor_a", "actor_a_marketplace",
                "actor_b", "actor_b_marketplace",
                "combined_score", "level", "coverage",
                "cryptographic_score", "infrastructure_score",
                "stylometric_score", "behavioural_score",
                "contradiction_count"
            ])
            for cp in data["correlated_pairs"]:
                dims = cp.get("dimension_scores", {})
                writer.writerow([
                    escape_csv_cell(cp["actor_a"]["username"]),
                    escape_csv_cell(cp["actor_a"]["marketplace"]),
                    escape_csv_cell(cp["actor_b"]["username"]),
                    escape_csv_cell(cp["actor_b"]["marketplace"]),
                    escape_csv_cell(cp["combined_score"]),
                    escape_csv_cell(cp["level"]),
                    escape_csv_cell(cp["coverage"]),
                    escape_csv_cell(dims.get("cryptographic", {}).get("score", 0.0)),
                    escape_csv_cell(dims.get("infrastructure", {}).get("score", 0.0)),
                    escape_csv_cell(dims.get("stylometric", {}).get("score", 0.0)),
                    escape_csv_cell(dims.get("behavioural", {}).get("score", 0.0)),
                    escape_csv_cell(cp["contradiction_count"]),
                ])

    return output_path.stat().st_size


def create_investigation_report(
    db: Session,
    investigation_id: int,
    user: User,
    report_format: str,
    run_id: Optional[int] = None,
    csv_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate and store forensic dossier export in requested format."""
    _verify_investigation_access(db, investigation_id, user)

    fmt = report_format.lower()
    if fmt not in ("pdf", "csv", "json"):
        raise APIException(code="INVALID_FORMAT", message="Supported formats are 'pdf', 'csv', 'json'.", status_code=422)

    kind = (csv_kind or "pairs").lower()
    if fmt == "csv" and kind not in ("pairs", "evidence", "indicators"):
        raise APIException(code="INVALID_CSV_KIND", message="csv_kind must be 'pairs', 'evidence', or 'indicators'.", status_code=422)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)

    # Gather data
    dossier = _gather_dossier_data(db, investigation_id, target_run_id)

    # Ensure output directory exists
    inv_dir = REPORTS_BASE_DIR / str(investigation_id)
    inv_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:8]
    ext = fmt
    filename = f"dossier_case_{investigation_id}_{fmt}_{uid}.{ext}"
    out_file = inv_dir / filename

    if fmt == "json":
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(dossier, f, indent=2)
        file_size = out_file.stat().st_size
    elif fmt == "csv":
        file_size = _generate_csv_report(dossier, kind, out_file)
    else:  # pdf
        file_size = _generate_pdf_report(dossier, out_file)

    # Persist report entity
    rep = InvestigationReport(
        investigation_id=investigation_id,
        format=ReportFormat(fmt),
        file_path=str(out_file),
        generated_by=user.id,
        parameters={
            "run_id": target_run_id,
            "csv_kind": kind if fmt == "csv" else None,
            "filename": filename,
            "file_size": file_size,
        },
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)

    return {
        "id": rep.id,
        "investigation_id": rep.investigation_id,
        "format": rep.format.value if hasattr(rep.format, "value") else str(rep.format),
        "filename": filename,
        "file_size": file_size,
        "created_at": rep.created_at.isoformat() if rep.created_at else None,
        "parameters": rep.parameters,
    }


def list_investigation_reports(
    db: Session,
    investigation_id: int,
    user: User,
) -> List[Dict[str, Any]]:
    """List all exported dossiers for an investigation."""
    _verify_investigation_access(db, investigation_id, user)

    reports = db.scalars(
        select(InvestigationReport)
        .where(InvestigationReport.investigation_id == investigation_id)
        .order_by(InvestigationReport.created_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "investigation_id": r.investigation_id,
            "format": r.format.value if hasattr(r.format, "value") else str(r.format),
            "filename": r.parameters.get("filename") if r.parameters else f"report_{r.id}.{r.format}",
            "file_size": r.parameters.get("file_size") if r.parameters else 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "parameters": r.parameters,
        }
        for r in reports
    ]


def get_report_file_for_download(
    db: Session,
    investigation_id: int,
    report_id: int,
    user: User,
) -> Tuple[Path, str, str]:
    """Retrieve verified file path, filename, and mime type for report download."""
    _verify_investigation_access(db, investigation_id, user)

    report = db.scalar(
        select(InvestigationReport).where(
            InvestigationReport.id == report_id,
            InvestigationReport.investigation_id == investigation_id,
        )
    )
    if not report:
        raise APIException(code="NOT_FOUND", message="Report not found.", status_code=404)

    file_path = Path(report.file_path)
    if not file_path.exists():
        raise APIException(code="NOT_FOUND", message="Report file missing from storage.", status_code=404)

    fmt = report.format.value if hasattr(report.format, "value") else str(report.format)
    mime_types = {
        "pdf": "application/pdf",
        "csv": "text/csv",
        "json": "application/json",
    }
    mime = mime_types.get(fmt, "application/octet-stream")
    filename = report.parameters.get("filename", file_path.name)

    return file_path, filename, mime

"""SQLAlchemy ORM models package for DARKTRACE.

Importing this package exposes Base.metadata with all entity models defined.
"""

from app.db.base import Base, TimestampMixin
from app.models.user import User, UserRole
from app.models.dataset import Dataset, DatasetSourceType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.threat_actor import ThreatActor
from app.models.actor_alias import ActorAlias
from app.models.post import Post
from app.models.extracted_indicator import (
    ExtractedIndicator,
    IndicatorType,
    ExtractionMethod,
)
from app.models.scoring_config import ScoringConfig
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import (
    PipelineStageRun,
    PipelineStage,
    PipelineStageStatus,
)
from app.models.evidence_record import (
    EvidenceRecord,
    EvidenceDimension,
    EvidenceDirection,
)
from app.models.evidence_source import EvidenceSource
from app.models.correlation_result import CorrelationResult
from app.models.analysis_result import AnalysisResult, AnalysisType
from app.models.investigation_report import InvestigationReport, ReportFormat

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "UserRole",
    "Dataset",
    "DatasetSourceType",
    "Investigation",
    "InvestigationStatus",
    "InvestigationDataset",
    "Marketplace",
    "ThreatActor",
    "ActorAlias",
    "Post",
    "ExtractedIndicator",
    "IndicatorType",
    "ExtractionMethod",
    "ScoringConfig",
    "PipelineRun",
    "PipelineRunStatus",
    "PipelineStageRun",
    "PipelineStage",
    "PipelineStageStatus",
    "EvidenceRecord",
    "EvidenceDimension",
    "EvidenceDirection",
    "EvidenceSource",
    "CorrelationResult",
    "AnalysisResult",
    "AnalysisType",
    "InvestigationReport",
    "ReportFormat",
]


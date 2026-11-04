"""Extracted indicator model representing atomic threat indicators (wallets, PGP keys, domains)."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence_source import EvidenceSource
    from app.models.post import Post


class IndicatorType(str, enum.Enum):
    """Categorization of extracted indicators."""
    PGP_FINGERPRINT = "pgp_fingerprint"
    WALLET_BTC = "wallet_btc"
    WALLET_ETH = "wallet_eth"
    WALLET_XMR = "wallet_xmr"
    WALLET_OTHER = "wallet_other"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    SSL_CERT_FINGERPRINT = "ssl_cert_fingerprint"
    CERT_METADATA = "cert_metadata"
    SERVER_BANNER = "server_banner"
    PORT = "port"


class ExtractionMethod(str, enum.Enum):
    """Method by which the indicator was extracted."""
    REGEX = "regex"
    STRUCTURED_FIELD = "structured_field"
    MANUAL = "manual"


class ExtractedIndicator(Base):
    """Observed technical artifact or identifier extracted from post content."""

    __tablename__ = "extracted_indicators"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "indicator_type",
            "normalised_value",
            name="uq_extracted_indicators_post_id_type_normalised_value",
        ),
        Index("ix_extracted_indicators_type_value", "indicator_type", "normalised_value"),
        CheckConstraint(
            "(span_start IS NULL OR span_end IS NULL) OR (span_end >= span_start)",
            name="ck_extracted_indicators_span_range",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_extracted_indicators_confidence",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_type: Mapped[IndicatorType] = mapped_column(
        Enum(IndicatorType, name="indicator_type", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalised_value: Mapped[str] = mapped_column(Text, nullable=False)
    span_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    span_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    extractor_version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_valid_format: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[str] = mapped_column(
        String(10),
        server_default="high",
        default="high",
        nullable=False,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="indicators")
    evidence_sources: Mapped[List["EvidenceSource"]] = relationship("EvidenceSource", back_populates="indicator")


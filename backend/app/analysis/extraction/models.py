"""Data models for pure-Python threat indicator extraction."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TextStats:
    """Statistical overview of the analysed text body."""
    char_count: int = 0
    word_count: int = 0
    sentence_count: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class ExtractedIndicator:
    """Observed atomic threat indicator candidate."""
    indicator_type: str
    raw_value: str
    normalised_value: str
    span_start: Optional[int]
    span_end: Optional[int]
    extraction_method: str  # "regex" | "structured_field"
    is_valid_format: bool = True
    confidence: str = "high"  # "high" | "medium" | "low"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    """Complete output of the extraction pipeline on a post."""
    indicators: List[ExtractedIndicator] = field(default_factory=list)
    text_stats: TextStats = field(default_factory=TextStats)
    warnings: List[str] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)
    extractor_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicators": [ind.to_dict() for ind in self.indicators],
            "text_stats": self.text_stats.to_dict(),
            "warnings": list(self.warnings),
            "debug": dict(self.debug),
            "extractor_version": self.extractor_version,
        }

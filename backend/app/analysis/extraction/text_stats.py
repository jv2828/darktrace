"""Text statistics computation for post bodies."""

import re
from app.analysis.extraction.models import TextStats

# Sentence boundary pattern: period, exclamation, or question mark followed by whitespace or end of string
SENTENCE_SPLIT_PATTERN = re.compile(r'[.!?]+(?:\s+|$)')


def compute_text_stats(content: str) -> TextStats:
    """Compute character, word, and sentence counts for raw text."""
    if not content or not content.strip():
        return TextStats(char_count=len(content), word_count=0, sentence_count=0)

    char_count = len(content)
    words = content.split()
    word_count = len(words)

    # Split into candidate sentences
    raw_sentences = [s.strip() for s in SENTENCE_SPLIT_PATTERN.split(content) if s.strip()]
    sentence_count = max(len(raw_sentences), 1 if word_count > 0 else 0)

    return TextStats(
        char_count=char_count,
        word_count=word_count,
        sentence_count=sentence_count,
    )


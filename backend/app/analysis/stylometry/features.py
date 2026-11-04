"""Feature extraction for stylometric writeprint profiling."""

import re
from collections import Counter
from typing import Dict, List, Tuple
import numpy as np

# Fixed, deterministic list of 100 English function words (lowercase, alphabetically sorted)
FUNCTION_WORDS: List[str] = sorted([
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "ours", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your",
])

PUNCTUATION_MARKS: List[str] = [".", ",", "!", "?", ";", ":", "-", "...", '"', "'", "(", ")"]


def extract_actor_features(
    full_masked_text: str,
    words: List[str],
    sentences: List[str],
    post_count: int,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Extract numeric stylometric features and function word frequency vector.
    
    Returns:
        (general_features, function_word_features)
    """
    total_chars = len(full_masked_text)
    total_words = len(words)
    total_sentences = len(sentences)

    # 1. Sentence length metrics
    if total_sentences > 0:
        sent_lengths = [len(re.findall(r"[A-Za-z0-9']+", s)) for s in sentences]
        mean_sent_len = float(np.mean(sent_lengths))
        std_sent_len = float(np.std(sent_lengths))
        
        # Share of sentences starting with lowercase letter
        lowercase_starts = 0
        for s in sentences:
            m = re.search(r"[A-Za-z]", s)
            if m and m.group(0).islower():
                lowercase_starts += 1
        lowercase_start_share = lowercase_starts / total_sentences
    else:
        mean_sent_len = 0.0
        std_sent_len = 0.0
        lowercase_start_share = 0.0

    # 2. Word length and vocabulary richness
    if total_words > 0:
        mean_word_len = float(np.mean([len(w) for w in words]))
        
        # Type-token ratio on first 300 words (or all if < 300)
        window = [w.lower() for w in words[:300]]
        ttr = len(set(window)) / float(len(window))
        
        # Hapax legomena ratio (words appearing exactly once)
        word_counts = Counter(w.lower() for w in words)
        hapax_count = sum(1 for c in word_counts.values() if c == 1)
        hapax_ratio = hapax_count / float(total_words)

        # ALL-CAPS word ratio (words with len > 1 all uppercase)
        all_caps_count = sum(1 for w in words if len(w) > 1 and w.isupper())
        all_caps_word_ratio = all_caps_count / float(total_words)
    else:
        mean_word_len = 0.0
        ttr = 0.0
        hapax_ratio = 0.0
        all_caps_word_ratio = 0.0

    # 3. Character and punctuation metrics
    text_per_1000 = (total_chars / 1000.0) if total_chars > 0 else 1.0

    punct_rates: Dict[str, float] = {}
    for mark in PUNCTUATION_MARKS:
        if mark == "...":
            cnt = full_masked_text.count("...")
        else:
            # Avoid counting dots inside ellipsis for '.'
            if mark == ".":
                # Count total dots minus 3 * count of ellipses
                cnt = max(0, full_masked_text.count(".") - (3 * full_masked_text.count("...")))
            else:
                cnt = full_masked_text.count(mark)
        punct_rates[f"punct_{mark}"] = float(cnt) / text_per_1000

    letters = [c for c in full_masked_text if c.isalpha()]
    if letters:
        uppercase_ratio = sum(1 for c in letters if c.isupper()) / float(len(letters))
    else:
        uppercase_ratio = 0.0

    digits_count = sum(1 for c in full_masked_text if c.isdigit())
    digit_ratio = (digits_count / float(total_chars)) if total_chars > 0 else 0.0

    double_space_count = full_masked_text.count("  ")
    double_space_rate = float(double_space_count) / text_per_1000

    avg_words_per_post = (float(total_words) / float(max(1, post_count)))

    # Assemble general features dict
    general_features: Dict[str, float] = {
        "mean_sentence_length": round(mean_sent_len, 4),
        "std_sentence_length": round(std_sent_len, 4),
        "mean_word_length": round(mean_word_len, 4),
        "type_token_ratio_300": round(ttr, 4),
        "hapax_ratio": round(hapax_ratio, 4),
        "uppercase_letter_ratio": round(uppercase_ratio, 4),
        "all_caps_word_ratio": round(all_caps_word_ratio, 4),
        "lowercase_sentence_start_share": round(lowercase_start_share, 4),
        "double_space_rate": round(double_space_rate, 4),
        "digit_ratio": round(digit_ratio, 4),
        "avg_words_per_post": round(avg_words_per_post, 4),
    }
    general_features.update({k: round(v, 4) for k, v in punct_rates.items()})

    # 4. Function words frequencies
    fw_features: Dict[str, float] = {}
    lower_words = [w.lower() for w in words]
    word_freq = Counter(lower_words)
    denominator = float(max(1, total_words))
    for fw in FUNCTION_WORDS:
        fw_features[f"fw_{fw}"] = round(word_freq[fw] / denominator, 6)

    return general_features, fw_features


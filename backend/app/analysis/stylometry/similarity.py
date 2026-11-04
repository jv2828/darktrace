"""Pairwise stylometric comparison, relative z-scoring, and evidence generation."""

from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def cosine_sim(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors with zero-norm safety."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    val = float(np.dot(v1, v2) / (norm1 * norm2))
    return max(0.0, min(1.0, val))


def compare_actors_stylometry(
    actor_docs: Dict[int, str],
    actor_word_counts: Dict[int, int],
    actor_sufficiencies: Dict[int, str],
    actor_features: Dict[int, Dict[str, float]],
    actor_fw_features: Dict[int, Dict[str, float]],
    config_weights: Optional[Dict[str, float]] = None,
    z_support: float = 1.5,
    z_full: float = 3.5,
) -> Tuple[
    List[Dict[str, Any]],  # evidence candidates
    Dict[int, List[Dict[str, Any]]],  # per-actor top 15 tfidf summary
    List[Dict[str, Any]],  # all comparable pair similarity records
    Dict[str, Any],  # run metrics (baseline, spread, etc.)
]:
    """Perform pairwise TF-IDF, function-word, and feature vector comparisons across actors.
    
    Returns:
        (evidence_candidates, actor_tfidf_summaries, all_pairs_records, run_metrics)
    """
    weights = config_weights or {
        "char_ngram": 0.35,
        "word_ngram": 0.15,
        "function_words": 0.25,
        "feature_vector": 0.25,
    }

    # Only compare actors with sufficient or limited text
    comparable_actor_ids = sorted([
        aid for aid, suff in actor_sufficiencies.items() if suff in ("sufficient", "limited")
    ])

    actor_tfidf_summaries: Dict[int, List[Dict[str, Any]]] = {}

    if len(comparable_actor_ids) < 2:
        return [], {}, [], {
            "actors_compared": len(comparable_actor_ids),
            "baseline": 0.0,
            "spread": 0.02,
            "pairs_compared": 0,
            "pairs_supporting": 0,
        }

    # 1. Fit Char N-gram Vectorizer (3-5 ngrams, sublinear_tf=True, lowercase=False)
    corpus = [actor_docs[aid] for aid in comparable_actor_ids]
    char_vec = TfidfVectorizer(
        analyzer="char",
        ngram_range=(3, 5),
        sublinear_tf=True,
        lowercase=False,
    )
    char_matrix = char_vec.fit_transform(corpus).toarray()

    # 2. Fit Word N-gram Vectorizer (1-2 ngrams, sublinear_tf=True)
    word_vec = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    word_matrix = word_vec.fit_transform(corpus).toarray()
    word_feature_names = word_vec.get_feature_names_out()

    # Compute top 15 distinctive words/bigrams per actor
    for idx, aid in enumerate(comparable_actor_ids):
        row = word_matrix[idx]
        top_indices = np.argsort(row)[::-1][:15]
        summary_items = [
            {"term": str(word_feature_names[i]), "tfidf": round(float(row[i]), 4)}
            for i in top_indices
            if row[i] > 0
        ]
        actor_tfidf_summaries[aid] = summary_items

    # 3. Assemble function words matrix
    fw_keys = sorted(list(next(iter(actor_fw_features.values())).keys()))
    fw_matrix = np.array([
        [actor_fw_features[aid][k] for k in fw_keys]
        for aid in comparable_actor_ids
    ])

    # 4. Assemble general numeric features matrix & z-score across actors
    feat_keys = sorted(list(next(iter(actor_features.values())).keys()))
    raw_feat_matrix = np.array([
        [actor_features[aid][k] for k in feat_keys]
        for aid in comparable_actor_ids
    ])
    feat_means = np.mean(raw_feat_matrix, axis=0)
    feat_stds = np.std(raw_feat_matrix, axis=0)
    feat_stds = np.maximum(feat_stds, 1e-6)  # std floor 1e-6
    z_feat_matrix = (raw_feat_matrix - feat_means) / feat_stds
    k_features = float(len(feat_keys))
    sqrt_k = np.sqrt(k_features)

    # 5. Compute pairwise component similarities
    pair_records: List[Dict[str, Any]] = []
    actor_idx_map = {aid: idx for idx, aid in enumerate(comparable_actor_ids)}

    for i in range(len(comparable_actor_ids)):
        aid_a = comparable_actor_ids[i]
        for j in range(i + 1, len(comparable_actor_ids)):
            aid_b = comparable_actor_ids[j]

            # char ngram similarity
            sim_char = cosine_sim(char_matrix[i], char_matrix[j])

            # word ngram similarity
            sim_word = cosine_sim(word_matrix[i], word_matrix[j])

            # function words similarity
            sim_fw = cosine_sim(fw_matrix[i], fw_matrix[j])

            # feature vector distance -> similarity = 1 / (1 + d / sqrt(k))
            dist = float(np.linalg.norm(z_feat_matrix[i] - z_feat_matrix[j]))
            sim_feat = 1.0 / (1.0 + (dist / sqrt_k))
            sim_feat = max(0.0, min(1.0, sim_feat))

            # overall weighted mean
            overall = (
                weights["char_ngram"] * sim_char
                + weights["word_ngram"] * sim_word
                + weights["function_words"] * sim_fw
                + weights["feature_vector"] * sim_feat
            )
            overall = max(0.0, min(1.0, overall))

            # Shared distinctive word ngrams: highest min(tfidf_a, tfidf_b)
            row_a = word_matrix[i]
            row_b = word_matrix[j]
            shared_weights = np.minimum(row_a, row_b)
            top_shared_indices = np.argsort(shared_weights)[::-1][:5]
            shared_top_terms = [
                str(word_feature_names[idx])
                for idx in top_shared_indices
                if shared_weights[idx] > 0
            ]

            pair_records.append({
                "actor_a_id": min(aid_a, aid_b),
                "actor_b_id": max(aid_a, aid_b),
                "char_ngram": round(sim_char, 4),
                "word_ngram": round(sim_word, 4),
                "function_words": round(sim_fw, 4),
                "feature_vector": round(sim_feat, 4),
                "overall": round(overall, 4),
                "shared_top_terms": shared_top_terms,
            })

    # 6. Relative scoring over all comparable pairs of THIS run
    overall_values = np.array([p["overall"] for p in pair_records])
    baseline = float(np.median(overall_values))
    mad = float(np.median(np.abs(overall_values - baseline)))
    spread = float(max(1.4826 * mad, 0.02))

    baseline_reliable = len(pair_records) >= 6

    evidence_candidates: List[Dict[str, Any]] = []

    for p in pair_records:
        z = (p["overall"] - baseline) / spread
        p["z"] = round(float(z), 4)

        aid_a = p["actor_a_id"]
        aid_b = p["actor_b_id"]
        suff_a = actor_sufficiencies[aid_a]
        suff_b = actor_sufficiencies[aid_b]

        data_factor = 1.0 if (suff_a == "sufficient" and suff_b == "sufficient") else 0.7

        # Supporting evidence if z >= z_support
        if z >= z_support:
            raw_strength = (z - z_support) / (z_full - z_support)
            raw_strength = max(0.0, min(1.0, raw_strength))
            strength = raw_strength * data_factor
            if not baseline_reliable:
                strength = min(strength, 0.5)

            strength = round(float(strength), 4)

            # Build human-readable explanation
            top_terms_str = ", ".join(f'"{t}"' for t in p["shared_top_terms"][:3]) or "shared structural n-grams"
            agree_count = sum(
                1 for s in (p["char_ngram"], p["word_ngram"], p["function_words"], p["feature_vector"])
                if s >= baseline
            )
            explanation = (
                f"The writing styles are more similar than most other pairs in this investigation (z = {z:.2f}). "
                f"Both use distinctive expressions such as {top_terms_str}; {agree_count} of 4 style measures exceed the investigation baseline. "
                "Caveat: Style similarity is heuristic evidence on its own because authors may imitate or share underground writing habits."
            )

            details = {
                "components": {
                    "char_ngram": p["char_ngram"],
                    "word_ngram": p["word_ngram"],
                    "function_words": p["function_words"],
                    "feature_vector": p["feature_vector"],
                },
                "overall": p["overall"],
                "z": p["z"],
                "baseline": round(baseline, 4),
                "spread": round(spread, 4),
                "baseline_reliable": baseline_reliable,
                "actor_a_words": actor_word_counts[aid_a],
                "actor_b_words": actor_word_counts[aid_b],
                "actor_a_sufficiency": suff_a,
                "actor_b_sufficiency": suff_b,
                "shared_top_terms": p["shared_top_terms"],
            }

            evidence_candidates.append({
                "actor_a_id": aid_a,
                "actor_b_id": aid_b,
                "dimension": "stylometric",
                "evidence_type": "stylometric_similarity",
                "direction": "supporting",
                "strength": strength,
                "explanation": explanation,
                "details": details,
            })

    run_metrics = {
        "actors_compared": len(comparable_actor_ids),
        "pairs_compared": len(pair_records),
        "baseline": round(baseline, 4),
        "spread": round(spread, 4),
        "baseline_reliable": baseline_reliable,
        "pairs_supporting": len(evidence_candidates),
    }

    return evidence_candidates, actor_tfidf_summaries, pair_records, run_metrics


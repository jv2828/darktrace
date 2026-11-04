"""Behavioral profiling from post temporal distributions."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def circular_smooth(bins: np.ndarray, kernel: List[float] = [0.25, 0.5, 0.25]) -> np.ndarray:
    """Apply circular convolution smoothing across 1D periodic array."""
    n = len(bins)
    smoothed = np.zeros(n, dtype=float)
    k_left, k_center, k_right = kernel
    for i in range(n):
        smoothed[i] = (
            k_left * bins[(i - 1) % n]
            + k_center * bins[i]
            + k_right * bins[(i + 1) % n]
        )
    # Ensure non-negative and normalized
    smoothed = np.maximum(smoothed, 0.0)
    total = np.sum(smoothed)
    if total > 0:
        smoothed /= total
    return smoothed


def compute_actor_behaviour_profile(
    timestamps: List[datetime],
    min_sufficient: int = 10,
    min_limited: int = 5,
) -> Dict[str, Any]:
    """Compute temporal behavioral writeprint from a list of UTC datetimes."""
    total_posts = len(timestamps)

    if total_posts >= min_sufficient:
        sufficiency = "sufficient"
    elif total_posts >= min_limited:
        sufficiency = "limited"
    else:
        sufficiency = "insufficient"

    if total_posts == 0:
        return {
            "total_posts": 0,
            "sufficiency": "insufficient",
            "hourly_distribution": [round(1.0 / 24.0, 4)] * 24,
            "daily_distribution": [round(1.0 / 7.0, 4)] * 7,
            "active_days": 0,
            "posts_per_active_day": 0.0,
            "posts_per_week": 0.0,
            "first_post": None,
            "last_post": None,
            "peak_hour": 0,
            "active_hour_window": [0, 7],
            "active_hour_window_str": "00:00-08:00 UTC",
        }

    # Normalize datetimes to UTC
    utc_times: List[datetime] = []
    for dt in timestamps:
        if dt.tzinfo is None:
            utc_times.append(dt.replace(tzinfo=timezone.utc))
        else:
            utc_times.append(dt.astimezone(timezone.utc))

    utc_times.sort()
    first_post_dt = utc_times[0]
    last_post_dt = utc_times[-1]

    # Hourly distribution (0..23)
    hourly_counts = np.zeros(24, dtype=float)
    for dt in utc_times:
        hourly_counts[dt.hour] += 1.0
    hourly_dist = hourly_counts / float(total_posts)

    # Daily distribution (Monday=0..Sunday=6)
    daily_counts = np.zeros(7, dtype=float)
    for dt in utc_times:
        daily_counts[dt.weekday()] += 1.0
    daily_dist = daily_counts / float(total_posts)

    # Active days & frequency
    active_dates = {dt.date() for dt in utc_times}
    active_days_count = len(active_dates)
    posts_per_active_day = float(total_posts) / float(max(1, active_days_count))

    # Posts per week
    span_days = max(1, (last_post_dt.date() - first_post_dt.date()).days + 1)
    weeks = span_days / 7.0
    posts_per_week = float(total_posts) / float(max(1.0, weeks))

    # Peak hour & 8-hour active window
    peak_hour = int(np.argmax(hourly_dist))
    best_window_sum = -1.0
    best_start = 0
    for h in range(24):
        w_sum = sum(hourly_dist[(h + k) % 24] for k in range(8))
        if w_sum > best_window_sum:
            best_window_sum = w_sum
            best_start = h

    window_end = (best_start + 8) % 24
    window_str = f"{best_start:02d}:00-{window_end:02d}:00 UTC"

    return {
        "total_posts": total_posts,
        "sufficiency": sufficiency,
        "hourly_distribution": [round(float(v), 4) for v in hourly_dist],
        "daily_distribution": [round(float(v), 4) for v in daily_dist],
        "active_days": active_days_count,
        "posts_per_active_day": round(posts_per_active_day, 4),
        "posts_per_week": round(posts_per_week, 4),
        "first_post": first_post_dt.isoformat(),
        "last_post": last_post_dt.isoformat(),
        "peak_hour": peak_hour,
        "active_hour_window": [best_start, window_end],
        "active_hour_window_str": window_str,
    }


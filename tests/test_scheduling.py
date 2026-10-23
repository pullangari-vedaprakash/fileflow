import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker"))
for p in (backend_path, worker_path):
    if p not in sys.path:
        sys.path.insert(0, p)

from queue_service import (
    calculate_ranking_score,
    calculate_effective_score,
    PRIORITY_WEIGHTS,
    AGING_RATE_PER_SECOND,
)


def test_priority_ordering_at_same_timestamp():
    """
    When jobs arrive at the same time:
    HIGH score > NORMAL score > LOW score
    """
    now = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
    score_high = calculate_ranking_score("HIGH", now)
    score_normal = calculate_ranking_score("NORMAL", now)
    score_low = calculate_ranking_score("LOW", now)

    assert score_high > score_normal
    assert score_normal > score_low


def test_priority_aging_prevents_starvation():
    """
    Demonstrate that an older LOW-priority job genuinely overtakes a newer HIGH-priority job.
    
    Formula:
    HIGH weight: 100
    LOW weight: 20
    Aging rate: 1.0 point/second
    
    Job A: LOW created at T = 0
    Job B: HIGH created at T = 90
    
    At T = 90:
    Job A has waited 90 seconds.
    Effective score of Job A = 20 + (1.0 * 90) = 110.
    Effective score of Job B = 100 + (1.0 * 0) = 100.
    
    110 > 100 -> Job A outranks Job B!
    """
    t0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
    t90 = t0 + timedelta(seconds=90)

    score_a = calculate_ranking_score("LOW", t0)
    score_b = calculate_ranking_score("HIGH", t90)

    # In Redis Sorted Set (popped via ZPOPMAX):
    # Job A must have higher score than Job B
    assert score_a > score_b, f"Expected Job A ({score_a}) > Job B ({score_b})"

    # Effective score check at T = 90
    eff_a = calculate_effective_score("LOW", t0.replace(tzinfo=None), t90.replace(tzinfo=None))
    eff_b = calculate_effective_score("HIGH", t90.replace(tzinfo=None), t90.replace(tzinfo=None))
    assert eff_a == 110.0
    assert eff_b == 100.0
    assert eff_a > eff_b


def test_fifo_ordering_for_same_priority():
    """
    Two jobs with same priority (e.g. NORMAL):
    The earlier job must have a higher score (FIFO).
    """
    t0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
    t10 = t0 + timedelta(seconds=10)

    score_first = calculate_ranking_score("NORMAL", t0)
    score_second = calculate_ranking_score("NORMAL", t10)

    assert score_first > score_second

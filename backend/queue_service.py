from datetime import datetime, timezone
from typing import Optional, Tuple
import redis.asyncio as redis

# Priority Weights
PRIORITY_WEIGHTS = {
    "HIGH": 100.0,
    "NORMAL": 50.0,
    "LOW": 20.0,
}

# Aging rate: 1.0 point bonus per second waited
# A LOW job (20) waiting 30 seconds reaches 50 (competing with a fresh NORMAL job)
# A LOW job (20) waiting 80 seconds reaches 100 (competing with a fresh HIGH job)
# A LOW job (20) waiting >80 seconds outranks any newly arriving HIGH job, preventing starvation
AGING_RATE_PER_SECOND = 1.0

QUEUE_KEY = "job_queue"


def get_priority_weight(priority: str) -> float:
    return PRIORITY_WEIGHTS.get(priority.upper(), 50.0)


def calculate_ranking_score(priority: str, created_at: datetime) -> float:
    """
    Calculate the static Redis Sorted Set score that preserves dynamic priority aging.
    
    Mathematical proof:
    effective_score(t) = priority_weight + AGING_RATE * (t - created_at)
                       = [priority_weight - AGING_RATE * created_at] + AGING_RATE * t
    Since (AGING_RATE * t) is identical for all jobs at any evaluation time t,
    ranking_score = priority_weight - AGING_RATE * created_at_timestamp.
    
    Jobs are popped in descending order (ZPOPMAX).
    """
    weight = get_priority_weight(priority)
    ts = created_at.timestamp()
    return weight - (AGING_RATE_PER_SECOND * ts)


def calculate_effective_score(priority: str, created_at: datetime, current_time: Optional[datetime] = None) -> float:
    """
    Calculate the actual human-readable effective score at current_time.
    Useful for observability, debugging, and UI inspection.
    """
    now = current_time or datetime.now(timezone.utc).replace(tzinfo=None)
    wait_seconds = max(0.0, (now - created_at).total_seconds())
    weight = get_priority_weight(priority)
    return weight + (AGING_RATE_PER_SECOND * wait_seconds)


async def enqueue_job(redis_client: redis.Redis, job_id: int, priority: str, created_at: datetime) -> float:
    score = calculate_ranking_score(priority, created_at)
    await redis_client.zadd(QUEUE_KEY, {str(job_id): score})
    return score


async def remove_job(redis_client: redis.Redis, job_id: int) -> bool:
    removed = await redis_client.zrem(QUEUE_KEY, str(job_id))
    return bool(removed)


async def dequeue_job(redis_client: redis.Redis) -> Optional[Tuple[int, float]]:
    """
    Atomically pop the highest score job (ZPOPMAX).
    Returns (job_id, score) or None if queue is empty.
    """
    res = await redis_client.zpopmax(QUEUE_KEY, count=1)
    if not res:
        return None
    job_id_str, score = res[0]
    return int(job_id_str), float(score)


async def get_queue_length(redis_client: redis.Redis) -> int:
    return await redis_client.zcard(QUEUE_KEY)

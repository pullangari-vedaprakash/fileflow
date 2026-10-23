from datetime import datetime, timezone
from typing import Optional, Tuple
import redis.asyncio as redis

# Priority weights
PRIORITY_WEIGHTS = {
    "HIGH": 100.0,
    "NORMAL": 50.0,
    "LOW": 20.0,
}

# Linear priority aging rate: 1.0 point per second waited
AGING_RATE_PER_SECOND = 1.0
QUEUE_KEY = "job_queue"


def calculate_ranking_score(priority: str, created_at: datetime) -> float:
    """
    effective_score(t) = priority_weight + AGING_RATE * (t - created_at)
                       = [priority_weight - AGING_RATE * created_at] + AGING_RATE * t
    Static score for Redis Sorted Set = priority_weight - AGING_RATE * timestamp
    Popped with ZPOPMAX.
    """
    weight = PRIORITY_WEIGHTS.get(priority.upper(), 50.0)
    return weight - (AGING_RATE_PER_SECOND * created_at.timestamp())


class QueueScheduler:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def enqueue(self, job_id: int, priority: str, created_at: datetime) -> float:
        score = calculate_ranking_score(priority, created_at)
        await self.redis.zadd(QUEUE_KEY, {str(job_id): score})
        return score

    async def dequeue(self) -> Optional[Tuple[int, float]]:
        res = await self.redis.zpopmax(QUEUE_KEY, count=1)
        if not res:
            return None
        job_id_str, score = res[0]
        return int(job_id_str), float(score)

    async def remove(self, job_id: int) -> bool:
        return bool(await self.redis.zrem(QUEUE_KEY, str(job_id)))

    async def size(self) -> int:
        return await self.redis.zcard(QUEUE_KEY)

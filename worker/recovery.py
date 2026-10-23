import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, update
import redis.asyncio as redis
from models import Worker, Job, JobStatus
from scheduler import QueueScheduler

logger = logging.getLogger("worker.recovery")

RECOVERY_LOCK_KEY = "fileflow:recovery_lock"
LOCK_TIMEOUT_SECONDS = 25
STALE_THRESHOLD_SECONDS = 60


class RecoveryService:
    def __init__(
        self,
        worker_id: str,
        session_factory: async_sessionmaker,
        redis_client: redis.Redis,
        scheduler: QueueScheduler,
        interval_seconds: int = 30,
    ):
        self.worker_id = worker_id
        self.session_factory = session_factory
        self.redis = redis_client
        self.scheduler = scheduler
        self.interval = interval_seconds
        self.running = False

    async def acquire_recovery_lock(self) -> bool:
        """
        Distributed lock: ensures only one worker performs recovery pass.
        Prevents multiple workers from simultaneously recovering the same jobs.
        """
        acquired = await self.redis.set(
            RECOVERY_LOCK_KEY,
            self.worker_id,
            nx=True,
            ex=LOCK_TIMEOUT_SECONDS,
        )
        return bool(acquired)

    async def release_recovery_lock(self):
        val = await self.redis.get(RECOVERY_LOCK_KEY)
        if val == self.worker_id:
            await self.redis.delete(RECOVERY_LOCK_KEY)

    async def recover_stale_workers(self) -> int:
        recovered_count = 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale_cutoff = now - timedelta(seconds=STALE_THRESHOLD_SECONDS)

        async with self.session_factory() as db:
            # Query for workers that have not sent a heartbeat and are BUSY
            stmt = select(Worker).where(
                Worker.last_heartbeat < stale_cutoff,
                Worker.status == "BUSY",
            )
            result = await db.execute(stmt)
            stale_workers = result.scalars().all()

            for sw in stale_workers:
                job_id = sw.current_job_id
                logger.warning(
                    f"EVENT=WORKER_STALE worker_id={sw.id} last_heartbeat={sw.last_heartbeat} job_id={job_id}"
                )

                if job_id:
                    # Fetch job
                    job_res = await db.execute(select(Job).where(Job.id == job_id))
                    job = job_res.scalar_one_or_none()

                    if job and job.status == JobStatus.PROCESSING.value:
                        if job.retry_count < job.max_retries:
                            # Recoverable: increment retry count, set QUEUED, re-enqueue
                            job.retry_count += 1
                            job.status = JobStatus.QUEUED.value
                            job.error_message = f"Recovered from dead worker {sw.id} (attempt {job.retry_count}/{job.max_retries})"
                            job.progress = 0.0
                            
                            # Re-enqueue in Redis with original creation timestamp to preserve aged priority
                            await self.scheduler.enqueue(job.id, job.priority, job.created_at)
                            recovered_count += 1
                            logger.info(
                                f"EVENT=JOB_RECOVERED job_id={job.id} retry_count={job.retry_count} from_worker={sw.id}"
                            )
                        else:
                            # Not recoverable: maximum retries reached
                            job.status = JobStatus.FAILED.value
                            job.error_message = f"Worker {sw.id} died and job exceeded max retries ({job.max_retries})"
                            logger.error(
                                f"EVENT=JOB_FAILED_UNRECOVERABLE job_id={job.id} from_worker={sw.id}"
                            )

                # Mark stale worker as DEAD and clear current_job_id
                sw.status = "DEAD"
                sw.current_job_id = None
                await db.commit()

        return recovered_count

    async def run(self):
        self.running = True
        logger.info(f"Recovery service started (interval={self.interval}s, threshold={STALE_THRESHOLD_SECONDS}s)")
        while self.running:
            try:
                locked = await self.acquire_recovery_lock()
                if locked:
                    try:
                        recovered = await self.recover_stale_workers()
                        if recovered > 0:
                            logger.info(f"Recovery cycle complete: {recovered} jobs requeued.")
                    finally:
                        await self.release_recovery_lock()
            except Exception as e:
                logger.error(f"Error during recovery cycle: {e}")

            await asyncio.sleep(self.interval)

    async def stop(self):
        self.running = False

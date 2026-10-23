import os
import sys
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update, delete
import redis.asyncio as redis

# Ensure backend modules (config, models, database, storage) are resolvable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "backend"))
for d in (backend_dir, current_dir):
    if d not in sys.path:
        sys.path.insert(0, d)

from config import get_settings
from models import Job, File, ProcessingResult, JobStatus
from storage import storage
from scheduler import QueueScheduler
from heartbeat import HeartbeatService
from recovery import RecoveryService
from processors.image_processor import ImageProcessor
from processors.pdf_processor import PDFProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("worker")

settings = get_settings()

# Setup async SQLAlchemy engine
engine_url = settings.database_url
connect_args = {}
if "ssl=" in engine_url or "sslmode=" in engine_url or "neon.tech" in engine_url:
    base, _, _ = engine_url.partition("?")
    engine_url = base
    connect_args["ssl"] = "require"

engine = create_async_engine(engine_url, echo=False, connect_args=connect_args)
async_session = async_sessionmaker(engine, expire_on_commit=False)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"


async def publish_progress(user_id: int, job_id: int, status: str, progress: float = None, error: str = None):
    payload = {
        "type": "job_update",
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "progress": progress,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await redis_client.publish("job_updates", json.dumps(payload))
    except Exception as e:
        logger.warning(f"Failed to publish progress to Redis Pub/Sub: {e}")


class FileFlowWorker:
    def __init__(self, worker_id: str = WORKER_ID):
        self.worker_id = worker_id
        self.running = False
        self.scheduler = QueueScheduler(redis_client)
        self.heartbeat = HeartbeatService(self.worker_id, async_session, interval_seconds=10)
        self.recovery = RecoveryService(
            self.worker_id,
            async_session,
            redis_client,
            self.scheduler,
            interval_seconds=30,
        )

    def get_processor_for_file(self, extension: str):
        ext = (extension or "").lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            return ImageProcessor()
        elif ext == ".pdf":
            return PDFProcessor()
        return None

    async def claim_job_atomically(self, job_id: int) -> bool:
        """
        Idempotent atomic job claiming:
        Transitions QUEUED -> PROCESSING in PostgreSQL using UPDATE ... WHERE status='QUEUED'.
        Returns True only if THIS worker successfully transitioned the job.
        Guarantees duplicate delivery does not result in concurrent duplicate execution.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with async_session() as db:
            stmt = (
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.QUEUED.value)
                .values(
                    status=JobStatus.PROCESSING.value,
                    started_at=now,
                    progress=0.0,
                )
            )
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount > 0

    async def process_single_job(self, job_id: int):
        # 1. Atomic claim check
        claimed = await self.claim_job_atomically(job_id)
        if not claimed:
            logger.info(f"Job {job_id} already claimed or cancelled. Skipping.")
            return

        self.heartbeat.set_current_job(job_id)
        logger.info(f"EVENT=JOB_CLAIMED worker_id={self.worker_id} job_id={job_id}")

        async with async_session() as db:
            job_res = await db.execute(select(Job).where(Job.id == job_id))
            job = job_res.scalar_one_or_none()
            if not job:
                logger.error(f"Job {job_id} not found after claiming.")
                self.heartbeat.set_current_job(None)
                return

            user_id = job.user_id
            await publish_progress(user_id, job_id, "PROCESSING", 0.0)

            try:
                # 2. Fetch input file metadata
                file_res = await db.execute(select(File).where(File.id == job.file_id))
                file_obj = file_res.scalar_one_or_none()
                if not file_obj:
                    raise ValueError(f"Associated file ID {job.file_id} not found")

                logger.info(f"EVENT=JOB_STARTED job_id={job_id} file='{file_obj.original_name}' ops={job.operations}")

                # 3. Download binary from object storage
                file_bytes = storage.download_file(file_obj.storage_key)

                # 4. Select modular processor
                processor = self.get_processor_for_file(file_obj.extension)
                if not processor:
                    raise ValueError(f"No processor registered for extension '{file_obj.extension}'")

                # Progress callback updater
                async def progress_cb(pct: float):
                    job.progress = pct
                    await db.commit()
                    await publish_progress(user_id, job_id, "PROCESSING", pct)
                    logger.debug(f"EVENT=JOB_PROGRESS job_id={job_id} progress={pct}%")

                # 5. Clean up any previous results from failed retries (Idempotency)
                await db.execute(delete(ProcessingResult).where(ProcessingResult.job_id == job_id))
                await db.commit()

                # 6. Execute processing
                results = await processor.process(file_bytes, job.operations, job_id, db, progress_cb)

                for r in results:
                    db.add(r)

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                job.status = JobStatus.COMPLETED.value
                job.progress = 100.0
                job.completed_at = now
                job.error_message = None
                await db.commit()

                await publish_progress(user_id, job_id, "COMPLETED", 100.0)
                logger.info(f"EVENT=JOB_COMPLETED worker_id={self.worker_id} job_id={job_id} results_count={len(results)}")

            except Exception as e:
                logger.error(f"EVENT=JOB_ERROR worker_id={self.worker_id} job_id={job_id} error={e}")
                job.error_message = str(e)
                job.retry_count += 1

                if job.retry_count >= job.max_retries:
                    job.status = JobStatus.FAILED.value
                    await db.commit()
                    await publish_progress(user_id, job_id, "FAILED", job.progress, str(e))
                    logger.error(f"EVENT=JOB_FAILED job_id={job_id} max_retries={job.max_retries} reached.")
                else:
                    # Automatic retry: requeue with original creation timestamp
                    job.status = JobStatus.QUEUED.value
                    job.progress = 0.0
                    await db.commit()
                    await self.scheduler.enqueue(job.id, job.priority, job.created_at)
                    await publish_progress(user_id, job_id, "QUEUED", 0.0, f"Auto-retry {job.retry_count}/{job.max_retries}")
                    logger.warning(f"EVENT=JOB_RETRIED job_id={job_id} retry_count={job.retry_count}")

            finally:
                self.heartbeat.set_current_job(None)

    async def run(self):
        self.running = True
        logger.info(f"Worker {self.worker_id} online. Priority aging active.")

        # Launch heartbeat & stale recovery background tasks
        heartbeat_task = asyncio.create_task(self.heartbeat.run())
        recovery_task = asyncio.create_task(self.recovery.run())

        try:
            while self.running:
                # Atomically dequeue next highest priority/aged job
                item = await self.scheduler.dequeue()
                if item:
                    job_id, score = item
                    logger.info(f"Dequeued job {job_id} (ranking_score={score:.2f})")
                    await self.process_single_job(job_id)
                else:
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("Worker run loop cancelled.")
        finally:
            await self.heartbeat.stop()
            await self.recovery.stop()
            heartbeat_task.cancel()
            recovery_task.cancel()


if __name__ == "__main__":
    worker_instance = FileFlowWorker()
    try:
        asyncio.run(worker_instance.run())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")

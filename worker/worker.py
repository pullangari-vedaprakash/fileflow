import asyncio
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update
import redis.asyncio as redis
from config import get_settings
from models import Job, File, ProcessingResult, Worker, JobStatus
from storage import storage
from processors.image_processor import ImageProcessor
from processors.pdf_processor import PDFProcessor

settings = get_settings()

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

WORKER_ID = str(uuid.uuid4())[:8]
PRIORITY_SCORES = {"HIGH": 100, "NORMAL": 50, "LOW": 10}


async def publish_update(user_id: int, job_id: int, status: str, progress: float = None, error: str = None):
    payload = {
        "user_id": user_id,
        "type": "job_update",
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "error": error,
    }
    await redis_client.publish("job_updates", json.dumps(payload))


class JobWorker:
    def __init__(self):
        self.running = True
        self.current_job_id = None

    async def heartbeat(self):
        while self.running:
            async with async_session() as db:
                stmt = update(Worker).where(Worker.id == WORKER_ID).values(
                    last_heartbeat=datetime.utcnow(),
                    status="BUSY" if self.current_job_id else "IDLE",
                    current_job_id=self.current_job_id,
                )
                result = await db.execute(stmt)
                if result.rowcount == 0:
                    db.add(Worker(
                        id=WORKER_ID,
                        status="BUSY" if self.current_job_id else "IDLE",
                        current_job_id=self.current_job_id,
                        last_heartbeat=datetime.utcnow(),
                    ))
                await db.commit()
            await asyncio.sleep(10)

    async def recover_stale_jobs(self):
        while self.running:
            async with async_session() as db:
                stale_threshold = datetime.utcnow() - timedelta(seconds=60)
                result = await db.execute(
                    select(Worker).where(Worker.last_heartbeat < stale_threshold, Worker.status == "BUSY")
                )
                stale_workers = result.scalars().all()
                for w in stale_workers:
                    if w.current_job_id:
                        job_result = await db.execute(select(Job).where(Job.id == w.current_job_id))
                        job = job_result.scalar_one_or_none()
                        if job and job.status == JobStatus.PROCESSING.value:
                            job.status = JobStatus.QUEUED.value
                            job.error_message = "Worker died, requeued"
                            await db.commit()
                            # Re-add to sorted set with fresh score
                            created_ts = datetime.utcnow().timestamp()
                            score = PRIORITY_SCORES.get(job.priority, 50) + (created_ts / 1000.0)
                            await redis_client.zadd("job_queue", {str(job.id): score})
                        w.status = "DEAD"
                        await db.commit()
            await asyncio.sleep(30)

    async def process_job(self, job_id: int):
        async with async_session() as db:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job or job.status != JobStatus.QUEUED.value:
                return

            job.status = JobStatus.PROCESSING.value
            job.started_at = datetime.utcnow()
            job.progress = 0.0
            await db.commit()
            self.current_job_id = job_id

            await publish_update(job.user_id, job.id, "PROCESSING", 0.0)

            try:
                file_result = await db.execute(select(File).where(File.id == job.file_id))
                file = file_result.scalar_one()
                file_bytes = storage.download_file(file.storage_key)

                processor = None
                if file.extension in [".jpg", ".jpeg", ".png", ".webp"]:
                    processor = ImageProcessor()
                elif file.extension == ".pdf":
                    processor = PDFProcessor()

                if not processor:
                    raise ValueError("Unsupported file type")

                # Process with progress
                async def progress_cb(p):
                    job.progress = p
                    await db.commit()
                    await publish_update(job.user_id, job.id, "PROCESSING", p)

                results = await processor.process(file_bytes, job.operations, job_id, db, progress_cb)
                for res in results:
                    db.add(res)

                job.status = JobStatus.COMPLETED.value
                job.progress = 100.0
                job.completed_at = datetime.utcnow()
                await db.commit()

                await publish_update(job.user_id, job.id, "COMPLETED", 100.0)
                print(f"Job {job_id} completed")

            except Exception as e:
                job.retry_count += 1
                job.error_message = str(e)
                if job.retry_count >= job.max_retries:
                    job.status = JobStatus.FAILED.value
                    await publish_update(job.user_id, job.id, "FAILED", job.progress, str(e))
                else:
                    job.status = JobStatus.QUEUED.value
                    created_ts = datetime.utcnow().timestamp()
                    score = PRIORITY_SCORES.get(job.priority, 50) + (created_ts / 1000.0)
                    await redis_client.zadd("job_queue", {str(job.id): score})
                    await publish_update(job.user_id, job.id, "QUEUED", 0.0, f"Retry {job.retry_count}")
                await db.commit()
                print(f"Job {job_id} failed: {e}")
            finally:
                self.current_job_id = None

    async def run(self):
        asyncio.create_task(self.heartbeat())
        asyncio.create_task(self.recover_stale_jobs())

        print(f"Worker {WORKER_ID} started (priority + aging via sorted set)")
        while self.running:
            # ZPOPMAX gets the highest score (highest priority + oldest)
            result = await redis_client.zpopmax("job_queue", count=1)
            if result:
                job_id_str, score = result[0]
                job_id = int(job_id_str)
                await self.process_job(job_id)
            else:
                await asyncio.sleep(1)


if __name__ == "__main__":
    worker = JobWorker()
    asyncio.run(worker.run())

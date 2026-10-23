import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import update
from models import Worker

logger = logging.getLogger("worker.heartbeat")


class HeartbeatService:
    def __init__(self, worker_id: str, session_factory: async_sessionmaker, interval_seconds: int = 10):
        self.worker_id = worker_id
        self.session_factory = session_factory
        self.interval = interval_seconds
        self.running = False
        self.current_job_id = None

    def set_current_job(self, job_id: int = None):
        self.current_job_id = job_id

    async def update_heartbeat(self, status: str = None):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        worker_status = status or ("BUSY" if self.current_job_id else "IDLE")

        async with self.session_factory() as db:
            stmt = (
                update(Worker)
                .where(Worker.id == self.worker_id)
                .values(
                    status=worker_status,
                    current_job_id=self.current_job_id,
                    last_heartbeat=now,
                )
            )
            res = await db.execute(stmt)
            if res.rowcount == 0:
                # First time registration
                db.add(
                    Worker(
                        id=self.worker_id,
                        status=worker_status,
                        current_job_id=self.current_job_id,
                        last_heartbeat=now,
                        created_at=now,
                    )
                )
            await db.commit()

    async def run(self):
        self.running = True
        logger.info(f"Heartbeat started for worker {self.worker_id} (interval={self.interval}s)")
        while self.running:
            try:
                await self.update_heartbeat()
            except Exception as e:
                logger.error(f"Failed to record heartbeat: {e}")
            await asyncio.sleep(self.interval)

    async def stop(self):
        self.running = False
        try:
            await self.update_heartbeat(status="OFFLINE")
            logger.info(f"Worker {self.worker_id} marked OFFLINE")
        except Exception:
            pass

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Job, File, User, JobStatus, Priority, ProcessingResult
from schemas import JobCreate, JobOut, ResultOut
from auth import get_current_user
import redis.asyncio as redis
from config import get_settings
import json
from datetime import datetime

settings = get_settings()
router = APIRouter()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

PRIORITY_SCORES = {"HIGH": 100, "NORMAL": 50, "LOW": 10}


@router.post("/", response_model=JobOut)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(File).where(File.id == job_data.file_id, File.user_id == current_user.id, File.deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if job_data.priority not in [p.value for p in Priority]:
        raise HTTPException(status_code=400, detail="Invalid priority")

    job = Job(
        user_id=current_user.id,
        file_id=job_data.file_id,
        operations=job_data.operations,
        priority=job_data.priority,
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Priority + aging via sorted set score
    # score = base_priority + (unix_timestamp / 1000) so older jobs get higher score
    created_ts = job.created_at.timestamp()
    score = PRIORITY_SCORES.get(job.priority, 50) + (created_ts / 1000.0)
    await redis_client.zadd("job_queue", {str(job.id): score})

    return job


@router.get("/", response_model=list[JobOut])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/results", response_model=list[ResultOut])
async def get_job_results(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    res_result = await db.execute(
        select(ProcessingResult).where(ProcessingResult.job_id == job_id)
    )
    results = res_result.scalars().all()

    # Attach presigned URLs
    from storage import storage
    for r in results:
        r.download_url = storage.get_presigned_url(r.storage_key, expires=3600)

    return results


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in [JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail="Job cannot be retried")

    job.status = JobStatus.QUEUED.value
    job.retry_count = 0
    job.error_message = None
    job.progress = 0.0
    await db.commit()

    created_ts = datetime.utcnow().timestamp()
    score = PRIORITY_SCORES.get(job.priority, 50) + (created_ts / 1000.0)
    await redis_client.zadd("job_queue", {str(job.id): score})
    return {"message": "Job requeued"}


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=400, detail="Only queued jobs can be cancelled")

    job.status = JobStatus.CANCELLED.value
    await db.commit()
    await redis_client.zrem("job_queue", str(job.id))
    return {"message": "Job cancelled"}

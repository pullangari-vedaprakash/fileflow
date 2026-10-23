from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from database import get_db
from models import Job, File, User, JobStatus, Priority, ProcessingResult
from schemas import JobCreate, JobOut, ResultOut
from auth import get_current_user
from config import get_settings
from storage import storage
import queue_service

settings = get_settings()
router = APIRouter()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

IMAGE_OPERATIONS = {"resize", "compress", "thumbnail"}
PDF_OPERATIONS = {"extract_text", "generate_preview"}


def validate_operations_for_file(file: File, operations: list[str]):
    if not operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one processing operation must be specified",
        )

    ext = (file.extension or "").lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        allowed = IMAGE_OPERATIONS
        file_kind = "image"
    elif ext == ".pdf":
        allowed = PDF_OPERATIONS
        file_kind = "PDF"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'",
        )

    invalid_ops = [op for op in operations if op not in allowed]
    if invalid_ops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid operations for {file_kind}: {invalid_ops}. Allowed: {list(allowed)}",
        )


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify file ownership and existence
    result = await db.execute(
        select(File).where(
            File.id == job_data.file_id,
            File.user_id == current_user.id,
            File.deleted == False,
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Validate priority
    priority_upper = job_data.priority.upper()
    if priority_upper not in [p.value for p in Priority]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority '{job_data.priority}'. Allowed: {[p.value for p in Priority]}",
        )

    # Validate operations for file type
    validate_operations_for_file(file, job_data.operations)

    job = Job(
        user_id=current_user.id,
        file_id=job_data.file_id,
        operations=job_data.operations,
        priority=priority_upper,
        status=JobStatus.QUEUED.value,
        retry_count=0,
        max_retries=3,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue in Redis with priority aging score
    await queue_service.enqueue_job(redis_client, job.id, job.priority, job.created_at)

    return job


@router.get("/", response_model=list[JobOut])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .where(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    res_result = await db.execute(
        select(ProcessingResult).where(ProcessingResult.job_id == job_id)
    )
    results = res_result.scalars().all()

    # Attach presigned download URLs
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # State machine rule: Only FAILED jobs can be retried
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job in '{job.status}' state. Only FAILED jobs can be retried.",
        )

    # Enforce retry limit
    if job.retry_count >= job.max_retries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum retry limit of {job.max_retries} reached. Cannot retry further.",
        )

    job.retry_count += 1
    job.status = JobStatus.QUEUED.value
    job.error_message = None
    job.progress = 0.0
    await db.commit()

    # Re-enqueue in Redis with original creation timestamp so it preserves aging
    await queue_service.enqueue_job(redis_client, job.id, job.priority, job.created_at)

    return {
        "message": "Job requeued successfully",
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
    }


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # State machine rule: Only QUEUED jobs can be cancelled
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in '{job.status}' state. Only QUEUED jobs can be cancelled.",
        )

    job.status = JobStatus.CANCELLED.value
    await db.commit()

    # Remove from Redis sorted set
    await queue_service.remove_job(redis_client, job.id)

    return {"message": "Job cancelled successfully"}

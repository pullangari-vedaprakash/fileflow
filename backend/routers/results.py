from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import ProcessingResult, Job, User
from auth import get_current_user
from storage import storage

router = APIRouter()


@router.get("/{result_id}/download")
async def download_result(
    result_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get presigned URL for processed file download.
    Verifies user ownership via job association.
    """
    stmt = (
        select(ProcessingResult, Job)
        .join(Job, ProcessingResult.job_id == Job.id)
        .where(ProcessingResult.id == result_id, Job.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found or unauthorized",
        )

    result_obj, _ = row
    presigned_url = storage.get_presigned_url(result_obj.storage_key, expires=3600)
    return {
        "result_id": result_obj.id,
        "type": result_obj.type,
        "file_name": result_obj.file_name,
        "download_url": presigned_url,
    }

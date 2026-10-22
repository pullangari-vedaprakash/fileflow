import uuid
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import File, User
from schemas import FileOut
from auth import get_current_user
from storage import storage

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=FileOut)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    storage_key = f"users/{current_user.id}/files/{uuid.uuid4().hex}{ext}"

    from io import BytesIO
    storage.upload_file(storage_key, BytesIO(content), len(content), file.content_type or "application/octet-stream")

    db_file = File(
        user_id=current_user.id,
        original_name=file.filename,
        storage_key=storage_key,
        mime_type=file.content_type,
        extension=ext,
        size=len(content),
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)
    return db_file


@router.get("/", response_model=list[FileOut])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(File).where(File.user_id == current_user.id, File.deleted == False).order_by(File.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileOut)
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(File).where(File.id == file_id, File.user_id == current_user.id, File.deleted == False)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

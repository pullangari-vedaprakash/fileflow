import uuid
from pathlib import Path
from io import BytesIO
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, HTTPException, status
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

ALLOWED_MIME_TYPES = {
    ".jpg": {"image/jpeg", "image/pjpeg"},
    ".jpeg": {"image/jpeg", "image/pjpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf", "application/x-pdf"},
}


def validate_file_signature(content: bytes, ext: str) -> bool:
    """Validate magic bytes against expected file extension."""
    if len(content) < 4:
        return False
    if ext in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    elif ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext == ".webp":
        return content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"
    elif ext == ".pdf":
        return content.startswith(b"%PDF-")
    return False


@router.post("/upload", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    # Sanitize filename against path traversal
    safe_name = Path(file.filename).name
    ext = "." + safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' not allowed. Supported formats: JPG, PNG, WebP, PDF",
        )

    # Validate reported MIME type
    valid_mimes = ALLOWED_MIME_TYPES.get(ext, set())
    if file.content_type and file.content_type.lower() not in valid_mimes:
        # Fallback check if browser sends generic stream
        if file.content_type not in {"application/octet-stream", "binary/octet-stream"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MIME type '{file.content_type}' does not match extension '{ext}'",
            )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds 50 MB limit")

    # Validate file content signature (magic bytes) to prevent extension spoofing
    if not validate_file_signature(content, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File binary content does not match expected format for {ext}",
        )

    # Generated secure storage key: users/{user_id}/files/{uuid}.ext
    storage_key = f"users/{current_user.id}/files/{uuid.uuid4().hex}{ext}"

    # Determine canonical content type
    canonical_mime = next(iter(valid_mimes))
    storage.upload_file(storage_key, BytesIO(content), len(content), canonical_mime)

    db_file = File(
        user_id=current_user.id,
        original_name=safe_name,
        storage_key=storage_key,
        mime_type=canonical_mime,
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
        select(File)
        .where(File.user_id == current_user.id, File.deleted == False)
        .order_by(File.created_at.desc())
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file

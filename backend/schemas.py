from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FileOut(BaseModel):
    id: int
    original_name: str
    mime_type: Optional[str]
    extension: Optional[str]
    size: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    file_id: int
    operations: List[str]
    priority: str = "NORMAL"


class JobOut(BaseModel):
    id: int
    file_id: int
    operations: List[str]
    priority: str
    status: str
    progress: float
    retry_count: int
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResultOut(BaseModel):
    id: int
    type: str
    file_name: Optional[str]
    storage_key: str
    created_at: datetime
    download_url: Optional[str] = None

    class Config:
        from_attributes = True

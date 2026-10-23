from pydantic import BaseModel, EmailStr, ConfigDict
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
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    mime_type: Optional[str] = None
    extension: Optional[str] = None
    size: Optional[int] = None
    created_at: datetime


class JobCreate(BaseModel):
    file_id: int
    operations: List[str]
    priority: str = "NORMAL"


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    operations: List[str]
    priority: str
    status: str
    progress: float
    retry_count: int
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    file_name: Optional[str] = None
    storage_key: str
    created_at: datetime
    download_url: Optional[str] = None

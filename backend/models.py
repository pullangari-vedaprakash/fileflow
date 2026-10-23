from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Float, Index
)
from sqlalchemy.orm import relationship
from database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Priority(str, Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(512), nullable=False)
    storage_key = Column(String(1024), nullable=False, unique=True)
    mime_type = Column(String(128))
    extension = Column(String(16))
    size = Column(Integer)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="files")
    jobs = relationship("Job", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_files_user_created", "user_id", "created_at"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    operations = Column(JSON, nullable=False)  # list of operation names
    priority = Column(String(16), default=Priority.NORMAL.value, nullable=False, index=True)
    status = Column(String(32), default=JobStatus.QUEUED.value, nullable=False, index=True)
    progress = Column(Float, default=0.0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="jobs")
    file = relationship("File", back_populates="jobs")
    results = relationship("ProcessingResult", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_priority_created", "priority", "created_at"),
    )


class ProcessingResult(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(64), nullable=False)  # e.g. "resized", "thumbnail", "text", "preview"
    storage_key = Column(String(1024), nullable=False)
    file_name = Column(String(512))
    result_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    job = relationship("Job", back_populates="results")


class Worker(Base):
    __tablename__ = "workers"

    id = Column(String(64), primary_key=True)
    status = Column(String(32), default="IDLE", nullable=False)
    current_job_id = Column(Integer, nullable=True)
    last_heartbeat = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_workers_heartbeat_status", "last_heartbeat", "status"),
    )

import os
import sys
import pytest
from sqlalchemy import text

# Ensure backend and worker are in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker"))
for p in (backend_path, worker_path):
    if p not in sys.path:
        sys.path.insert(0, p)

from config import get_settings
from database import engine
from storage import storage
import redis.asyncio as redis


def test_settings_load():
    settings = get_settings()
    assert settings.app_name == "FileFlow"
    assert settings.database_url is not None
    assert settings.redis_url is not None
    assert settings.jwt_secret is not None
    assert settings.minio_bucket == "fileflow"


@pytest.mark.asyncio
async def test_database_connectivity():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_redis_connectivity():
    settings = get_settings()
    client = redis.from_url(settings.redis_url)
    pong = await client.ping()
    assert pong is True
    await client.aclose()


def test_storage_connectivity():
    bucket_exists = storage.client.bucket_exists(storage.bucket)
    assert bucket_exists is True

import os
import sys
import pytest_asyncio

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker"))
for p in (backend_path, worker_path):
    if p not in sys.path:
        sys.path.insert(0, p)

from database import engine


@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()

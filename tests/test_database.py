import os
import sys
import pytest
from sqlalchemy import inspect, select

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database import engine, Base, async_session, init_db
from models import User, File, Job, ProcessingResult, Worker, JobStatus, Priority


@pytest.mark.asyncio
async def test_database_schema_and_indexes():
    await init_db()

    def check_schema(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        expected_tables = {"users", "files", "jobs", "results", "workers"}
        assert expected_tables.issubset(tables)

        job_indexes = {idx["name"] for idx in inspector.get_indexes("jobs")}
        assert any("user" in name for name in job_indexes)
        assert any("status" in name for name in job_indexes)

        worker_indexes = {idx["name"] for idx in inspector.get_indexes("workers")}
        assert any("heartbeat" in name for name in worker_indexes)

    async with engine.connect() as conn:
        await conn.run_sync(check_schema)


@pytest.mark.asyncio
async def test_model_crud_and_cascade():
    async with async_session() as session:
        # Create user
        user = User(email="test_model_user@fileflow.io", password_hash="hashed_pw")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        user_id = user.id

        # Create file
        file = File(
            user_id=user_id,
            original_name="sample.png",
            storage_key=f"users/{user_id}/files/sample.png",
            mime_type="image/png",
            extension=".png",
            size=1024,
        )
        session.add(file)
        await session.commit()
        await session.refresh(file)
        assert file.id is not None
        file_id = file.id

        # Create job
        job = Job(
            user_id=user_id,
            file_id=file_id,
            operations=["resize", "thumbnail"],
            priority=Priority.HIGH.value,
            status=JobStatus.QUEUED.value,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        assert job.id is not None
        assert job.priority == "HIGH"
        assert job.status == "QUEUED"
        job_id = job.id

        # Create result
        result = ProcessingResult(
            job_id=job_id,
            type="resized",
            storage_key=f"results/{job_id}/resized.jpg",
            file_name="resized.jpg",
            result_metadata={"width": 800, "height": 600},
        )
        session.add(result)
        await session.commit()
        await session.refresh(result)
        assert result.result_metadata == {"width": 800, "height": 600}

        # Create worker
        worker = Worker(id="test-worker-diag", status="IDLE")
        session.add(worker)
        await session.commit()

        # Clean up test data: delete user (cascades to files, jobs, results)
        await session.delete(user)
        await session.delete(worker)
        await session.commit()

        # Verify cascade
        check_job = await session.execute(select(Job).where(Job.id == job_id))
        assert check_job.scalar_one_or_none() is None

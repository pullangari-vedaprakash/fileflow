import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport
import redis.asyncio as redis

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from main import app
from database import init_db, async_session
from models import Job, JobStatus
from config import get_settings
from queue_service import QUEUE_KEY
from sqlalchemy import select

settings = get_settings()


@pytest.mark.asyncio
async def test_job_lifecycle_and_constraints():
    await init_db()
    r = redis.from_url(settings.redis_url, decode_responses=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login user
        login_res = await client.post(
            "/api/auth/register",
            json={"email": "job_tester@fileflow.io", "password": "password123"},
        )
        if login_res.status_code == 400:
            login_res = await client.post(
                "/api/auth/login",
                json={"email": "job_tester@fileflow.io", "password": "password123"},
            )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload test image
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGB", (50, 50), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        upload_res = await client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("photo.jpg", buf.getvalue(), "image/jpeg")},
        )
        assert upload_res.status_code == 201
        file_id = upload_res.json()["id"]

        # 3. Create job with invalid operation for image (e.g. extract_text) -> 400
        bad_op_res = await client.post(
            "/api/jobs/",
            headers=headers,
            json={"file_id": file_id, "operations": ["extract_text"], "priority": "HIGH"},
        )
        assert bad_op_res.status_code == 400

        # 4. Create job with invalid priority -> 400
        bad_prio_res = await client.post(
            "/api/jobs/",
            headers=headers,
            json={"file_id": file_id, "operations": ["resize"], "priority": "SUPER_HIGH"},
        )
        assert bad_prio_res.status_code == 400

        # 5. Create valid job
        create_res = await client.post(
            "/api/jobs/",
            headers=headers,
            json={"file_id": file_id, "operations": ["resize", "thumbnail"], "priority": "HIGH"},
        )
        assert create_res.status_code == 201
        job_data = create_res.json()
        job_id = job_data["id"]
        assert job_data["status"] == "QUEUED"
        assert job_data["priority"] == "HIGH"

        # Verify job is present in Redis sorted set
        score = await r.zscore(QUEUE_KEY, str(job_id))
        assert score is not None

        # 6. Cancel queued job -> 200 and removed from Redis
        cancel_res = await client.post(f"/api/jobs/{job_id}/cancel", headers=headers)
        assert cancel_res.status_code == 200
        cancelled_score = await r.zscore(QUEUE_KEY, str(job_id))
        assert cancelled_score is None

        # Cancelling already cancelled job -> 400
        cancel_again = await client.post(f"/api/jobs/{job_id}/cancel", headers=headers)
        assert cancel_again.status_code == 400

        # 7. Retry cancelled job should be rejected (only FAILED can be retried) -> 400
        retry_cancelled = await client.post(f"/api/jobs/{job_id}/retry", headers=headers)
        assert retry_cancelled.status_code == 400

        # 8. Set job status to FAILED in DB and test retry behavior
        async with async_session() as session:
            db_job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
            db_job.status = JobStatus.FAILED.value
            db_job.retry_count = 0
            await session.commit()

        # Retry 1 -> 200, retry_count becomes 1
        r1 = await client.post(f"/api/jobs/{job_id}/retry", headers=headers)
        assert r1.status_code == 200
        assert r1.json()["retry_count"] == 1

        # Simulate job failed again up to max_retries = 3
        async with async_session() as session:
            db_job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
            db_job.status = JobStatus.FAILED.value
            db_job.retry_count = 3
            await session.commit()

        # 4th retry exceeds limit -> 400
        r_over = await client.post(f"/api/jobs/{job_id}/retry", headers=headers)
        assert r_over.status_code == 400
        assert "Maximum retry limit" in r_over.json()["detail"]

    await r.aclose()

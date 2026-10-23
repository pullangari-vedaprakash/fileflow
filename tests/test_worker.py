import os
import sys
import uuid
import pytest
from io import BytesIO
from PIL import Image
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker"))
for p in (backend_path, worker_path):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import app
from database import init_db, async_session
from models import Job, ProcessingResult, Worker, JobStatus, User, File, Priority
from worker import FileFlowWorker
from storage import storage


def create_sample_image():
    img = Image.new("RGB", (300, 300), color="green")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


def create_sample_pdf():
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )


@pytest.mark.asyncio
async def test_worker_image_processing_pipeline():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Auth
        auth_res = await client.post(
            "/api/auth/register",
            json={"email": "worker_image_user@fileflow.io", "password": "password123"},
        )
        if auth_res.status_code == 400:
            auth_res = await client.post(
                "/api/auth/login",
                json={"email": "worker_image_user@fileflow.io", "password": "password123"},
            )
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload Image
        img_bytes = create_sample_image()
        up_res = await client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("sample_worker.jpg", img_bytes, "image/jpeg")},
        )
        assert up_res.status_code == 201
        file_id = up_res.json()["id"]

        # Create Job with all 3 image operations
        job_res = await client.post(
            "/api/jobs/",
            headers=headers,
            json={"file_id": file_id, "operations": ["resize", "compress", "thumbnail"], "priority": "HIGH"},
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Run worker processing
        worker = FileFlowWorker(worker_id="test-worker-image")
        await worker.process_single_job(job_id)

        # Verify job is COMPLETED with 100% progress
        async with async_session() as session:
            job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
            assert job.status == JobStatus.COMPLETED.value
            assert job.progress == 100.0

            # Verify 3 results created
            results = (await session.execute(select(ProcessingResult).where(ProcessingResult.job_id == job_id))).scalars().all()
            assert len(results) == 3
            types = {r.type for r in results}
            assert types == {"resized", "compressed", "thumbnail"}

            # Verify downloaded result from storage
            for r in results:
                content = storage.download_file(r.storage_key)
                assert len(content) > 0

        # Verify results API endpoint with presigned download URLs
        res_api = await client.get(f"/api/jobs/{job_id}/results", headers=headers)
        assert res_api.status_code == 200
        res_list = res_api.json()
        assert len(res_list) == 3
        for item in res_list:
            assert item["download_url"] is not None
            assert item["download_url"].startswith("http")

        # Test GET /results/{id}/download
        first_result_id = res_list[0]["id"]
        dl_api = await client.get(f"/api/results/{first_result_id}/download", headers=headers)
        assert dl_api.status_code == 200
        assert dl_api.json()["download_url"] is not None


@pytest.mark.asyncio
async def test_worker_pdf_processing_pipeline():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_res = await client.post(
            "/api/auth/register",
            json={"email": "worker_pdf_user@fileflow.io", "password": "password123"},
        )
        if auth_res.status_code == 400:
            auth_res = await client.post(
                "/api/auth/login",
                json={"email": "worker_pdf_user@fileflow.io", "password": "password123"},
            )
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload PDF
        pdf_bytes = create_sample_pdf()
        up_res = await client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("manual.pdf", pdf_bytes, "application/pdf")},
        )
        assert up_res.status_code == 201
        file_id = up_res.json()["id"]

        # Create PDF Job
        job_res = await client.post(
            "/api/jobs/",
            headers=headers,
            json={"file_id": file_id, "operations": ["extract_text", "generate_preview"], "priority": "NORMAL"},
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Run worker processing
        worker = FileFlowWorker(worker_id="test-worker-pdf")
        await worker.process_single_job(job_id)

        # Verify job is COMPLETED
        async with async_session() as session:
            job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
            assert job.status == JobStatus.COMPLETED.value
            assert job.progress == 100.0

            results = (await session.execute(select(ProcessingResult).where(ProcessingResult.job_id == job_id))).scalars().all()
            assert len(results) == 2
            types = {r.type for r in results}
            assert types == {"text", "preview"}


@pytest.mark.asyncio
async def test_idempotent_atomic_job_claiming():
    await init_db()
    worker_a = FileFlowWorker(worker_id="worker-claim-A")
    worker_b = FileFlowWorker(worker_id="worker-claim-B")

    uid_tag = uuid.uuid4().hex[:8]
    async with async_session() as session:
        user = User(email=f"claim_user_{uid_tag}@fileflow.io", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        file = File(
            user_id=user.id,
            original_name="test.png",
            storage_key=f"users/{user.id}/files/claim_{uid_tag}.png",
            mime_type="image/png",
            extension=".png",
        )
        session.add(file)
        await session.commit()
        await session.refresh(file)

        job = Job(
            user_id=user.id,
            file_id=file.id,
            operations=["resize"],
            priority=Priority.HIGH.value,
            status=JobStatus.QUEUED.value,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    claim_a = await worker_a.claim_job_atomically(job_id)
    claim_b = await worker_b.claim_job_atomically(job_id)

    assert (claim_a and not claim_b) or (claim_b and not claim_a)


@pytest.mark.asyncio
async def test_worker_heartbeat_and_stale_recovery():
    await init_db()
    uid_tag = uuid.uuid4().hex[:8]
    worker = FileFlowWorker(worker_id=f"worker-recov-{uid_tag}")

    async with async_session() as session:
        await worker.heartbeat.update_heartbeat(status="IDLE")
        w_record = (await session.execute(select(Worker).where(Worker.id == worker.worker_id))).scalar_one()
        assert w_record.status == "IDLE"

        dead_worker_id = f"dead-{uid_tag}"
        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=90)

        user = User(email=f"recovery_{uid_tag}@fileflow.io", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        file = File(
            user_id=user.id,
            original_name="img.png",
            storage_key=f"users/{user.id}/files/rec_{uid_tag}.png",
            extension=".png",
        )
        session.add(file)
        await session.commit()
        await session.refresh(file)

        job = Job(
            user_id=user.id,
            file_id=file.id,
            operations=["resize"],
            priority=Priority.NORMAL.value,
            status=JobStatus.PROCESSING.value,
            retry_count=0,
            max_retries=3,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        session.add(
            Worker(
                id=dead_worker_id,
                status="BUSY",
                current_job_id=job.id,
                last_heartbeat=stale_time,
            )
        )
        await session.commit()

    # Run recovery pass in its own session
    recovered_count = await worker.recovery.recover_stale_workers()
    assert recovered_count == 1

    # Verify changes using a new session
    async with async_session() as verify_session:
        refreshed_job = (await verify_session.execute(select(Job).where(Job.id == job.id))).scalar_one()
        assert refreshed_job.status == JobStatus.QUEUED.value
        assert refreshed_job.retry_count == 1
        assert dead_worker_id in refreshed_job.error_message

        refreshed_worker = (await verify_session.execute(select(Worker).where(Worker.id == dead_worker_id))).scalar_one()
        assert refreshed_worker.status == "DEAD"

import os
import sys
import pytest
from io import BytesIO
from PIL import Image
from httpx import AsyncClient, ASGITransport

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from main import app
from database import init_db
from storage import storage


def create_test_image(format="PNG"):
    img = Image.new("RGB", (100, 100), color="blue")
    buf = BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def create_test_pdf():
    # Minimal valid PDF header and trailer
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )
    return pdf_bytes


@pytest.mark.asyncio
async def test_file_upload_and_validation():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        res_a = await client.post(
            "/api/auth/register",
            json={"email": "fileuser_a@fileflow.io", "password": "password123"},
        )
        if res_a.status_code == 400:
            res_a = await client.post(
                "/api/auth/login",
                json={"email": "fileuser_a@fileflow.io", "password": "password123"},
            )
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 1. Valid PNG Upload
        png_data = create_test_image("PNG")
        res_png = await client.post(
            "/api/files/upload",
            headers=headers_a,
            files={"file": ("test_image.png", png_data, "image/png")},
        )
        assert res_png.status_code == 201
        png_json = res_png.json()
        assert png_json["original_name"] == "test_image.png"
        assert png_json["mime_type"] == "image/png"
        file_a_id = png_json["id"]

        # Verify binary is in object storage
        from models import File
        from database import async_session
        from sqlalchemy import select

        async with async_session() as session:
            f = (await session.execute(select(File).where(File.id == file_a_id))).scalar_one()
            downloaded = storage.download_file(f.storage_key)
            assert len(downloaded) == len(png_data)

        # 2. Valid PDF Upload
        pdf_data = create_test_pdf()
        res_pdf = await client.post(
            "/api/files/upload",
            headers=headers_a,
            files={"file": ("document.pdf", pdf_data, "application/pdf")},
        )
        assert res_pdf.status_code == 201

        # 3. Disallowed extension (e.g. CSV or TXT)
        res_csv = await client.post(
            "/api/files/upload",
            headers=headers_a,
            files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
        )
        assert res_csv.status_code == 400

        # 4. Spoofed extension: fake PNG with text content
        res_spoof = await client.post(
            "/api/files/upload",
            headers=headers_a,
            files={"file": ("fake.png", b"this is not an image", "image/png")},
        )
        assert res_spoof.status_code == 400

        # 5. Path traversal attempt in filename
        res_traversal = await client.post(
            "/api/files/upload",
            headers=headers_a,
            files={"file": ("../../evil.png", png_data, "image/png")},
        )
        assert res_traversal.status_code == 201
        assert res_traversal.json()["original_name"] == "evil.png"

        # 6. User B isolation check: User B cannot get User A's file
        res_b = await client.post(
            "/api/auth/register",
            json={"email": "fileuser_b@fileflow.io", "password": "password123"},
        )
        if res_b.status_code == 400:
            res_b = await client.post(
                "/api/auth/login",
                json={"email": "fileuser_b@fileflow.io", "password": "password123"},
            )
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        res_unauthorized = await client.get(f"/api/files/{file_a_id}", headers=headers_b)
        assert res_unauthorized.status_code == 404

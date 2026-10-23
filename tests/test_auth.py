import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from main import app
from database import async_session, init_db
from models import User
from sqlalchemy import select, delete


@pytest.mark.asyncio
async def test_auth_flow():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = "authtest_user_unique@fileflow.io"
        test_password = "supersecretpassword123"

        # 1. Clean up user if existed
        async with async_session() as session:
            await session.execute(delete(User).where(User.email == test_email))
            await session.commit()

        # 2. Register
        reg_res = await client.post(
            "/api/auth/register",
            json={"email": test_email, "password": test_password},
        )
        assert reg_res.status_code == 201
        data = reg_res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        token = data["access_token"]

        # 3. Duplicate register should fail with 400
        dup_res = await client.post(
            "/api/auth/register",
            json={"email": test_email, "password": test_password},
        )
        assert dup_res.status_code == 400

        # 4. Short password should fail with 400
        short_res = await client.post(
            "/api/auth/register",
            json={"email": "shortpw@fileflow.io", "password": "123"},
        )
        assert short_res.status_code == 400

        # 5. Login with invalid password should fail with 401
        bad_login = await client.post(
            "/api/auth/login",
            json={"email": test_email, "password": "wrongpassword"},
        )
        assert bad_login.status_code == 401

        # 6. Login with valid credentials
        good_login = await client.post(
            "/api/auth/login",
            json={"email": test_email, "password": test_password},
        )
        assert good_login.status_code == 200
        login_token = good_login.json()["access_token"]

        # 7. Access /me with valid token
        me_res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {login_token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == test_email

        # 8. Access /me without token should fail with 401
        no_auth = await client.get("/api/auth/me")
        assert no_auth.status_code == 401

        # 9. Access /me with forged token should fail with 401
        fake_auth = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert fake_auth.status_code == 401

        # Clean up
        async with async_session() as session:
            await session.execute(delete(User).where(User.email == test_email))
            await session.commit()

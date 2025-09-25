import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db, engine as app_engine
from app.models import User
from app.auth import get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from datetime import timedelta
from sqlalchemy.future import select

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://user:password@db:5432/cadastral_db_test"

test_session_maker = sessionmaker(
    bind=app_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db():
    async with test_session_maker() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
async def reset_database_before_each_test():
    async with app_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def get_test_token(email: str, password: str, db: AsyncSession) -> str:
    statement = select(User).where(User.email == email)
    # Применяем await перед execute
    user = (await db.execute(statement)).scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise Exception("Invalid credentials for test user")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return access_token


def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


@pytest.mark.asyncio
async def test_auth_flow():
    async_session_generator = override_get_db()
    db: AsyncSession = await async_session_generator.__anext__()

    email = "testuser@example.com"
    password = "testpassword123"

    register_response = client.post("/register", json={"email": email, "password": password})
    assert register_response.status_code == 200, f"Registration failed: {register_response.text}"
    assert "User registered successfully" in register_response.json()["message"]

    register_duplicate_response = client.post("/register", json={"email": email, "password": password})
    assert register_duplicate_response.status_code == 400, "Registering duplicate user should fail with 400"
    assert "Email already registered" in register_duplicate_response.text

    login_response = client.post("/login", data={"username": email, "password": password})
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    token_data = login_response.json()
    access_token = token_data.get("access_token")
    assert access_token is not None, "Login should return an access token"
    assert token_data.get("token_type") == "bearer"

    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = client.get("/users/me", headers=headers)
    assert me_response.status_code == 200, f"GET /users/me failed: {me_response.text}"
    me_data = me_response.json()
    assert me_data["email"] == email
    assert me_data["is_active"] is True
    assert me_data["is_superuser"] is False

    unauthorized_response = client.get("/history")
    assert unauthorized_response.status_code == 401, "Access to protected resource without token should fail with 401"

    invalid_headers = {"Authorization": "Bearer invalid_token"}
    invalid_token_response = client.get("/history", headers=invalid_headers)
    assert invalid_token_response.status_code == 401, "Access with invalid token should fail with 401"

    await db.close()


@pytest.mark.asyncio
async def test_query_and_history_endpoints():
    async_session_generator = override_get_db()
    db: AsyncSession = await async_session_generator.__anext__()

    email = "testuser_for_query@example.com"
    password = "testpassword123"

    statement = select(User).where(User.email == email)
    user = (await db.execute(statement)).scalar_one_or_none()
    if not user:
        hashed_password = get_password_hash(password)
        user = User(email=email, hashed_password=hashed_password, is_active=True, is_superuser=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = await get_test_token(email, password, db)
    headers = {"Authorization": f"Bearer {access_token}"}

    cadastral_number = "123456789012"
    latitude = 55.7558
    longitude = 37.6173

    response_history_empty = client.get("/history", headers=headers)
    assert response_history_empty.status_code == 200
    assert response_history_empty.json() == []

    response_not_found = client.get("/history", params={"cadastral_number": "non_existent"}, headers=headers)
    assert response_not_found.status_code == 404
    assert "No history found for cadastral number: non_existent" in response_not_found.text

    query_data_post = {
        "cadastral_number": cadastral_number,
        "latitude": latitude,
        "longitude": longitude
    }
    response_post_query = client.post("/query", json=query_data_post, headers=headers)
    assert response_post_query.status_code == 200, f"POST /query failed with status {response_post_query.status_code}. Response: {response_post_query.text}"

    created_query_data = response_post_query.json()
    created_query_id = created_query_data.get("id")
    assert created_query_id is not None, "POST /query should return the id of the created record"
    assert "Success" in created_query_data.get("external_server_response", "")

    response_history_one_item = client.get("/history", headers=headers)
    assert response_history_one_item.status_code == 200
    history_items = response_history_one_item.json()
    assert len(history_items) == 1, f"Expected 1 item in history, got {len(history_items)}"
    assert history_items[0]["cadastral_number"] == cadastral_number
    assert history_items[0]["latitude"] == latitude
    assert history_items[0]["longitude"] == longitude

    response_history_filtered = client.get("/history", params={"cadastral_number": cadastral_number}, headers=headers)
    assert response_history_filtered.status_code == 200
    filtered_history = response_history_filtered.json()
    assert len(filtered_history) == 1, f"Expected 1 item in filtered history, got {len(filtered_history)}"
    assert filtered_history[0]["cadastral_number"] == cadastral_number
    assert filtered_history[0]["latitude"] == latitude
    assert filtered_history[0]["longitude"] == longitude

    await db.close()


@pytest.mark.asyncio
async def test_query_logs_table_creation():
    async_session_generator = override_get_db()
    db: AsyncSession = await async_session_generator.__anext__()

    email = "testuser_for_logs@example.com"
    password = "testpassword123"

    statement = select(User).where(User.email == email)
    user = (await db.execute(statement)).scalar_one_or_none()
    if not user:
        hashed_password = get_password_hash(password)
        user = User(email=email, hashed_password=hashed_password, is_active=True, is_superuser=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = await get_test_token(email, password, db)
    headers = {"Authorization": f"Bearer {access_token}"}

    cadastral_number = "987654321098"
    latitude = 51.5074
    longitude = -0.1278

    query_data_post = {
        "cadastral_number": cadastral_number,
        "latitude": latitude,
        "longitude": longitude
    }

    response_post_query = client.post("/query", json=query_data_post, headers=headers)
    assert response_post_query.status_code == 200, f"POST /query did not return 200 OK. Response: {response_post_query.text}"

    response_history_check = client.get("/history", params={"cadastral_number": cadastral_number}, headers=headers)
    assert response_history_check.status_code == 200
    history_items = response_history_check.json()
    assert len(history_items) == 1, f"Expected 1 record in history after POST /query, got {len(history_items)}"
    assert history_items[0]["cadastral_number"] == cadastral_number

    await db.close()
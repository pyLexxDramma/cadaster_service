import os
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.future import select

from app.db import engine, get_db, Base
from app.models import QueryLog, User
from app.auth import TokenData, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, \
    ALGORITHM
from app.auth_routes import router as auth_router
from app.dependencies import get_current_active_user

import httpx
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta

EXTERNAL_API_URL = os.environ.get("EXTERNAL_API_URL", "http://external_api_mock:8001")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")

app = FastAPI()

app.include_router(auth_router)


class QueryLogCreate(BaseModel):
    cadastral_number: str
    latitude: float
    longitude: float


class QueryLogResponse(BaseModel):
    id: int
    cadastral_number: str
    latitude: float
    longitude: float
    external_server_response: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


async def call_external_api(cadastral_number: str, latitude: float, longitude: float) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EXTERNAL_API_URL}/mock_query/",
                json={
                    "cadastral_number": cadastral_number,
                    "latitude": latitude,
                    "longitude": longitude
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"cadastral_number": cadastral_number, "status": "NotFound",
                    "message": "External API could not find data"}
        else:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=f"External API error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"External API is unavailable: {e}")


@app.get("/ping")
async def ping():
    return {"message": "pong"}


@app.post("/query", response_model=QueryLogResponse)
async def process_query(
        query_data: QueryLogCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    external_response = await call_external_api(
        query_data.cadastral_number,
        query_data.latitude,
        query_data.longitude
    )

    log_entry = QueryLog(
        cadastral_number=query_data.cadastral_number,
        latitude=query_data.latitude,
        longitude=query_data.longitude,
        external_server_response=str(external_response),
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    return log_entry


@app.get("/history", response_model=List[QueryLogResponse])
async def get_query_history(
        cadastral_number: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    statement = select(QueryLog).order_by(QueryLog.created_at.desc())
    if cadastral_number:
        statement = statement.where(QueryLog.cadastral_number == cadastral_number)

    result = await db.execute(statement)
    logs = result.scalars().all()

    if not logs and cadastral_number:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No history found for cadastral number: {cadastral_number}")

    return logs


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

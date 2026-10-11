import asyncio
import logging
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.document_service import rebuild_vector_index
from app.models import Base
from app.routers.chat import router as chat_router
from app.routers.database import router as database_router
from app.routers.documents import router as documents_router
from app.routers.evaluations import router as evaluations_router
from app.routers.monitoring import router as monitoring_router
from app.routers.settings import router as settings_router
from app.seed import seed_business_data, seed_source_documents
from app.vector_store import get_vector_store

settings = get_settings()
logger = logging.getLogger("novatech.api")
request_buckets: dict[str, deque[float]] = defaultdict(deque)
rate_limit_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env != "production":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_business_data(session)
        await seed_source_documents(session)
        await rebuild_vector_index(session)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Secure, evidence-backed enterprise knowledge and agent platform.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(database_router)
app.include_router(evaluations_router)
app.include_router(monitoring_router)
app.include_router(settings_router)


@app.get("/api/health", tags=["system"])
async def health(request: Request) -> JSONResponse:
    database_status = "ok"
    vector_status = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    try:
        await get_vector_store().health()
    except Exception:
        vector_status = "unavailable"
    healthy = database_status == "ok" and vector_status == "ok"
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "service": settings.app_name,
            "dependencies": {"database": database_status, "vector_store": vector_status},
            "request_id": request.state.request_id,
        },
    )


@app.middleware("http")
async def request_controls(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_id) else str(uuid4())
    request.state.request_id = request_id

    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        async with rate_limit_lock:
            bucket = request_buckets[client_key]
            cutoff = now - settings.rate_limit_window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_requests:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Retry after the current window.",
                        "request_id": request_id,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                return response
            bucket.append(now)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request parameters.", "request_id": request.state.request_id},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API failure request_id=%s error_type=%s",
        request.state.request_id,
        type(error).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "The request could not be completed.", "request_id": request.state.request_id},
    )

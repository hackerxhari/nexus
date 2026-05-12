"""
FastAPI application entry point for Nexus.
All startup, shutdown, middleware, and route registration here.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.ip_whitelist import IPWhitelistMiddleware
from api.routes import auth, query, ingest, admin, departments
from api.routes import custom_qa as custom_qa_routes
from api.routes import stt as stt_routes
from api.schemas.response import APIResponse
from cache.redis_client import redis_client
from core.config import get_settings
from core.exceptions import GreenBaseException
from core.logger import get_logger, setup_logging
from db.base import init_db
from ingestion.embedder import embedding_model
from retrieval.vector_store import vector_store

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown.
    All heavy initialization happens here once — not per request.
    """
    logger.info("nexus_starting", version=settings.APP_VERSION)

    # Initialize all services
    init_db()
    redis_client.initialize()
    vector_store.initialize()
    embedding_model.load()  # Load once — stays in memory

    if settings.OLLAMA_PREWARM:
        from llm.ollama_client import ollama_client
        ollama_client.prewarm()

    # Initialize STT if enabled (Vosk singleton loads its model on import)
    if settings.VOSK_ENABLED:
        try:
            from services.stt_service import stt_service  # noqa: F401
        except Exception as e:
            logger.warning("stt_init_skipped", error=str(e))

    logger.info("nexus_ready", host=settings.APP_HOST, port=settings.APP_PORT)
    yield

    # Graceful shutdown
    redis_client.close()
    logger.info("nexus_shutdown")


app = FastAPI(
    title="Nexus",
    description="Internal AI Knowledge Base",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(IPWhitelistMiddleware)

# CORS — configurable origins from .env
cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── Global Exception Handler ──────────────────────────────────
@app.exception_handler(GreenBaseException)
async def nexus_exception_handler(
    request: Request,
    exc: GreenBaseException
) -> JSONResponse:
    """
    Handle all custom exceptions uniformly.
    Never expose internal details to clients.
    """
    logger.warning(
        "handled_exception",
        error_code=exc.error_code.value,
        message=exc.message,
        path=request.url.path
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=APIResponse.fail(
            exc.error_code.value,
            exc.message,
            details=exc.details
        ).model_dump()
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Catch all unhandled exceptions — never return stack traces."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path
    )
    return JSONResponse(
        status_code=500,
        content=APIResponse.fail(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again."
        ).model_dump()
    )


# ── Routes ────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(custom_qa_routes.router, prefix="/api/v1")
app.include_router(stt_routes.router, prefix="/api/v1")


@app.get("/health")
async def public_health():
    """Public health check — no auth required."""
    return {"status": "ok", "version": settings.APP_VERSION}
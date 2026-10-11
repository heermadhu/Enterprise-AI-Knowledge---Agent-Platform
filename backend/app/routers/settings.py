from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def settings_status() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "database": "postgresql" if settings.database_url.startswith("postgresql") else "sqlite development",
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model if settings.llm_provider != "disabled" else None,
            "configured": settings.llm_provider == "openai" and bool(settings.llm_api_key),
        },
        "embeddings": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model if settings.embedding_provider != "local" else "local-hashing-384",
            "configured": settings.embedding_provider == "local" or bool(settings.embedding_api_key),
        },
        "vector_store": "qdrant",
        "max_upload_mb": settings.max_upload_mb,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "rate_limit": {
            "requests": settings.rate_limit_requests,
            "window_seconds": settings.rate_limit_window_seconds,
        },
        "allowed_file_types": ["PDF", "DOCX", "TXT", "CSV"],
    }

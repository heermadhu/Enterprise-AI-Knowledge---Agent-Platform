import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.document_service import DuplicateDocumentError, ingest_document, retrieve_chunks
from app.ingestion import EmptyDocumentError, UnsupportedDocumentError
from app.models import Document, DocumentChunk
from app.vector_store import get_vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=6, ge=1, le=12)


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)) -> list[dict]:
    counts = (
        select(DocumentChunk.document_id, func.count(DocumentChunk.id).label("chunk_count"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Document, func.coalesce(counts.c.chunk_count, 0).label("chunk_count"))
            .outerjoin(counts, counts.c.document_id == Document.id)
            .order_by(Document.uploaded_at.desc(), Document.id.desc())
        )
    ).all()
    return [
        {
            "id": document.id,
            "filename": document.filename,
            "content_type": document.content_type,
            "file_size": document.file_size,
            "status": document.status,
            "page_count": document.page_count,
            "chunk_count": chunk_count,
            "uploaded_at": document.uploaded_at,
        }
        for document, chunk_count in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    filename = file.filename or ""
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Files must be no larger than {settings.max_upload_mb} MB.",
        )
    try:
        document = await ingest_document(
            session,
            filename,
            file.content_type or "application/octet-stream",
            data,
        )
    except DuplicateDocumentError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (UnsupportedDocumentError, EmptyDocumentError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "page_count": document.page_count,
    }


@router.post("/search")
async def search_documents(request: SearchRequest) -> dict:
    citations = await retrieve_chunks(request.query, request.limit)
    return {"query": request.query, "citations": citations}


@router.get("/metadata/search")
async def search_document_metadata(
    query: str = Query(min_length=1, max_length=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.scalars(
            select(Document)
            .where(Document.filename.ilike(f"%{query}%"))
            .order_by(Document.uploaded_at.desc())
            .limit(20)
        )
    ).all()
    return [
        {"id": row.id, "filename": row.filename, "status": row.status, "uploaded_at": row.uploaded_at}
        for row in rows
    ]


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = (
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    ).all()
    return {
        "document_id": document.id,
        "filename": document.filename,
        "chunks": [
            {"id": chunk.id, "page": chunk.page_number, "content": chunk.content}
            for chunk in chunks
        ],
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, session: AsyncSession = Depends(get_session)) -> None:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = (
        await session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
    ).all()
    await get_vector_store().delete([chunk.vector_id for chunk in chunks])
    storage_path = Path(document.storage_path)
    await session.delete(document)
    await session.commit()
    await asyncio.to_thread(storage_path.unlink, missing_ok=True)

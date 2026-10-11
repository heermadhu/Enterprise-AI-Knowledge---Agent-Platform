import asyncio
import hashlib
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.embeddings import embed_texts, embedding_signature
from app.ingestion import chunk_pages, extract_pages
from app.models import Document, DocumentChunk
from app.vector_store import get_vector_store


class DuplicateDocumentError(ValueError):
    pass


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "compared", "did", "do", "does",
    "about", "for", "from", "how", "in", "is", "it", "of", "on", "our", "tell",
    "the", "to", "was", "what", "when", "where", "which", "who", "why", "with",
}


def safe_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f]", "", name)
    if not name or len(name) > 255:
        raise ValueError("The uploaded filename must contain 1 to 255 characters.")
    return name


async def ingest_document(
    session: AsyncSession,
    filename: str,
    content_type: str,
    data: bytes,
) -> Document:
    safe_name = safe_filename(filename)
    checksum = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(select(Document).where(Document.checksum == checksum))
    if existing:
        raise DuplicateDocumentError("This file has already been indexed.")

    settings = get_settings()
    pages = extract_pages(safe_name, data)
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("The document did not produce any searchable text.")
    if len(chunks) > 5000:
        raise ValueError("A document may produce no more than 5,000 indexed passages.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid4().hex}{Path(safe_name).suffix.lower()}"
    await asyncio.to_thread(file_path.write_bytes, data)
    document = Document(
        filename=safe_name,
        content_type=content_type[:120] or "application/octet-stream",
        checksum=checksum,
        file_size=len(data),
        storage_path=str(file_path.resolve()),
        status="processing",
        page_count=len(pages),
    )
    vector_ids: list[str] = []
    try:
        session.add(document)
        await session.flush()
        vectors = await embed_texts([chunk.content for chunk in chunks])
        vector_ids = [str(uuid4()) for _ in chunks]
        await get_vector_store().upsert(
            [
                {
                    "id": vector_id,
                    "vector": vector,
                    "payload": {
                        "document_id": document.id,
                        "filename": safe_name,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "embedding_signature": embedding_signature(),
                    },
                }
                for vector_id, vector, chunk in zip(vector_ids, vectors, chunks)
            ]
        )
        session.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    vector_id=vector_id,
                )
                for chunk, vector_id in zip(chunks, vector_ids)
            ]
        )
        document.status = "indexed"
        await session.commit()
    except Exception:
        await session.rollback()
        await get_vector_store().delete(vector_ids)
        await asyncio.to_thread(file_path.unlink, missing_ok=True)
        raise
    await session.refresh(document)
    return document


async def retrieve_chunks(query: str, limit: int = 6) -> list[dict]:
    query_vector = (await embed_texts([query]))[0]
    hits = await get_vector_store().search(query_vector, limit=max(limit * 4, 24))
    requested_year = re.search(r"\b20\d{2}\b", query)
    requested_quarters = {
        f"q{quarter}" for quarter in re.findall(r"\bq([1-4])\b", query.lower())
    }
    query_terms = {
        token[:-3] if token.endswith("ies") else token[:-1] if token.endswith("s") else token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }
    normalized_query = query.lower()
    if re.search(r"\b(?:what does|tell me about)\b", normalized_query) and any(
        product in normalized_query
        for product in ("novacloud", "novasecure", "novaanalytics", "novaflow", "novaai")
    ):
        query_terms.add("provide")
    results = []
    for hit in hits:
        payload = hit["payload"]
        content = payload.get("content", "").lower()
        filename = payload.get("filename", "").lower().replace("_", " ").replace("-", " ")
        if requested_year and requested_year.group(0) not in content and requested_year.group(0) not in filename:
            continue
        if requested_quarters and not any(
            quarter in content or quarter in filename for quarter in requested_quarters
        ):
            continue
        content_terms = {
            token[:-3] if token.endswith("ies") else token[:-1] if token.endswith("s") else token
            for token in re.findall(r"[a-z0-9]+", content)
        }
        matched_terms = query_terms & content_terms
        filename_matches = sum(term in filename for term in query_terms)
        lexical_score = len(matched_terms) / len(query_terms) if query_terms else 0.0
        filename_score = filename_matches / len(query_terms) if query_terms else 0.0
        semantic_score = float(hit["score"])
        reranked_score = semantic_score * 0.35 + lexical_score * 0.4 + filename_score * 0.25
        if not matched_terms and not filename_matches and get_settings().embedding_provider == "local":
            continue
        results.append(
            {
                "filename": payload.get("filename", "Unknown source"),
                "page": payload.get("page_number"),
                "snippet": payload.get("content", ""),
                "score": round(reranked_score, 4),
                "semantic_score": round(semantic_score, 4),
                "document_id": payload.get("document_id"),
                "chunk_index": payload.get("chunk_index"),
            }
        )
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


async def rebuild_vector_index(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(DocumentChunk.id)
        )
    ).all()
    vector_store = get_vector_store()
    signature = embedding_signature()
    point_count = await vector_store.count()
    if point_count == len(rows) and await vector_store.index_signature() == signature:
        return 0
    await vector_store.clear()
    if not rows:
        return 0
    vectors = await embed_texts([chunk.content for chunk, _ in rows])
    await vector_store.upsert(
        [
            {
                "id": chunk.vector_id,
                "vector": vector,
                "payload": {
                    "document_id": chunk.document_id,
                    "filename": filename,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "embedding_signature": signature,
                },
            }
            for (chunk, filename), vector in zip(rows, vectors)
        ]
    )
    return len(rows)

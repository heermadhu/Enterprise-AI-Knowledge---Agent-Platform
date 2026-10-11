from app.config import get_settings
from app.document_service import (
    DuplicateDocumentError,
    ingest_document,
    rebuild_vector_index,
    retrieve_chunks,
)
from app.vector_store import get_vector_store


async def test_ingestion_indexes_and_retrieves_citable_text(db_session, tmp_path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "qdrant_collection", "test_documents")
    get_vector_store.cache_clear()
    body = (
        b"NovaTech remote work policy allows employees to work remotely up to three days per week "
        b"with manager approval. Use company devices and multi-factor authentication."
    )

    document = await ingest_document(db_session, "Remote Work Policy.txt", "text/plain", body)
    citations = await retrieve_chunks("How many remote work days are allowed?", limit=3)

    assert document.status == "indexed"
    assert document.page_count == 1
    assert citations
    assert citations[0]["filename"] == "Remote Work Policy.txt"
    assert "three days per week" in citations[0]["snippet"]
    assert citations[0]["page"] is None
    assert citations[0]["score"] > 0
    try:
        await ingest_document(db_session, "Remote Work Policy.txt", "text/plain", body)
    except DuplicateDocumentError:
        pass
    else:
        raise AssertionError("Duplicate content should not be indexed twice.")


async def test_retrieval_does_not_use_sources_from_a_different_explicit_year(
    db_session, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "qdrant_collection", "year_filter_test")
    get_vector_store.cache_clear()
    await ingest_document(
        db_session,
        "Annual Report 2025.txt",
        "text/plain",
        b"NovaTech recognized revenue was 472000 dollars in September 2025.",
    )

    citations = await retrieve_chunks("What was NovaTech revenue in 2024?", limit=3)

    assert citations == []


async def test_product_definition_prefers_product_documentation(
    db_session, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "qdrant_collection", "product_definition_test")
    get_vector_store.cache_clear()
    await ingest_document(
        db_session,
        "Product_Documentation.txt",
        "text/plain",
        b"NovaSecure provides identity governance, threat monitoring, and endpoint protection.",
    )

    citations = await retrieve_chunks("Tell me about NovaSecure.", limit=3)

    assert citations
    assert citations[0]["filename"] == "Product_Documentation.txt"
    assert "identity governance" in citations[0]["snippet"]


async def test_quarter_retrieval_excludes_other_quarter_reports(
    db_session, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "qdrant_collection", "quarter_filter_test")
    get_vector_store.cache_clear()
    await ingest_document(
        db_session,
        "Q2_Financial_Report.txt",
        "text/plain",
        b"Q2 financial report: monthly revenue totaled 1392000 dollars.",
    )
    await ingest_document(
        db_session,
        "Q3_Financial_Report.txt",
        "text/plain",
        b"Q3 financial report: monthly revenue totaled 1497000 dollars.",
    )

    citations = await retrieve_chunks("What does the Q3 report say about revenue?", limit=6)

    assert citations
    assert all("Q3" in citation["filename"] for citation in citations)


async def test_startup_rebuilds_index_when_embedding_signature_changes(
    db_session, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "qdrant_collection", "signature_rebuild_test")
    get_vector_store.cache_clear()
    await ingest_document(
        db_session,
        "Index_Source.txt",
        "text/plain",
        b"NovaTech documents are indexed with an embedding provider signature.",
    )

    monkeypatch.setattr("app.document_service.embedding_signature", lambda: "different:model:version")

    rebuilt_count = await rebuild_vector_index(db_session)

    assert rebuilt_count == 1
    assert await get_vector_store().count() == 1
    assert await get_vector_store().index_signature() == "different:model:version"

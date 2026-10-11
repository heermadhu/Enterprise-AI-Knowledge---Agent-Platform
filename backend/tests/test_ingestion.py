import pytest

from app.ingestion import (
    EmptyDocumentError,
    ExtractedPage,
    UnsupportedDocumentError,
    chunk_pages,
    extract_pages,
)


def test_text_extraction_cleans_whitespace() -> None:
    pages = extract_pages("policy.txt", b"Remote work\r\n\r\n\r\n is supported.")

    assert pages[0].page_number is None
    assert pages[0].text == "Remote work\n\n is supported."


def test_rejects_untrusted_or_unsupported_uploads() -> None:
    with pytest.raises(UnsupportedDocumentError):
        extract_pages("../policy.exe", b"not safe")
    with pytest.raises(UnsupportedDocumentError):
        extract_pages("fake.pdf", b"not a PDF")
    with pytest.raises(EmptyDocumentError):
        extract_pages("empty.txt", b" \n ")


def test_chunks_preserve_page_and_overlap() -> None:
    chunks = chunk_pages([ExtractedPage(2, "abcdefghij" * 5)], chunk_size=20, overlap=5)

    assert len(chunks) > 1
    assert all(chunk.page_number == 2 for chunk in chunks)
    assert chunks[0].content[-5:] == chunks[1].content[:5]
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_invalid_chunk_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_pages([ExtractedPage(None, "text")], chunk_size=10, overlap=10)

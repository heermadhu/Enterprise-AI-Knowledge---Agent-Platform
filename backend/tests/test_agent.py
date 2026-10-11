from app.agent import answer_query
from app.config import get_settings
from app.vector_store import get_vector_store


async def test_agent_explicitly_reports_insufficient_evidence(db_session, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "qdrant_collection", "empty_evidence_test")
    get_vector_store.cache_clear()

    response = await answer_query("What was the CEO's blood type?", db_session)

    assert "don't have enough indexed evidence" in response["answer"].lower()
    assert response["citations"] == []


async def test_agent_abstains_when_retrieved_chunks_are_weakly_relevant(db_session, monkeypatch) -> None:
    async def weak_evidence(query: str, limit: int) -> list[dict]:
        return [
            {
                "filename": "HR_Handbook.txt",
                "snippet": "Employees coordinate planned leave with their manager.",
                "score": 0.1,
                "document_id": 1,
                "chunk_index": 0,
            }
        ]

    monkeypatch.setattr("app.agent.retrieve_chunks", weak_evidence)

    response = await answer_query("What is the employee private home address?", db_session)

    assert "don't have enough indexed evidence" in response["answer"].lower()
    assert response["citations"] == []

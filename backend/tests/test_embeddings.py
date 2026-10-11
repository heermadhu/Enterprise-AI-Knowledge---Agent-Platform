import asyncio

from app.embeddings import LOCAL_DIMENSION, local_embedding
from app.vector_store import VectorStore


def test_local_embedding_is_normalized_and_deterministic() -> None:
    first = local_embedding("Remote work policy and secure access")

    assert len(first) == LOCAL_DIMENSION
    assert first == local_embedding("Remote work policy and secure access")
    assert abs(sum(value * value for value in first) - 1) < 1e-6


def test_qdrant_stores_and_retrieves_chunk_metadata() -> None:
    store = VectorStore()
    vector = local_embedding("NovaTech remote work policy")
    asyncio.run(
        store.upsert(
            [
                {
                    "id": "a2a7943f-fd55-4f16-a7f6-1dcf88f3d9c2",
                    "vector": vector,
                    "payload": {"filename": "Remote Work Policy.txt", "content": "Employees may work remotely."},
                }
            ]
        )
    )
    results = asyncio.run(store.search(vector, limit=1))

    assert results[0]["payload"]["filename"] == "Remote Work Policy.txt"
    assert results[0]["score"] > 0.99

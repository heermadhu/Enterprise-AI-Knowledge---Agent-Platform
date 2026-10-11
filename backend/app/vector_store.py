import asyncio
from functools import lru_cache
from uuid import UUID

from qdrant_client import QdrantClient, models

from app.config import get_settings


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.client = (
            QdrantClient(":memory:")
            if settings.qdrant_url == ":memory:"
            else QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        )

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        if any(collection.name == self.collection for collection in collections):
            info = self.client.get_collection(self.collection)
            configured_size = info.config.params.vectors.size
            if configured_size != vector_size:
                raise ValueError(
                    f"Qdrant collection vector dimension is {configured_size}, expected {vector_size}."
                )
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    async def upsert(self, points: list[dict]) -> None:
        if not points:
            return
        await asyncio.to_thread(self._ensure_collection, len(points[0]["vector"]))
        qdrant_points = [
            models.PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point["payload"],
            )
            for point in points
        ]
        for offset in range(0, len(qdrant_points), 256):
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.collection,
                points=qdrant_points[offset : offset + 256],
                wait=True,
            )

    async def search(self, vector: list[float], limit: int = 6) -> list[dict]:
        await asyncio.to_thread(self._ensure_collection, len(vector))
        results = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": str(point.id), "score": point.score, "payload": point.payload or {}}
            for point in results.points
        ]

    async def delete(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        await asyncio.to_thread(
            self.client.delete,
            collection_name=self.collection,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )

    async def health(self) -> None:
        await asyncio.to_thread(self.client.get_collections)

    async def count(self) -> int:
        collections = await asyncio.to_thread(self.client.get_collections)
        if not any(collection.name == self.collection for collection in collections.collections):
            return 0
        result = await asyncio.to_thread(self.client.count, self.collection, exact=True)
        return result.count

    async def index_signature(self) -> str | None:
        collections = await asyncio.to_thread(self.client.get_collections)
        if not any(collection.name == self.collection for collection in collections.collections):
            return None
        points, _ = await asyncio.to_thread(
            self.client.scroll,
            collection_name=self.collection,
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not points or not points[0].payload:
            return None
        signature = points[0].payload.get("embedding_signature")
        return signature if isinstance(signature, str) else None

    async def clear(self) -> None:
        collections = await asyncio.to_thread(self.client.get_collections)
        if any(collection.name == self.collection for collection in collections.collections):
            await asyncio.to_thread(self.client.delete_collection, self.collection)


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()

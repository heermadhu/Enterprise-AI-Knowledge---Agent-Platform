import hashlib
import math
import re

import httpx

from app.config import get_settings

LOCAL_DIMENSION = 384
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def embedding_signature() -> str:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return f"local:blake2b-hashing:{LOCAL_DIMENSION}:v1"
    return (
        f"{settings.embedding_provider}:{settings.embedding_model}:"
        f"{settings.embedding_base_url.rstrip('/')}"
    )


def local_embedding(text: str) -> list[float]:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
    features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
    vector = [0.0] * LOCAL_DIMENSION
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest[:4], "little")
        index = value % LOCAL_DIMENSION
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        vector = [value / magnitude for value in vector]
    return vector


async def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return [local_embedding(text) for text in texts]
    if settings.embedding_provider != "openai":
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
    if not settings.embedding_api_key:
        raise ValueError("EMBEDDING_API_KEY is required for the OpenAI-compatible embedding provider.")

    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=45) as client:
        for offset in range(0, len(texts), 64):
            batch = texts[offset : offset + 64]
            response = await client.post(
                f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": batch},
            )
            response.raise_for_status()
            payload = response.json()
            batch_vectors = [
                item["embedding"]
                for item in sorted(payload["data"], key=lambda item: item["index"])
            ]
            if len(batch_vectors) != len(batch):
                raise ValueError("Embedding provider returned an unexpected number of vectors.")
            vectors.extend(batch_vectors)
    return vectors

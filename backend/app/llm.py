import time
from dataclasses import dataclass

import httpx

from app.config import get_settings


class LLMProviderError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float


async def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
    settings = get_settings()
    if settings.llm_provider != "openai":
        raise LLMProviderError("An OpenAI-compatible LLM provider is not configured.")
    if not settings.llm_api_key:
        raise LLMProviderError("LLM_API_KEY is required for the OpenAI-compatible LLM provider.")

    payload: dict = {"model": settings.llm_model, "messages": messages, "temperature": 0.1}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as error:
        raise LLMProviderError("The configured LLM provider timed out.") from error
    except httpx.HTTPStatusError as error:
        raise LLMProviderError(
            f"The configured LLM provider returned HTTP {error.response.status_code}."
        ) from error
    except httpx.HTTPError as error:
        raise LLMProviderError("The configured LLM provider could not be reached.") from error
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMProviderError("The configured LLM provider returned an invalid response.") from error

    choice = data["choices"][0]["message"]
    usage = data.get("usage") or {}
    return LLMResponse(
        content=choice.get("content") or "",
        tool_calls=choice.get("tool_calls") or [],
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        latency_ms=(time.perf_counter() - started) * 1000,
    )

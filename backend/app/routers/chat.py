import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent import answer_query
from app.db import SessionLocal, get_session
from app.llm import LLMProviderError
from app.models import ChatMessage, Conversation
from app.telemetry import elapsed_ms, record_metric

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    conversation_id: int | None = Field(default=None, ge=1)


@router.get("/conversations")
async def list_conversations(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.scalars(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at,
            "message_count": len(row.messages),
        }
        for row in rows
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    conversation = await session.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "metadata": message.metadata_json,
                "created_at": message.created_at,
            }
            for message in conversation.messages
        ],
    }


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    started = time.perf_counter()
    request_id = request.state.request_id
    response_result: dict[str, Any] | None = None
    response_status = 200
    error_name: str | None = None
    conversation_id: int | None = None
    try:
        history: list[dict[str, str]] = []
        if body.conversation_id is None:
            conversation = Conversation(title=body.query[:80])
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            conversation_id = conversation.id
        else:
            conversation = await session.scalar(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == body.conversation_id)
            )
            if conversation is None:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            conversation_id = conversation.id
            history = [
                {"role": item.role, "content": item.content}
                for item in conversation.messages[-8:]
                if item.role in {"user", "assistant"}
            ]
            await session.rollback()

        response_result = await answer_query(body.query, session, history)
        await session.rollback()
        session.add_all(
            [
                ChatMessage(conversation_id=conversation_id, role="user", content=body.query),
                ChatMessage(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_result["answer"],
                    metadata_json={
                        "citations": response_result["citations"],
                        "selected_tools": response_result["selected_tools"],
                        "sql": response_result["sql"],
                    },
                ),
            ]
        )
        await session.commit()
        response_result["conversation_id"] = conversation_id
        response_result["request_id"] = request_id
        return response_result
    except HTTPException as error:
        response_status = error.status_code
        error_name = "HTTPException"
        raise
    except LLMProviderError as error:
        response_status = 503
        error_name = type(error).__name__
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        response_status = 500
        error_name = type(error).__name__
        raise
    finally:
        async with SessionLocal() as metrics_session:
            await record_metric(
                metrics_session,
                request_id=request_id or str(uuid4()),
                query=body.query,
                status_code=response_status,
                result=response_result,
                error=error_name,
                total_latency_ms=elapsed_ms(started),
            )

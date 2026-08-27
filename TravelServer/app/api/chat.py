from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.db import create_session, get_session, list_sessions, touch_session
from app.graph.agent import get_graph
from app.graph.memory import ThinkFilter, strip_think

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=8000)


class SessionCreateRequest(BaseModel):
    title: str | None = None


def _thread_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _content_text(content: object) -> str:
    """兼容字符串和 GPT 风格 content block 列表，SSE 只推纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or ""))
        return "".join(parts)
    return str(content)


def _message_payload(message: Any) -> dict[str, str] | None:
    msg_type = getattr(message, "type", "")
    if msg_type not in {"human", "ai"}:
        return None
    return {
        "role": "user" if msg_type == "human" else "assistant",
        "content": strip_think(_content_text(message.content)),
    }


def _title_from_message(message: str) -> str:
    text = " ".join(message.strip().split())
    if len(text) <= 18:
        return text or "新的行程"
    return text[:18] + "…"


async def _serialize_state(session_id: str) -> dict[str, Any]:
    """从 LangGraph 检查点读出当前线程的消息、摘要和 token 占用。"""
    graph = get_graph()
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = snapshot.values if snapshot and snapshot.values else {}
    messages = []
    for item in values.get("messages") or []:
        payload = _message_payload(item)
        if payload:
            messages.append(payload)
    return {
        "messages": messages,
        "summary": values.get("summary") or "",
        "token_count": int(values.get("token_count") or 0),
        "compressed": bool(values.get("compressed")),
    }


@router.post("/sessions")
def create_chat_session(body: SessionCreateRequest | None = None) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    title = (body.title if body and body.title else None) or "新的行程"
    return create_session(session_id, title=title)


@router.get("/sessions")
def get_chat_sessions() -> dict[str, Any]:
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = await _serialize_state(session_id)
    return {**session, **state}


@router.get("/sessions/{session_id}/messages")
async def get_chat_messages(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    state = await _serialize_state(session_id)
    return {
        "session": session,
        **state,
        "context_window": settings.context_window,
        "compress_threshold": settings.compress_threshold,
    }


@router.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    """SSE 对话入口。thread_id 与 session_id 相同，用于续聊记忆。"""
    session = get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session["title"] == "新的行程":
        touch_session(body.session_id, title=_title_from_message(body.message))

    return StreamingResponse(
        _stream_chat(body.session_id, body.message.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_chat(session_id: str, message: str) -> AsyncIterator[str]:
    """跑完整张图：专项 Agent 推 progress，compose 节点推 token。"""
    graph = get_graph()
    config = _thread_config(session_id)
    compressed = False
    token_count = 0
    streamed = False
    think_filter = ThinkFilter()
    progress_labels = {
        "preference": "偏好 Agent：整理出行约束…",
        "destination": "目的地 Agent：评估候选城市…",
        "parallel_search": "航班 / 酒店 / 活动 Agent 并行搜索…",
        "budget": "预算 Agent：校验总花费…",
        "adjust": "超预算，启动渐进式降级…",
        "compose": "汇总 Agent：正在生成攻略…",
    }

    try:
        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=message)], "compressed": False},
            config,
            version="v2",
        ):
            kind = event.get("event")
            node = (event.get("metadata") or {}).get("langgraph_node")
            if kind == "on_chain_start" and node in progress_labels:
                yield _sse({"type": "progress", "agent": node, "message": progress_labels[node]})
            if kind == "on_chat_model_stream" and node == "compose":
                chunk = (event.get("data") or {}).get("chunk")
                raw = _content_text(getattr(chunk, "content", None) if chunk is not None else None)
                content = think_filter.feed(raw)
                if content:
                    streamed = True
                    yield _sse({"type": "token", "content": content})
            elif kind == "on_chain_end" and node == "compress":
                output = (event.get("data") or {}).get("output") or {}
                if isinstance(output, dict) and output.get("compressed"):
                    compressed = True
                    yield _sse(
                        {
                            "type": "compressed",
                            "summary": output.get("summary") or "",
                            "token_count": int(output.get("token_count") or 0),
                        }
                    )
            elif kind == "on_chain_end" and node in progress_labels:
                output = (event.get("data") or {}).get("output") or {}
                if isinstance(output, dict) and output.get("progress"):
                    yield _sse(
                        {
                            "type": "progress",
                            "agent": node,
                            "message": output["progress"],
                        }
                    )

        state = await graph.aget_state(config)
        values = state.values if state and state.values else {}
        token_count = int(values.get("token_count") or 0)
        compressed = compressed or bool(values.get("compressed"))
        summary = values.get("summary") or ""
        touch_session(
            session_id,
            summary=summary if compressed else None,
            token_count=token_count,
        )

        messages = list(values.get("messages") or [])
        last = messages[-1] if messages else None
        last_text = (
            strip_think(_content_text(last.content))
            if last is not None and getattr(last, "type", "") == "ai"
            else ""
        )
        if not streamed and last_text:
            yield _sse({"type": "token", "content": last_text})
        elif streamed and last_text:
            # 流式过程只有模型正文；文末「请确认」是 compose 后补上的，这里补推给前端
            marker = "\n---\n"
            idx = last_text.rfind(marker)
            if idx < 0:
                idx = last_text.rfind("## 请确认")
            if idx >= 0:
                yield _sse({"type": "token", "content": last_text[idx:]})

        yield _sse(
            {
                "type": "done",
                "compressed": compressed,
                "token_count": token_count,
                "summary": summary,
                "context_window": settings.context_window,
                "compress_threshold": settings.compress_threshold,
            }
        )
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})

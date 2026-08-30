from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.config import settings
from app.graph.trace import span

TOOL_NAME = "bailian_web_search"


class WebSearchMcpError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    key = settings.web_search_key
    if not key:
        raise WebSearchMcpError("未配置 WEB_SEARCH_MCP_KEY / AMAP_MCP_KEY，无法调用联网搜索 MCP")
    return {"Authorization": f"Bearer {key}"}


def _parse_tool_payload(result: Any) -> Any:
    chunks: list[str] = []
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            chunks.append(str(text))
        elif isinstance(item, dict) and item.get("text"):
            chunks.append(str(item["text"]))
    raw = "\n".join(chunks).strip()
    if getattr(result, "isError", False):
        raise WebSearchMcpError(raw or "联网搜索 MCP 调用失败")
    if not raw:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


@asynccontextmanager
async def open_web_search_session() -> AsyncIterator[Any]:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client

    url = (settings.web_search_mcp_url or "").strip()
    if not url:
        raise WebSearchMcpError("未配置 WEB_SEARCH_MCP_URL")
    http = create_mcp_http_client(headers=_headers())
    async with http:
        async with streamable_http_client(url, http_client=http) as streams:
            read, write = streams
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def call_web_search(query: str) -> Any:
    """只调 bailian_web_search，不把其它 MCP 工具塞进模型。"""
    q = (query or "").strip()
    if not q:
        raise WebSearchMcpError("搜索词为空")
    async with span("tool", TOOL_NAME):
        async with open_web_search_session() as session:
            result = await session.call_tool(TOOL_NAME, {"query": q})
            return _parse_tool_payload(result)

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.config import settings
from app.graph.amap.catalog import tools_for_categories
from app.graph.trace import span


class AmapMcpError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    key = (settings.amap_mcp_key or "").strip()
    if not key:
        raise AmapMcpError("未配置 AMAP_MCP_KEY，无法调用高德 MCP")
    return {"Authorization": f"Bearer {key}"}


def _sse_url(mcp_url: str) -> str:
    url = mcp_url.rstrip("/")
    if url.endswith("/mcp"):
        return url[:-4] + "/sse"
    if url.endswith("/sse"):
        return url
    return url + "/sse"


def _parse_tool_payload(result: Any) -> Any:
    """MCP tools/call 的 content 可能是文本或 JSON 字符串，统一抽成 dict/list。"""
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
        raise AmapMcpError(raw or "高德 MCP 工具调用失败")
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
async def open_amap_session() -> AsyncIterator[Any]:
    """优先 Streamable HTTP（用户给的 /mcp），失败再走百炼文档里的 /sse。"""
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client

    url = (settings.amap_mcp_url or "").strip()
    if not url:
        raise AmapMcpError("未配置 AMAP_MCP_URL")
    headers = _headers()
    errors: list[str] = []

    try:
        http = create_mcp_http_client(headers=headers)
        async with http:
            async with streamable_http_client(url, http_client=http) as streams:
                read, write = streams
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
                    return
    except Exception as exc:
        errors.append(f"streamable-http: {exc}")

    try:
        async with sse_client(_sse_url(url), headers=headers, timeout=30.0) as streams:
            read, write = streams
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
                return
    except Exception as exc:
        errors.append(f"sse: {exc}")

    raise AmapMcpError("高德 MCP 连接失败：" + " | ".join(errors[:2]))


async def call_amap_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """单次开关会话调用一个工具；类别校验在上层做，避免误调未授权专项。"""
    async with span("tool", name):
        async with open_amap_session() as session:
            result = await session.call_tool(name, arguments or {})
            return _parse_tool_payload(result)


async def call_amap_category(
    category: str,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    allowed = set(tools_for_categories((category,)))
    if name not in allowed:
        raise AmapMcpError(f"工具 {name} 不属于 {category} 类别，已拒绝调用")
    return await call_amap_tool(name, arguments)

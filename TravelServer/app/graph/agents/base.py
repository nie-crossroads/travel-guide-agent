from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.jsonutil import parse_json_object
from app.graph.llm import build_llm
from app.graph.memory import message_text, strip_think
from app.graph.state import AgentState

_worker_llm = None


def worker_llm():
    """专项 Agent 共用非流式模型，避免和最终攻略的 token 流混在一起。"""
    global _worker_llm
    if _worker_llm is None:
        _worker_llm = build_llm(temperature=0.3, streaming=False)
    return _worker_llm


def context_block(state: AgentState) -> str:
    summary = (state.get("summary") or "").strip()
    prefs = state.get("preferences") or {}
    dest = state.get("destination") or {}
    hints = state.get("adjustment_hints") or []
    messages = list(state.get("messages") or [])
    latest = ""
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            latest = message_text(message)
            break
    parts = [
        f"压缩记忆：{summary or '无'}",
        f"当前偏好：{prefs or '无'}",
        f"当前目的地：{dest or '无'}",
        f"降级指令：{hints or '无'}",
        f"用户最新消息：{latest or '无'}",
    ]
    return "\n".join(parts)


async def invoke_json(system: str, user: str) -> dict:
    response = await worker_llm().ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return parse_json_object(strip_think(message_text(response)))

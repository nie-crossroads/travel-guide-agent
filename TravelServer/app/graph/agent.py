from __future__ import annotations

import asyncio
import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.db import save_compressed_summary
from app.graph.agents import (
    next_adjustment,
    run_activity,
    run_budget,
    run_destination,
    run_flight,
    run_hotel,
    run_preference,
)
from app.graph.llm import build_llm
from app.graph.memory import (
    build_system_prompt,
    count_state_tokens,
    format_transcript,
    message_text,
    should_compress,
    strip_think,
)
from app.graph.state import AgentState
from app.prompts.travel import COMPOSE_CHAT_PROMPT, COMPOSE_PLAN_PROMPT, COMPRESS_PROMPT

_graph = None
_chat_llm = None
_compress_llm = None


def _get_chat_llm():
    global _chat_llm
    if _chat_llm is None:
        _chat_llm = build_llm(temperature=0.7, streaming=True)
    return _chat_llm


def _get_compress_llm():
    global _compress_llm
    if _compress_llm is None:
        _compress_llm = build_llm(temperature=0.2, streaming=False)
    return _compress_llm


def route_memory(state: AgentState) -> Literal["compress", "preference"]:
    """入口路由：窗口将满则先压缩，否则进入偏好 Agent。"""
    if should_compress(state):
        return "compress"
    return "preference"


def route_intent(state: AgentState) -> Literal["destination", "compose"]:
    if (state.get("intent") or "plan") == "chat":
        return "compose"
    return "destination"


def route_budget(state: AgentState) -> Literal["adjust", "compose"]:
    """超预算且未满 3 轮则降级后重跑并行搜索，否则汇总输出。"""
    budget = state.get("budget") or {}
    if budget.get("within_budget"):
        return "compose"
    if int(state.get("adjustment_round") or 0) >= settings.budget_max_rounds:
        return "compose"
    limit = budget.get("limit") or 0
    if not limit:
        return "compose"
    return "adjust"


def compress_node(state: AgentState) -> dict:
    """把旧消息压成摘要，并用 RemoveMessage 从 checkpointer 中删掉已压缩内容。"""
    messages = list(state.get("messages") or [])
    keep = settings.keep_recent_messages
    if len(messages) <= keep:
        return {
            "compressed": False,
            "token_count": count_state_tokens(state),
        }

    to_compress = messages[:-keep]
    old_summary = (state.get("summary") or "").strip()
    old_summary_block = (
        f"已有摘要：\n{old_summary}" if old_summary else "尚无旧摘要。"
    )
    prompt = COMPRESS_PROMPT.format(
        old_summary=old_summary_block,
        transcript=format_transcript(to_compress),
    )
    response = _get_compress_llm().invoke([HumanMessage(content=prompt)])
    new_summary = strip_think(message_text(response))

    remove_ops = [
        RemoveMessage(id=message.id)
        for message in to_compress
        if getattr(message, "id", None)
    ]
    token_count = count_state_tokens(
        {
            "messages": messages[-keep:],
            "summary": new_summary,
            "token_count": 0,
            "compressed": True,
        }
    )
    return {
        "summary": new_summary,
        "messages": remove_ops,
        "compressed": True,
        "token_count": token_count,
    }


def persist_summary(state: AgentState, config: RunnableConfig) -> dict:
    """把压缩摘要额外写入会话表，满足「压缩后保存」，便于列表页展示记忆。"""
    thread_id = (config.get("configurable") or {}).get("thread_id")
    if thread_id and state.get("compressed"):
        save_compressed_summary(
            thread_id,
            state.get("summary") or "",
            int(state.get("token_count") or 0),
        )
    return {}


async def preference_node(state: AgentState) -> dict:
    return await run_preference(state)


async def destination_node(state: AgentState) -> dict:
    return await run_destination(state)


async def parallel_search_node(state: AgentState) -> dict:
    """航班 / 酒店 / 活动互不依赖，并行执行以降低等待时间。"""
    results = await asyncio.gather(
        run_flight(state),
        run_hotel(state),
        run_activity(state),
        return_exceptions=True,
    )
    names = ("flights", "hotels", "activities")
    payload: dict = {"progress": "并行搜索：航班 / 酒店 / 活动已完成"}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            payload[name] = {"total": 0, "note": str(result)}
        else:
            payload[name] = result
    return payload


def budget_node(state: AgentState) -> dict:
    return run_budget(state)


def adjust_node(state: AgentState) -> dict:
    return next_adjustment(state)


def _plan_context(state: AgentState) -> str:
    blob = {
        "preferences": state.get("preferences") or {},
        "destination": state.get("destination") or {},
        "flights": state.get("flights") or {},
        "hotels": state.get("hotels") or {},
        "activities": state.get("activities") or {},
        "budget": state.get("budget") or {},
        "adjustment_round": state.get("adjustment_round") or 0,
    }
    return json.dumps(blob, ensure_ascii=False, indent=2)


def build_confirm_tail(state: AgentState) -> str:
    """确认引导固定贴在回复最末尾，避免模型把追问插在正文中间。"""
    prefs = state.get("preferences") or {}
    dest = (state.get("destination") or {}).get("city") or prefs.get("destination_hint") or "当前目的地"
    days = prefs.get("days") or "未定"
    budget = prefs.get("budget") or 0
    budget_text = f"{int(budget)} 元" if budget else "预算未定"
    missing = [str(item).strip() for item in (prefs.get("missing") or []) if str(item).strip()]
    extra = f"\n另外请一并确认：{'、'.join(missing[:3])}。" if missing else ""
    return (
        "\n\n---\n\n## 请确认\n\n"
        f"以上按 **{dest} · {days} 天 · {budget_text}** 给出。"
        f"{extra}\n\n"
        "请直接回复：\n"
        "- 「确认，按这个走」\n"
        "- 或告诉我要改哪一块（目的地 / 天数 / 预算 / 住宿 / 某一天行程）\n"
    )


def ensure_confirm_tail(text: str, state: AgentState) -> str:
    """若模型已在文末写了确认节，先裁掉再统一追加，保证引导永远在最后。"""
    body = strip_think(text or "").rstrip()
    for marker in ("\n## 请确认", "\n### 请确认", "\n请确认"):
        idx = body.rfind(marker)
        if idx >= 0 and idx > len(body) * 0.35:
            body = body[:idx].rstrip()
            break
    return body + build_confirm_tail(state)


async def compose_node(state: AgentState) -> dict:
    """汇总各 Agent 结果并流式写出 Markdown 攻略。"""
    intent = state.get("intent") or "plan"
    system = COMPOSE_CHAT_PROMPT if intent == "chat" else COMPOSE_PLAN_PROMPT
    system = (
        build_system_prompt(state.get("summary") or "")
        + "\n\n"
        + system
        + "\n\n规划 JSON：\n"
        + _plan_context(state)
    )
    llm_messages = [SystemMessage(content=system), *list(state.get("messages") or [])]
    full = None
    async for chunk in _get_chat_llm().astream(llm_messages):
        full = chunk if full is None else full + chunk
    if full is None:
        full = await _get_chat_llm().ainvoke(llm_messages)
    response = AIMessage(content=ensure_confirm_tail(message_text(full), state))
    token_count = count_state_tokens(state, extra_messages=[response])
    return {
        "messages": [response],
        "token_count": token_count,
        "compressed": bool(state.get("compressed")),
        "progress": "",
    }


def build_graph(checkpointer):
    """记忆压缩后走 6 Agent：偏好→目的地→并行搜索→预算循环→汇总。"""
    workflow = StateGraph(AgentState)
    workflow.add_node("compress", compress_node)
    workflow.add_node("persist_summary", persist_summary)
    workflow.add_node("preference", preference_node)
    workflow.add_node("destination", destination_node)
    workflow.add_node("parallel_search", parallel_search_node)
    workflow.add_node("budget", budget_node)
    workflow.add_node("adjust", adjust_node)
    workflow.add_node("compose", compose_node)
    workflow.add_conditional_edges(
        START,
        route_memory,
        {"compress": "compress", "preference": "preference"},
    )
    workflow.add_edge("compress", "persist_summary")
    workflow.add_edge("persist_summary", "preference")
    workflow.add_conditional_edges(
        "preference",
        route_intent,
        {"destination": "destination", "compose": "compose"},
    )
    workflow.add_edge("destination", "parallel_search")
    workflow.add_edge("parallel_search", "budget")
    workflow.add_conditional_edges(
        "budget",
        route_budget,
        {"adjust": "adjust", "compose": "compose"},
    )
    workflow.add_edge("adjust", "parallel_search")
    workflow.add_edge("compose", END)
    return workflow.compile(checkpointer=checkpointer)


def set_graph(graph) -> None:
    global _graph
    _graph = graph


def get_graph():
    if _graph is None:
        raise RuntimeError("旅行顾问图尚未初始化")
    return _graph

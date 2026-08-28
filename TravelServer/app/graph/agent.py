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
    next_adjust_step,
    next_adjustment,
    run_activity,
    run_budget,
    run_destination,
    run_flight,
    run_hotel,
    run_maps_route,
    run_preference,
    run_weather,
)
from app.graph.scope import needed_list, needed_set, needs_search
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


def route_after_preference(
    state: AgentState,
) -> Literal["destination", "parallel_search", "weather", "maps_route", "budget", "compose"]:
    """Preference 之后按 needed_agents 走最小路径，不问的专项直接跳过。"""
    needed = needed_set(state)
    if "destination" in needed:
        return "destination"
    if needs_search(state):
        return "parallel_search"
    if "weather" in needed:
        return "weather"
    if "maps_route" in needed:
        return "maps_route"
    if "budget" in needed:
        return "budget"
    return "compose"


def route_after_destination(
    state: AgentState,
) -> Literal["parallel_search", "weather", "maps_route", "budget", "compose"]:
    if needs_search(state):
        return "parallel_search"
    if "weather" in needed_set(state):
        return "weather"
    if "maps_route" in needed_set(state):
        return "maps_route"
    if "budget" in needed_set(state):
        return "budget"
    return "compose"


def route_after_search(
    state: AgentState,
) -> Literal["weather", "maps_route", "budget", "compose"]:
    if "weather" in needed_set(state):
        return "weather"
    if "maps_route" in needed_set(state):
        return "maps_route"
    if "budget" in needed_set(state):
        return "budget"
    return "compose"


def route_after_weather(
    state: AgentState,
) -> Literal["maps_route", "budget", "compose"]:
    if "maps_route" in needed_set(state):
        return "maps_route"
    if "budget" in needed_set(state):
        return "budget"
    return "compose"


def route_after_maps_route(state: AgentState) -> Literal["budget", "compose"]:
    if "budget" in needed_set(state):
        return "budget"
    return "compose"


def route_budget(state: AgentState) -> Literal["adjust", "compose"]:
    """超预算且本轮跑过可降级专项、未满 3 轮时才重搜，否则汇总输出。"""
    if "budget" not in needed_set(state):
        return "compose"
    budget = state.get("budget") or {}
    if budget.get("within_budget"):
        return "compose"
    if int(state.get("adjustment_round") or 0) >= settings.budget_max_rounds:
        return "compose"
    limit = budget.get("limit") or 0
    if not limit:
        return "compose"
    if not next_adjust_step(state):
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


async def weather_node(state: AgentState) -> dict:
    return await run_weather(state)


async def maps_route_node(state: AgentState) -> dict:
    return await run_maps_route(state)


async def parallel_search_node(state: AgentState) -> dict:
    """只跑本轮需要的航班 / 酒店 / 活动；互不依赖时并行以降低等待。"""
    needed = needed_set(state)
    jobs: list[tuple[str, object]] = []
    mapping = (
        ("flight", "flights", "航班", run_flight),
        ("hotel", "hotels", "酒店", run_hotel),
        ("activity", "activities", "活动", run_activity),
    )
    for agent, field, _label, runner in mapping:
        if agent in needed:
            jobs.append((field, runner(state)))
    if not jobs:
        return {"progress": ""}
    names = [name for name, _coro in jobs]
    results = await asyncio.gather(
        *[coro for _name, coro in jobs],
        return_exceptions=True,
    )
    labels = {"flights": "航班", "hotels": "酒店", "activities": "活动"}
    done = " / ".join(labels[name] for name in names)
    payload: dict = {"progress": f"专项搜索：{done}已完成"}
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
    """只把本轮 needed_agents 的结果交给汇总，避免上一轮机票酒店漏进景点问答。"""
    needed = needed_list(state)
    blob: dict = {
        "needed_agents": needed,
        "preferences": state.get("preferences") or {},
    }
    field_by_agent = {
        "destination": "destination",
        "flight": "flights",
        "hotel": "hotels",
        "activity": "activities",
        "budget": "budget",
        "weather": "weather",
        "maps_route": "maps_route",
    }
    for agent, field in field_by_agent.items():
        if agent in needed:
            blob[field] = state.get(field) or {}
    if "budget" in needed:
        blob["adjustment_round"] = state.get("adjustment_round") or 0
    return json.dumps(blob, ensure_ascii=False, indent=2)


def build_confirm_tail(state: AgentState) -> str:
    """确认引导固定贴在回复最末尾；内容跟本轮问的专项对齐，不假装已经排好行程。"""
    needed = needed_set(state)
    prefs = state.get("preferences") or {}
    dest = (
        (state.get("destination") or {}).get("city")
        or prefs.get("destination_hint")
        or "这里"
    )
    missing = [str(item).strip() for item in (prefs.get("missing") or []) if str(item).strip()]
    extra = f"\n另外请一并确认：{'、'.join(missing[:3])}。" if missing else ""
    if not needed:
        return (
            "\n\n---\n\n## 请确认\n\n"
            "如果还需要排行程、找住宿或查交通，直接告诉我。\n"
        )
    if needed <= {"weather"}:
        return (
            "\n\n---\n\n## 请确认\n\n"
            f"以上是 **{dest}** 的天气，没有安排行程。{extra}\n\n"
            "请直接回复：\n"
            "- 「确认，知道了」\n"
            "- 或告诉我还要推荐景点 / 排行程 / 查路线\n"
        )
    if needed <= {"maps_route"}:
        return (
            "\n\n---\n\n## 请确认\n\n"
            f"以上是本轮路线，没有安排住宿和机票。{extra}\n\n"
            "请直接回复：\n"
            "- 「确认，按这条走」\n"
            "- 或告诉我要改起点、终点或出行方式\n"
        )
    if needed <= {"destination"}:
        return (
            "\n\n---\n\n## 请确认\n\n"
            f"以上是 **{dest}** 的推荐，没有安排行程、酒店和机票。{extra}\n\n"
            "请直接回复：\n"
            "- 「确认，就这些地方」\n"
            "- 或告诉我还要排几天行程 / 找住宿 / 查交通\n"
        )
    offers = []
    if "activity" not in needed:
        offers.append("排几天行程")
    if "hotel" not in needed:
        offers.append("找住宿")
    if "flight" not in needed:
        offers.append("查交通")
    if "weather" not in needed:
        offers.append("查天气")
    if "maps_route" not in needed:
        offers.append("规划市内路线")
    days = prefs.get("days") or "未定"
    budget = prefs.get("budget") or 0
    budget_text = f"{int(budget)} 元" if budget else "预算未定"
    scope_bits = []
    if "destination" in needed or dest != "这里":
        scope_bits.append(str(dest))
    if "activity" in needed:
        scope_bits.append(f"{days} 天")
    if "budget" in needed:
        scope_bits.append(budget_text)
    scope = " · ".join(scope_bits) if scope_bits else dest
    more = f"\n也可以继续让我帮你{' / '.join(offers)}。" if offers else ""
    return (
        "\n\n---\n\n## 请确认\n\n"
        f"以上按 **{scope}** 给出。{extra}{more}\n\n"
        "请直接回复：\n"
        "- 「确认，按这个走」\n"
        "- 或告诉我要改哪一块\n"
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
    """按本轮 needed_agents 汇总；没跑专项时走闲聊提示，避免写成完整攻略。"""
    needed = needed_list(state)
    system = COMPOSE_CHAT_PROMPT if not needed else COMPOSE_PLAN_PROMPT
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
    """压缩后先走 Preference，再按 needed_agents 按需进入目的地 / 搜索 / 预算 / 汇总。"""
    workflow = StateGraph(AgentState)
    workflow.add_node("compress", compress_node)
    workflow.add_node("persist_summary", persist_summary)
    workflow.add_node("preference", preference_node)
    workflow.add_node("destination", destination_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("maps_route", maps_route_node)
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
        route_after_preference,
        {
            "destination": "destination",
            "parallel_search": "parallel_search",
            "weather": "weather",
            "maps_route": "maps_route",
            "budget": "budget",
            "compose": "compose",
        },
    )
    workflow.add_conditional_edges(
        "destination",
        route_after_destination,
        {
            "parallel_search": "parallel_search",
            "weather": "weather",
            "maps_route": "maps_route",
            "budget": "budget",
            "compose": "compose",
        },
    )
    workflow.add_conditional_edges(
        "parallel_search",
        route_after_search,
        {
            "weather": "weather",
            "maps_route": "maps_route",
            "budget": "budget",
            "compose": "compose",
        },
    )
    workflow.add_conditional_edges(
        "weather",
        route_after_weather,
        {
            "maps_route": "maps_route",
            "budget": "budget",
            "compose": "compose",
        },
    )
    workflow.add_conditional_edges(
        "maps_route",
        route_after_maps_route,
        {"budget": "budget", "compose": "compose"},
    )
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

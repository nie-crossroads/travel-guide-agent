from __future__ import annotations

from app.graph.memory import message_text
from app.graph.state import AgentState

SPECIALISTS = (
    "destination",
    "flight",
    "hotel",
    "activity",
    "budget",
    "weather",
    "maps_route",
)
SEARCH_AGENTS = ("flight", "hotel", "activity")

# 问景点时模型常扩成完整攻略；这些词说明本轮只想听地方，不该带行程/住宿
_NARROW_PLACE = ("好玩", "景点", "必去", "打卡", "值得去", "推荐哪些地方", "有哪些地方")
_WANTS_MORE = (
    "行程",
    "攻略",
    "规划",
    "几天",
    "酒店",
    "住宿",
    "机票",
    "航班",
    "怎么去",
    "预算",
    "怎么玩",
    "安排",
)
_WEATHER = ("天气", "气温", "下雨", "降雨", "穿什么", "预报", "冷不冷", "热不热", "伞")
_ROUTE = ("怎么走", "路线", "导航", "打车", "地铁怎么", "公交怎么", "怎么过去")


def latest_user_text(state: AgentState) -> str:
    for message in reversed(list(state.get("messages") or [])):
        if getattr(message, "type", "") == "human":
            return message_text(message).strip()
    return ""


def normalize_needed(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        name = str(item or "").strip().lower()
        if name in SPECIALISTS and name not in seen:
            seen.append(name)
    return seen


def clamp_needed(user_text: str, needed: list[str]) -> list[str]:
    """按本轮话术收束 Agent；天气/路线另开专项，避免被扩成完整攻略。"""
    text = (user_text or "").strip()
    if not text:
        return needed
    wants_weather = any(key in text for key in _WEATHER)
    wants_route = any(key in text for key in _ROUTE) and "机票" not in text and "航班" not in text
    wants_place = any(key in text for key in _NARROW_PLACE)
    wants_more = any(key in text for key in _WANTS_MORE)

    if wants_weather and not wants_place and not wants_more and not wants_route:
        return ["weather"]
    if wants_route and not wants_place and not wants_weather:
        return ["maps_route"]
    if wants_place and not wants_more:
        needed = ["destination"]
    else:
        needed_set = set(needed)
        if {"flight", "hotel", "activity"} <= needed_set and "budget" not in needed_set:
            needed = [*needed, "budget"]

    extra: list[str] = []
    if wants_weather:
        extra.append("weather")
    if wants_route:
        extra.append("maps_route")
    for item in extra:
        if item not in needed:
            needed.append(item)
    return needed


def needed_list(state: AgentState) -> list[str]:
    return normalize_needed(state.get("needed_agents") or [])


def needed_set(state: AgentState) -> set[str]:
    return set(needed_list(state))


def needs_search(state: AgentState) -> bool:
    return bool(needed_set(state) & set(SEARCH_AGENTS))

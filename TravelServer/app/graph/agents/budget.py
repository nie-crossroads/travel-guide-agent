from __future__ import annotations

from app.graph.jsonutil import as_number
from app.graph.state import AgentState

# 与参考项目一致：活动 → 酒店 → 航班，用户对活动降级感知最小
ADJUST_STEPS = (
    "cut_activity_up_to_40_percent",
    "downgrade_hotel_up_to_35_percent",
    "switch_to_economy_flight_up_to_25_percent",
)


def run_budget(state: AgentState) -> dict:
    """用各 Agent 报出的数字做硬校验，避免再让模型口算导致循环抖动。"""
    prefs = state.get("preferences") or {}
    limit = as_number(prefs.get("budget"))
    flight_cost = as_number((state.get("flights") or {}).get("total"))
    hotel_cost = as_number((state.get("hotels") or {}).get("total"))
    activity_cost = as_number((state.get("activities") or {}).get("total"))
    total = flight_cost + hotel_cost + activity_cost
    within = True if limit <= 0 else total <= limit + 1
    over_amount = 0.0 if within or limit <= 0 else round(total - limit, 2)
    round_no = int(state.get("adjustment_round") or 0)
    return {
        "budget": {
            "limit": int(limit),
            "flight_cost": int(flight_cost),
            "hotel_cost": int(hotel_cost),
            "activity_cost": int(activity_cost),
            "total": int(total),
            "within_budget": within,
            "over_amount": int(over_amount),
            "adjustment_round": round_no,
        },
        "progress": (
            "预算 Agent：当前方案在预算内"
            if within
            else f"预算 Agent：超支约 {int(over_amount)} 元"
        ),
    }


def next_adjustment(state: AgentState) -> dict:
    """渐进式降级：每轮只动一个开支维度，最多 3 轮。"""
    round_no = int(state.get("adjustment_round") or 0) + 1
    hints = list(state.get("adjustment_hints") or [])
    index = min(round_no - 1, len(ADJUST_STEPS) - 1)
    hint = ADJUST_STEPS[index]
    if hint not in hints:
        hints.append(hint)
    labels = {
        "cut_activity_up_to_40_percent": "第 1 轮：压缩活动花费",
        "downgrade_hotel_up_to_35_percent": "第 2 轮：下调住宿档位",
        "switch_to_economy_flight_up_to_25_percent": "第 3 轮：改经济舱航班",
    }
    return {
        "adjustment_round": round_no,
        "adjustment_hints": hints,
        "progress": f"预算循环：{labels.get(hint, hint)}",
    }

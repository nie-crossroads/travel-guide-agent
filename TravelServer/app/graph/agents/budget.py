from __future__ import annotations

from app.graph.jsonutil import as_number
from app.graph.scope import needed_set
from app.graph.state import AgentState
from app.graph.trace import traced

# 与参考项目一致：活动 → 酒店 → 航班，用户对活动降级感知最小
ADJUST_STEPS = (
    "cut_activity_up_to_40_percent",
    "downgrade_hotel_up_to_35_percent",
    "switch_to_economy_flight_up_to_25_percent",
)
STEP_AGENT = {
    "cut_activity_up_to_40_percent": "activity",
    "downgrade_hotel_up_to_35_percent": "hotel",
    "switch_to_economy_flight_up_to_25_percent": "flight",
}


def next_adjust_step(state: AgentState) -> str | None:
    """只对「本轮实际跑过」的开支项降级，跳过用户没问的航班/酒店/活动。"""
    needed = needed_set(state)
    used = set(state.get("adjustment_hints") or [])
    for step in ADJUST_STEPS:
        if step in used:
            continue
        agent = STEP_AGENT[step]
        if needed and agent not in needed:
            continue
        return step
    return None


@traced("agent", "budget")
def run_budget(state: AgentState) -> dict:
    """用本轮跑过的专项数字做硬校验，不把上一轮没问的机票酒店算进总价。"""
    prefs = state.get("preferences") or {}
    needed = needed_set(state)
    limit = as_number(prefs.get("budget"))
    flight_cost = (
        as_number((state.get("flights") or {}).get("total")) if "flight" in needed else 0
    )
    hotel_cost = (
        as_number((state.get("hotels") or {}).get("total")) if "hotel" in needed else 0
    )
    activity_cost = (
        as_number((state.get("activities") or {}).get("total")) if "activity" in needed else 0
    )
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


@traced("agent", "adjust")
def next_adjustment(state: AgentState) -> dict:
    """渐进式降级：每轮只动一个开支维度，最多 3 轮。"""
    hint = next_adjust_step(state)
    if not hint:
        return {"progress": "预算循环：没有可再降级的专项"}
    round_no = int(state.get("adjustment_round") or 0) + 1
    hints = list(state.get("adjustment_hints") or [])
    if hint not in hints:
        hints.append(hint)
    labels = {
        "cut_activity_up_to_40_percent": "压缩活动花费",
        "downgrade_hotel_up_to_35_percent": "下调住宿档位",
        "switch_to_economy_flight_up_to_25_percent": "改经济舱航班",
    }
    return {
        "adjustment_round": round_no,
        "adjustment_hints": hints,
        "progress": f"预算循环：{labels.get(hint, hint)}",
    }

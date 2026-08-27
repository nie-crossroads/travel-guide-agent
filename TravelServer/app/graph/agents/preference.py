from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.state import AgentState

SYSTEM = """你是 Preference Agent，只负责从对话里整理出行偏好。
只输出 JSON，不要 Markdown。字段：
{
  "intent": "plan 或 chat",
  "departure": "出发城市，未知则空字符串",
  "destination_hint": "用户点名的目的地，未知则空",
  "start_date": "出发日期或季节，未知则空",
  "days": 3,
  "travelers": 2,
  "budget": 0,
  "style": "budget/comfort/luxury/family/outdoor 之一",
  "interests": ["美食"],
  "notes": "禁忌或特殊需求",
  "missing": ["还缺的关键信息"]
}
intent=plan：用户在要行程/攻略/改预算改目的地。
intent=chat：追问、闲聊、解释已有方案。
数字未知用合理默认：days=3, travelers=2, budget=0 表示未给预算。
必须合并已有偏好，不要丢掉用户早就确认过的信息。
"""


async def run_preference(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state))
    previous = dict(state.get("preferences") or {})
    previous.update({key: value for key, value in data.items() if value not in ("", None, [])})
    intent = data.get("intent") or "plan"
    if not previous.get("days"):
        previous["days"] = 3
    if not previous.get("travelers"):
        previous["travelers"] = 2
    result: dict = {
        "preferences": previous,
        "intent": intent,
        "progress": "偏好 Agent：已整理出行约束",
    }
    if intent == "plan":
        # 新一轮规划从第 0 轮开始，避免沿用上次预算循环的降级指令
        result["adjustment_round"] = 0
        result["adjustment_hints"] = []
    return result

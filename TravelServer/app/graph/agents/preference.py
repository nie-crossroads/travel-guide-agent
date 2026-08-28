from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.scope import clamp_needed, latest_user_text, normalize_needed
from app.graph.state import AgentState

SYSTEM = """你是 Preference Agent，只负责从对话里整理出行偏好，并判断本轮要调用哪些专项 Agent。
只输出 JSON，不要 Markdown。字段：
{
  "intent": "plan 或 chat",
  "needed_agents": ["destination"],
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

needed_agents 只能从 destination / flight / hotel / activity / budget / weather / maps_route 中选，必须是本轮问题的最小集合：
- 「成都有哪些好玩的地方 / 推荐景点 / 必去打卡」→ ["destination"]，不要带 flight/hotel/activity/budget/weather
- 「成都天气怎么样 / 会不会下雨 / 穿什么」→ ["weather"]，不要排行程
- 「从宽窄巷子怎么去大熊猫基地 / 市内路线 / 导航 / 打车」→ ["maps_route"]
- 「三天怎么玩 / 排行程 / 逐日安排」→ ["destination", "activity"]
- 「住哪 / 酒店推荐」→ ["destination", "hotel"]；目的地已确定则可只给 ["hotel"]
- 「机票 / 航班」→ ["destination", "flight"]
- 「完整攻略 / 帮我规划一趟旅行」需要交通+住宿+行程 → ["destination","flight","hotel","activity","budget"]
- 「这个方案为什么 / 确认 / 闲聊 / 解释」→ intent=chat，needed_agents=[]

intent=plan：本轮需要专项 Agent 产出新内容。
intent=chat：追问、闲聊、解释已有方案，不跑专项。
不要因为用户提了城市就自动规划机票、酒店、逐日行程或查天气。
用户已指定城市时不要改城市。
数字未知：不要编造预算；days/travelers 仅在需要行程或住宿时给默认 3 天 / 2 人。
必须合并已有偏好，不要丢掉用户早就确认过的信息。
"""


async def run_preference(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state))
    previous = dict(state.get("preferences") or {})
    previous.update({key: value for key, value in data.items() if value not in ("", None, [])})
    previous.pop("needed_agents", None)
    previous.pop("intent", None)

    intent = data.get("intent") or "plan"
    needed = clamp_needed(latest_user_text(state), normalize_needed(data.get("needed_agents")))
    if intent == "chat" and not needed:
        needed = []
    elif intent != "chat" and not needed:
        # 模型漏填时宁可不跑全图，只整理目的地
        needed = ["destination"]
        intent = "plan"

    search_needed = bool(set(needed) & {"flight", "hotel", "activity", "budget"})
    if search_needed:
        if not previous.get("days"):
            previous["days"] = 3
        if not previous.get("travelers"):
            previous["travelers"] = 2

    result: dict = {
        "preferences": previous,
        "intent": intent,
        "needed_agents": needed,
        "progress": (
            "偏好 Agent：闲聊直出"
            if not needed
            else f"偏好 Agent：本轮调用 {' / '.join(needed)}"
        ),
    }
    if needed:
        # 新一轮规划从第 0 轮开始，避免沿用上次预算循环的降级指令
        result["adjustment_round"] = 0
        result["adjustment_hints"] = []
    return result

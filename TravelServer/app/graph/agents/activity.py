from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.jsonutil import as_number
from app.graph.state import AgentState
from app.graph.trace import traced

SYSTEM = """你是 Activity Agent，按天排上午/下午/晚上的活动，控制时间和花费。
只输出 JSON：
{
  "days": [
    {
      "label": "D1",
      "theme": "到店+核心区",
      "items": [
        {"slot": "morning", "name": "", "hours": 3, "cost": 0}
      ]
    }
  ],
  "total": 0,
  "note": "预约或避坑"
}
天数必须覆盖 preferences.days。cost 为人民币人均或团队总价，与偏好人数一致并在 note 说明。
若降级指令要求砍活动，优先换成免费/低价项目，总活动花费大约下降最多 40%。
"""


@traced("agent", "activity")
async def run_activity(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state))
    days = data.get("days") or []
    computed = 0.0
    for day in days:
        for item in day.get("items") or []:
            computed += as_number(item.get("cost"))
    data["total"] = int(as_number(data.get("total")) or computed)
    return data

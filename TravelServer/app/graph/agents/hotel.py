from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.jsonutil import as_number
from app.graph.state import AgentState
from app.graph.trace import traced

SYSTEM = """你是 Hotel Agent，按旅行风格匹配住宿。
只输出 JSON：
{
  "name": "酒店名",
  "stars": 4,
  "area": "区位",
  "nightly": 0,
  "nights": 2,
  "total": 0,
  "style_fit": "为何匹配",
  "note": "含早/交通提醒"
}
nights 默认 days-1。价格人民币。
若降级指令要求降酒店等级，总价大约下降最多 35%，可换成更经济但仍干净安全的选择。
"""


@traced("agent", "hotel")
async def run_hotel(state: AgentState) -> dict:
    prefs = state.get("preferences") or {}
    days = int(as_number(prefs.get("days"), 3))
    data = await invoke_json(SYSTEM, context_block(state) + f"\n默认入住晚数：{max(days - 1, 1)}")
    nights = int(as_number(data.get("nights"), max(days - 1, 1)))
    nightly = as_number(data.get("nightly"))
    total = as_number(data.get("total")) or nightly * nights
    data["nights"] = nights
    data["total"] = int(total)
    return data

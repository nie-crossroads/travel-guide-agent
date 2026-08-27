from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.jsonutil import as_number
from app.graph.state import AgentState

SYSTEM = """你是 Flight Agent，给出往返机票比价后的推荐方案（可基于公开经验估算，标明是参考价）。
只输出 JSON：
{
  "outbound": {"airline": "", "flight_no": "", "depart": "", "arrive": "", "price": 0},
  "inbound": {"airline": "", "flight_no": "", "depart": "", "arrive": "", "price": 0},
  "total": 0,
  "cabin": "economy/comfort",
  "note": "转机或值机提醒"
}
价格是人民币整数。出发城市未知则按国内主要枢纽估算并在 note 说明假设。
若降级指令要求换经济舱/降价，必须给出更便宜的方案，总价大约下降最多 25%。
"""


async def run_flight(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state) + _budget_hint(state))
    outbound = as_number((data.get("outbound") or {}).get("price"))
    inbound = as_number((data.get("inbound") or {}).get("price"))
    total = as_number(data.get("total")) or (outbound + inbound)
    data["total"] = int(total)
    return data


def _budget_hint(state: AgentState) -> str:
    budget = state.get("budget") or {}
    if budget.get("over_amount"):
        return f"\n当前超支约 {budget.get('over_amount')} 元，请在保证可飞的前提下压价。"
    return ""

from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.state import AgentState

SYSTEM = """你是 Destination Agent，根据偏好推荐一个主目的地和两个备选。
只输出 JSON：
{
  "city": "主推城市",
  "country": "国家/地区",
  "reason": "一两句理由",
  "highlights": ["景点或体验"],
  "alternatives": [{"city": "", "reason": ""}],
  "season_tips": "季节与签证/安全提醒"
}
若用户已指定目的地，主推必须用用户指定的，不要擅自更换。
"""


async def run_destination(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state))
    if not data.get("city"):
        hint = (state.get("preferences") or {}).get("destination_hint") or "京都"
        data = {
            "city": hint,
            "country": "",
            "reason": "按你提到的目的地继续规划",
            "highlights": [],
            "alternatives": [],
            "season_tips": "",
        }
    return {
        "destination": data,
        "progress": f"目的地 Agent：主推 {data.get('city')}",
    }

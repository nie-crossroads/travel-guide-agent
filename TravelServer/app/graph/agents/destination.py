from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.amap.client import AmapMcpError, call_amap_category
from app.graph.amap.parse import extract_pois
from app.graph.state import AgentState

SYSTEM = """你是 Destination Agent，根据偏好推荐一个主目的地和两个备选。
只输出 JSON：
{
  "city": "主推城市",
  "country": "国家/地区",
  "reason": "一两句理由",
  "highlights": ["景点名：一句话为什么值得去"],
  "alternatives": [{"city": "", "reason": ""}],
  "season_tips": "季节与签证/安全提醒",
  "poi_keywords": "高德搜索关键词，问景点用景点，问美食用美食"
}
若用户已指定目的地，主推必须用用户指定的，不要擅自更换。
若用户在问好玩的地方 / 景点 / 打卡，highlights 列出 8–12 个具体地点（含片区和一句理由），不要规划逐日行程、酒店、机票。
poi_keywords 默认「景点」。
"""


async def run_destination(state: AgentState) -> dict:
    data = await invoke_json(SYSTEM, context_block(state))
    if not data.get("city"):
        hint = (state.get("preferences") or {}).get("destination_hint") or "京都"
        data = {
            "city": hint,
            "country": "",
            "reason": "按你提到的目的地继续",
            "highlights": [],
            "alternatives": [],
            "season_tips": "",
            "poi_keywords": "景点",
        }
    city = str(data.get("city") or "").strip()
    keywords = str(data.get("poi_keywords") or "景点").strip() or "景点"
    # 目的地节点已经在跑，这时才调 POI 类别，不顺手查天气或路线
    try:
        payload = await call_amap_category(
            "poi",
            "maps_text_search",
            {"keywords": keywords, "city": city},
        )
        pois = extract_pois(payload, 10)
        if pois:
            data["highlights"] = [
                f"{item['name']}：{item['address'] or '当地热门地点'}" for item in pois
            ]
            data["amap_pois"] = pois
            data["poi_source"] = "amap"
    except AmapMcpError:
        data["poi_source"] = "llm"
    return {
        "destination": data,
        "progress": f"目的地 Agent：主推 {city}",
    }

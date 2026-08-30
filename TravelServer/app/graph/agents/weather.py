from __future__ import annotations

from app.graph.amap.client import AmapMcpError, call_amap_category
from app.graph.amap.parse import extract_forecasts
from app.graph.state import AgentState
from app.graph.trace import traced


def _city(state: AgentState) -> str:
    dest = state.get("destination") or {}
    prefs = state.get("preferences") or {}
    return str(dest.get("city") or prefs.get("destination_hint") or "").strip()


@traced("agent", "weather")
async def run_weather(state: AgentState) -> dict:
    """只调 weather 类别的 maps_weather，不顺手搜景点或路线。"""
    city = _city(state)
    if not city:
        return {
            "weather": {"city": "", "forecasts": [], "note": "还不知道查哪个城市的天气"},
            "progress": "天气 Agent：缺少城市",
        }
    try:
        payload = await call_amap_category("weather", "maps_weather", {"city": city})
        forecasts = extract_forecasts(payload)
        note = "" if forecasts else "高德未返回预报，请稍后再试"
        return {
            "weather": {
                "city": city,
                "forecasts": forecasts[:7],
                "source": "amap",
                "note": note,
            },
            "progress": f"天气 Agent：已查询 {city}",
        }
    except AmapMcpError as exc:
        return {
            "weather": {"city": city, "forecasts": [], "source": "amap", "note": str(exc)},
            "progress": f"天气 Agent：{city} 查询失败",
        }

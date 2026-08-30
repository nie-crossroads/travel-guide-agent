from __future__ import annotations

from app.graph.agents.base import context_block, invoke_json
from app.graph.amap.catalog import ROUTE_MODE_TOOLS
from app.graph.amap.client import AmapMcpError, call_amap_category
from app.graph.amap.parse import first_city, first_location, is_lnglat
from app.graph.state import AgentState
from app.graph.trace import traced

SYSTEM = """你是市内出行路线 Agent。根据用户本轮问题选出起终点和交通方式。
只输出 JSON：
{
  "origin": "起点地址或地标",
  "destination": "终点地址或地标",
  "city": "主要城市",
  "cityd": "终点城市，同城可与 city 相同",
  "mode": "walking / bicycling / driving / transit 之一"
}
未知字段用空字符串。mode 默认 transit。不要规划机票。
"""


async def _geocode(address: str, city: str) -> tuple[str, str]:
    """返回 (lnglat, city)。坐标解析失败时不要把中文地址传给路径规划。"""
    if not address:
        return "", city
    data = await call_amap_category("geocode", "maps_geo", {"address": address, "city": city})
    loc = first_location(data)
    resolved_city = first_city(data) or city
    return loc, resolved_city


@traced("agent", "maps_route")
async def run_maps_route(state: AgentState) -> dict:
    """只调 geocode + 对应一种路径规划工具，不查天气、不搜景点。"""
    plan = await invoke_json(SYSTEM, context_block(state))
    origin = str(plan.get("origin") or "").strip()
    dest = str(plan.get("destination") or "").strip()
    city = str(plan.get("city") or (state.get("preferences") or {}).get("destination_hint") or "").strip()
    cityd = str(plan.get("cityd") or city).strip()
    mode = str(plan.get("mode") or "transit").strip().lower()
    tool = ROUTE_MODE_TOOLS.get(mode, ROUTE_MODE_TOOLS["transit"])
    if not origin or not dest:
        return {
            "maps_route": {
                "origin": origin,
                "destination": dest,
                "mode": mode,
                "note": "还缺起点或终点，无法规划路线",
            },
            "progress": "路线 Agent：缺少起终点",
        }
    try:
        origin_loc, origin_city = await _geocode(origin, city)
        dest_loc, dest_city = await _geocode(dest, cityd or city)
        city = origin_city or city
        cityd = dest_city or cityd or city
        if not is_lnglat(origin_loc) or not is_lnglat(dest_loc):
            return {
                "maps_route": {
                    "origin": origin,
                    "destination": dest,
                    "mode": mode,
                    "note": "起终点无法解析成经纬度，未调用路径规划，避免高德返回参数错误",
                },
                "progress": "路线 Agent：坐标解析失败",
            }
        args = {"origin": origin_loc, "destination": dest_loc}
        if tool == "maps_direction_transit_integrated":
            # 公交接口 city/cityd 必填，且 origin/destination 必须是「经度,纬度」
            if not city or not cityd:
                return {
                    "maps_route": {
                        "origin": origin,
                        "destination": dest,
                        "origin_location": origin_loc,
                        "destination_location": dest_loc,
                        "mode": mode,
                        "note": "公交规划缺少起点或终点城市",
                    },
                    "progress": "路线 Agent：缺少城市",
                }
            args["city"] = city
            args["cityd"] = cityd
        payload = await call_amap_category("route", tool, args)
        return {
            "maps_route": {
                "origin": origin,
                "destination": dest,
                "origin_location": origin_loc,
                "destination_location": dest_loc,
                "mode": mode,
                "tool": tool,
                "result": payload,
                "source": "amap",
            },
            "progress": f"路线 Agent：{mode} {origin} → {dest}",
        }
    except AmapMcpError as exc:
        return {
            "maps_route": {
                "origin": origin,
                "destination": dest,
                "mode": mode,
                "source": "amap",
                "note": str(exc),
            },
            "progress": "路线 Agent：规划失败",
        }

"""把高德 MCP 工具分成互斥类别，图里只按本轮 needed 去调，避免 12+ 个工具全塞进模型。"""

from __future__ import annotations

# 百炼 / 官方高德 MCP 的稳定工具名（list_tools 失败时也按这个分类调用）
TOOL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "weather": ("maps_weather",),
    "poi": ("maps_text_search", "maps_around_search", "maps_search_detail"),
    "geocode": ("maps_geo", "maps_regeocode", "maps_ip_location"),
    "route": (
        "maps_direction_walking",
        "maps_direction_bicycling",
        "maps_direction_driving",
        "maps_direction_transit_integrated",
        "maps_distance",
    ),
    "schema": ("maps_schema_navi", "maps_schema_take_taxi", "maps_schema_personal_map"),
}

# 图节点名 -> 本轮允许调用的 MCP 类别
AGENT_MCP_CATEGORIES: dict[str, tuple[str, ...]] = {
    "weather": ("weather",),
    "destination": ("poi", "geocode"),
    "activity": ("poi",),
    "hotel": ("poi",),
    "maps_route": ("geocode", "route", "schema"),
}

ROUTE_MODE_TOOLS = {
    "walking": "maps_direction_walking",
    "bicycling": "maps_direction_bicycling",
    "driving": "maps_direction_driving",
    "transit": "maps_direction_transit_integrated",
}


def tools_for_categories(categories: tuple[str, ...] | list[str]) -> list[str]:
    names: list[str] = []
    for category in categories:
        for tool in TOOL_CATEGORIES.get(category, ()):
            if tool not in names:
                names.append(tool)
    return names

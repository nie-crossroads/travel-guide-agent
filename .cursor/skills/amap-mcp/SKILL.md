---
name: amap-mcp
description: >-
  Integrates DashScope-hosted Amap MCP. Classifies tools into weather / poi /
  geocode / route / schema and calls them on demand. Use when editing Amap
  client, weather, maps_route, destination POI, AMAP_MCP env, or 高德 MCP.
---

# 高德 MCP（按类别按需调用）

百炼托管：`https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp`。`.env` 里 `AMAP_MCP_URL` + `AMAP_MCP_KEY`（百炼 DashScope Key）。**不要把全部工具一次性塞进模型**，按类别拆开，本轮需要才调。

客户端：`TravelServer/app/graph/amap/`。分类表：`catalog.py`。每次 `call_amap_tool` 记一条 `tool` span（见 [agent-trace](../agent-trace/SKILL.md)）。

| 类别 | 工具 | 何时调用 |
| --- | --- | --- |
| weather | `maps_weather` | 用户问天气/气温/会不会下雨 |
| poi | `maps_text_search` / `maps_around_search` / `maps_search_detail` | 目的地/景点推荐时，由 Destination 调用 |
| geocode | `maps_geo` / `maps_regeocode` / `maps_ip_location` | 路线规划前解析起终点坐标；公交/驾车只传 `经度,纬度`，不能回退成中文地址 |
| route | 步行/骑行/驾车/公交/测距 | 用户问怎么走、导航、市内路线 |
| schema | 导航/打车/专属地图唤端 | 路线节点需要唤起 App 时 |

问「成都天气」只走 Preference → Weather → Compose。问景点仍走 Destination（内部才调 POI），不查天气。

---
name: web-search-mcp
description: >-
  Integrates DashScope-hosted WebSearch MCP (bailian_web_search) as an on-demand
  web_search Agent. Use when editing web search client, Preference routing,
  latest-news queries, or WEB_SEARCH_MCP env.
---

# 联网搜索 MCP（按需调用）

百炼托管：`https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp`。`.env` 里 `WEB_SEARCH_MCP_URL`；Key 用 `WEB_SEARCH_MCP_KEY` 或复用 `AMAP_MCP_KEY`。

只调一个工具：`bailian_web_search`，参数 `query`。天气/POI/路线仍走高德，不要用网页搜索替代。

问「搜一下成都最近有什么展会」→ Preference → WebSearch → Compose。问景点仍走 Destination，不自动联网搜。

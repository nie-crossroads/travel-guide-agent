---
name: langgraph-planner
description: >-
  Maintains the on-demand LangGraph travel planner: Preference needed_agents,
  destination/flight/hotel/activity/budget/weather/maps_route, compose
  confirm-tail. Use when editing TravelServer/app/graph, agent routing,
  compose prompts, or changing which agents run per turn.
---

# LangGraph 按需规划

参考 [multi-agent-travel-planner](https://github.com/dreams-under-the-starry-sky/multi-agent-travel-planner)。**按用户本轮问题最小集合跑 Agent**，不要每次走完全图。

图：`START -> compress? -> preference -> (destination? / search? / weather? / maps_route? / budget?) -> compose`

专项代码在 `TravelServer/app/graph/agents/`。前端用 SSE `progress` 展示当前实际在跑的 Agent（未调用的专项不出现）。

## Agent 职责

1. Preference：整理预算/天数/风格，输出 `needed_agents`（`destination` / `flight` / `hotel` / `activity` / `budget` / `weather` / `maps_route`）
2. Destination：仅当本轮要推荐城市或景点时运行；问「哪里好玩」只列地点，不排行程；内部按需调高德 POI
3. Flight / Hotel / Activity：只跑 `needed_agents` 里有的，可 `asyncio.gather` 并行
4. Weather / MapsRoute：仅当本轮问天气或市内路线时调用对应类别的高德 MCP（细节见 [amap-mcp](../amap-mcp/SKILL.md)）
5. Budget：仅完整规划或用户问预算时硬校验；超预算则只对跑过的专项降级（活动→酒店→航班），最多 3 轮
6. Compose：只汇总本轮结果；**确认引导固定在全文最后**，并与本轮范围对齐（问景点就不要假装已排好酒店）

例子：「成都有哪些好玩的地方」→ Preference + Destination + Compose，跳过航班/酒店/活动/预算。

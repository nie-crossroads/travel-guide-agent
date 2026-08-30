---
name: agent-trace
description: >-
  Per-turn timing traces for agent entry/exit, LLM calls, and Amap tools. Use
  when editing TravelServer/app/graph/trace.py, chat SSE trace events, or the
  frontend 本轮耗时 panel.
---

# Agent 耗时追踪

每轮对话用 `contextvars` 收集 span，**不写入** LangGraph state。实现：`TravelServer/app/graph/trace.py`。

| kind | 何时打点 |
| --- | --- |
| agent | 各 Agent / 节点进出（preference、destination、weather、maps_route、web_search、flight、hotel、activity、budget、adjust、parallel_search、compose、compress） |
| tool | 高德 `call_amap_tool`、联网搜索 `bailian_web_search` |
| llm | `invoke_json`、compose 流式、compress |

SSE：`type=trace` 边跑边推已结束的 span；`done.trace` 带 `total_ms` 和全部 spans。后端 logger `travel.trace` 打一行按耗时降序的摘要。

前端助手气泡下展示「本轮耗时」树，最慢一段用橙强调色。历史会话不回放 trace（只存在当轮 SSE）。

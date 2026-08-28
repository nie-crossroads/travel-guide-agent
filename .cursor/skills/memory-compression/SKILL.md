---
name: memory-compression
description: >-
  Session memory with a 10000-token window, compress at 80% used via
  RemoveMessage, AsyncSqliteSaver checkpoints. Use when editing memory.py,
  CONTEXT_WINDOW, compression, checkpoints, or the token progress bar.
---

# 记忆与压缩

- 上下文窗口 **10000 tokens**（`CONTEXT_WINDOW`）
- 剩余 ≤ **20%**（已用 ≥ 8000）时压缩更早的对话，保留最近 2 条原话
- 用 `RemoveMessage` 删旧消息，不要整表替换 `messages`
- `AsyncSqliteSaver` 持久化 graph；摘要再写入会话表
- 压缩后 SSE 推 `compressed`，前端提示「对话记忆已压缩并保存」
- 流式输出要过滤 `<think>`，历史里也不保存思考块

实现：`TravelServer/app/graph/memory.py`。

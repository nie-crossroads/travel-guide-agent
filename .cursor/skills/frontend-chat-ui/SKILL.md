---
name: frontend-chat-ui
description: >-
  Cursor-style Vue chat UI: sticky bottom composer, Markdown-rendered assistant
  replies, hover-only session delete, 100% height so the scrollbar reaches the
  last message. Use when editing Travel/ ChatView, travel.css, chat store, or
  chat layout/scrolling.
---

# 前端聊天界面

代码只放 `Travel/`。`/api` 由 Vite 代理到 `http://127.0.0.1:8000`。

- Cursor 风格深色界面：近黑背景、细边框、橙强调色、助手消息轻量、用户消息深灰气泡
- 整页按容器 **100% 高度**铺满（不用 100vh，避免右侧内嵌浏览器裁掉底部）；只有消息列表滚动，滚动条能滚到最后一条
- 输入框在消息区外、始终贴在视口底部
- 流式回答时允许上滑查看上文；仅当用户贴近底部时才自动跟滚
- 侧栏会话（每条可清除，删除图标仅悬停时显示）+ 主区对话 + 快捷芯片 + token 进度条
- 助手回复按 Markdown 渲染（标题、列表、表格、代码块），用户消息保持纯文本
- SSE `progress` 展示当前实际在跑的 Agent（未调用的专项不出现）
- 本轮结束后助手气泡下展示 Agent / 模型 / 工具耗时树（SSE `trace` + `done.trace`）

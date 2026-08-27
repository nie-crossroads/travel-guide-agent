---
name: travel-agent
description: >-
  Maintains the travel-guide Agent (TravelServer LangGraph backend + Travel Vue3
  frontend), including a 6-agent LangGraph planner (preference, destination,
  parallel flight/hotel/activity, budget loop), 5000-token memory compression,
  Cursor-style dark UI with a sticky bottom composer, Markdown-rendered assistant
  replies, comments on complex methods, and keeping this skill in sync when
  requirements change. Use when editing this repo, adding features, generating
  code, or when the user updates product/tech requirements.
---

# 旅游攻略 Agent

本仓库是「出发吧」旅行顾问。改代码或加功能前先对照下面约定；**需求变更时必须同步更新本 Skill**。

## 用户硬性要求（原文）

- 给一些较为复杂的方法增加注释，后续在生成代码时也要有注释
- 生成skill，把前面的要求增加到skill中，后续有要求变更也要及时更新skill
- 界面样式换成cursor风格
- 输入框应该是一直固定在底部不会跟随页面滚动
- 回答输出的内容是markdown格式，但是并没有进行渲染
- 参考https://github.com/dreams-under-the-starry-sky/multi-agent-travel-planner 架构，用多agent实现旅游攻略
- 在进行回答时，此时用户无法向上滑动页面
- 后端在输出内容时，需要进一步和用户确认，引导用户输入确认的内容应该放在最后面

## 技术栈与目录

- 后端：Python 3.14 + FastAPI + LangGraph，代码只放 [`TravelServer/`](TravelServer/)
- 前端：Vue 3 + Vite + Element Plus + Pinia，代码只放 [`Travel/`](Travel/)
- 密钥只写 [`TravelServer/.env`](TravelServer/.env)，禁止硬编码；模板见 `.env.example`
- 模型：`gpt-5.6-terra`，OpenAI 兼容地址 `https://apinebula.ai/v1`

## 记忆与压缩

- 上下文窗口 **5000 tokens**
- 剩余 ≤ **20%**（已用 ≥ 4000）时压缩更早的对话，保留最近 2 条原话
- 用 `RemoveMessage` 删旧消息，不要整表替换 `messages`
- `AsyncSqliteSaver` 持久化 graph；摘要再写入会话表
- 压缩后 SSE 推 `compressed`，前端提示「对话记忆已压缩并保存」
- 流式输出要过滤 `<think>`，历史里也不保存思考块

图：`START -> compress? -> preference -> destination -> parallel_search -> budget ↺adjust -> compose`

## 多 Agent 规划

参考 [multi-agent-travel-planner](https://github.com/dreams-under-the-starry-sky/multi-agent-travel-planner)：

1. Preference：整理预算/天数/风格，并判断 `plan` 还是追问 `chat`
2. Destination：推荐主目的地
3. Flight / Hotel / Activity：`asyncio.gather` 并行
4. Budget：硬校验总价；超预算则渐进式降级（活动→酒店→航班），最多 3 轮
5. Compose：把结构化结果写成 Markdown 攻略并流式输出；**确认引导固定在全文最后**（可回复「确认」或指出要改的部分）

专项 Agent 代码在 `TravelServer/app/graph/agents/`。前端用 SSE `progress` 展示当前 Agent。

## 前端

- Cursor 风格深色界面：近黑背景、细边框、橙强调色、助手消息轻量、用户消息深灰气泡
- 整页 `100vh` 锁死，只有消息列表滚动；输入框在消息区外、始终贴在视口底部
- 流式回答时允许上滑查看上文；仅当用户贴近底部时才自动跟滚
- 侧栏会话 + 主区对话 + 快捷芯片 + token 进度条
- 助手回复按 Markdown 渲染（标题、列表、表格、代码块），用户消息保持纯文本
- SSE `progress` 展示当前是哪个 Agent 在工作
- `/api` 由 Vite 代理到 `http://127.0.0.1:8000`

## 注释约定

后续生成或修改代码时：

- 给**较复杂**的方法写简短中文 docstring / 注释：说明为什么、关键阈值、易错点
- 不给一眼能看懂的赋值、CRUD 堆注释
- 风格对齐现有文件：[`TravelServer/app/graph/memory.py`](TravelServer/app/graph/memory.py)、[`TravelServer/app/graph/agent.py`](TravelServer/app/graph/agent.py)、[`Travel/src/api/chat.js`](Travel/src/api/chat.js)

## 需求变更时更新本 Skill

同一轮改动里更新 [SKILL.md](SKILL.md)，不要只改代码：

1. 新增/删除功能、换模型、改窗口或压缩阈值
2. 调整目录、API、UI 风格、注释规则
3. 用户明确提出的新约束（原文可原样贴进「用户硬性要求」）

保持描述准确，删掉已过时的条目。

# 出发吧 Agent

本仓库是「出发吧」旅行顾问（TravelServer LangGraph + Travel Vue3）。改代码前先对照本文；专项流程按任务读取 `.cursor/skills/`。**需求变更时必须同步更新本文与对应 skill。**

Cursor 会自动加载根目录 `AGENTS.md`（指向本文）。

## 用户硬性要求（原文）

- 给一些较为复杂的方法增加注释，后续在生成代码时也要有注释
- 生成skill，把前面的要求增加到skill中，后续有要求变更也要及时更新skill
- 界面样式换成cursor风格
- 输入框应该是一直固定在底部不会跟随页面滚动
- 回答输出的内容是markdown格式，但是并没有进行渲染
- 参考https://github.com/dreams-under-the-starry-sky/multi-agent-travel-planner 架构，用多agent实现旅游攻略
- 在进行回答时，此时用户无法向上滑动页面
- 后端在输出内容时，需要进一步和用户确认，引导用户输入确认的内容应该放在最后面
- 现在每次都会走全部agent，应该是用户提问什么，才回答什么，后面的agent看情况执行，比如输入：成都有哪些好玩的地方，只需要推荐地方，不需要做后续的行程、酒店等安排
- 把会话token上限设置为10000
- 右侧浏览器的滚动条应该是能滚动到最底部的
- 左侧的会话列表要有能清除的按钮
- 左侧会话最后的删除图标，应该是鼠标悬浮时才显示
- 现在有高德的MCP服务，有天气查询相关的功能使用，帮我接入，需要将里面的功能进行分类，需要时再调用

## 技术栈与目录

- 后端：Python 3.14 + FastAPI + LangGraph，代码只放 `TravelServer/`
- 前端：Vue 3 + Vite + Element Plus + Pinia，代码只放 `Travel/`
- 密钥只写 `TravelServer/.env`，禁止硬编码；模板见 `.env.example`
- 高德 MCP：`AMAP_MCP_URL` + `AMAP_MCP_KEY`（百炼 DashScope Key），工具按类别按需调用
- 模型：`gpt-5.6-terra`，OpenAI 兼容地址 `https://apinebula.ai/v1`

## 按任务读取的 Skill

| 场景 | Skill |
| --- | --- |
| 改图、路由、专项 Agent、Compose | [langgraph-planner](.cursor/skills/langgraph-planner/SKILL.md) |
| 高德 MCP、天气、POI、市内路线 | [amap-mcp](.cursor/skills/amap-mcp/SKILL.md) |
| token 窗口、压缩、检查点 | [memory-compression](.cursor/skills/memory-compression/SKILL.md) |
| Vue 聊天界面、滚动、会话删除 | [frontend-chat-ui](.cursor/skills/frontend-chat-ui/SKILL.md) |

## 注释约定

后续生成或修改代码时：

- 给**较复杂**的方法写简短中文 docstring / 注释：说明为什么、关键阈值、易错点
- 不给一眼能看懂的赋值、CRUD 堆注释
- 风格对齐现有文件：`TravelServer/app/graph/memory.py`、`TravelServer/app/graph/agent.py`、`Travel/src/api/chat.js`

## 需求变更时更新文档

同一轮改动里更新 [AGENT.md](AGENT.md) 和对应 skill，不要只改代码：

1. 新增/删除功能、换模型、改窗口或压缩阈值
2. 调整目录、API、UI 风格、注释规则
3. 用户明确提出的新约束（原文可原样贴进「用户硬性要求」）

保持描述准确，删掉已过时的条目。

# 出发吧 · 旅行顾问

多轮对话旅游攻略：LangGraph 上的 6 Agent 协作规划，前端为 Cursor 风格深色聊天界面。

架构参考：[multi-agent-travel-planner](https://github.com/dreams-under-the-starry-sky/multi-agent-travel-planner)。

## 环境要求

- Python 3.14+
- Node.js 18+

## 启动后端

```bash
cd TravelServer
python -m pip install -r requirements.txt
copy .env.example .env
# 在 .env 中填写 OPENAI_API_KEY
python -m uvicorn app.main:app --reload --port 8000 --reload-exclude data
```

健康检查：`http://127.0.0.1:8000/api/health`

## 启动前端

```bash
cd Travel
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`（若端口被占用，Vite 会自动改用 5174/5175）。前端会把 `/api` 代理到后端 `8000` 端口。

## 多 Agent 流程

1. Preference：整理预算、天数、风格
2. Destination：推荐目的地
3. Flight / Hotel / Activity：并行搜索
4. Budget：校验总价；超支则按活动 → 酒店 → 航班降级，最多 3 轮
5. Compose：输出 Markdown 攻略

## 记忆策略

- 上下文窗口：5000 tokens
- 当剩余窗口 ≤ 20%（已用 ≥ 4000）时，自动压缩更早的对话
- 压缩摘要写入会话记录，并随 LangGraph 检查点一起保存
- 之后的回复会带着这份旅行记忆继续，而不是从头再问一遍

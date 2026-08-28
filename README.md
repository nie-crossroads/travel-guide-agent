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

Preference 先判断本轮 `needed_agents`，后面的专项按需执行，不问的机票/酒店/行程不会跑：

1. Preference：整理偏好，并给出本轮最小 Agent 集合
2. Destination：仅当需要推荐城市或景点时运行（内部可调高德 POI）
3. Flight / Hotel / Activity：仅运行用户问到的专项，可并行
4. Weather / 市内路线：仅当用户问天气或怎么走时调用高德 MCP
5. Budget：仅完整规划或用户问预算时校验；超支则按活动 → 酒店 → 航班降级，最多 3 轮
6. Compose：只汇总本轮跑过的结果；确认引导放在文末

`.env` 中配置 `AMAP_MCP_URL` 与 `AMAP_MCP_KEY`（百炼 Key）。高德工具按 weather / poi / geocode / route / schema 分类，需要才调用。

## 记忆策略

- 上下文窗口：10000 tokens
- 当剩余窗口 ≤ 20%（已用 ≥ 8000）时，自动压缩更早的对话
- 压缩摘要写入会话记录，并随 LangGraph 检查点一起保存
- 之后的回复会带着这份旅行记忆继续，而不是从头再问一遍

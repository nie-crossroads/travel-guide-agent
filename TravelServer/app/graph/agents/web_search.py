from __future__ import annotations

from app.graph.scope import latest_user_text
from app.graph.state import AgentState
from app.graph.trace import traced
from app.graph.websearch.client import WebSearchMcpError, call_web_search
from app.graph.websearch.parse import extract_pages


def _query(state: AgentState) -> str:
    """用本轮原话检索；已有城市且话里没提及时补上，避免搜到别的地方。"""
    text = latest_user_text(state)
    dest = state.get("destination") or {}
    prefs = state.get("preferences") or {}
    city = str(dest.get("city") or prefs.get("destination_hint") or "").strip()
    if city and city not in text:
        return f"{city} {text}".strip()
    return text


@traced("agent", "web_search")
async def run_web_search(state: AgentState) -> dict:
    """仅当 Preference 点名 web_search 时运行；天气/POI 仍走高德。"""
    query = _query(state)
    if not query:
        return {
            "web_search": {"query": "", "pages": [], "note": "还不知道要搜什么"},
            "progress": "联网搜索：缺少关键词",
        }
    try:
        payload = await call_web_search(query)
        pages = extract_pages(payload)
        return {
            "web_search": {
                "query": query,
                "pages": pages,
                "source": "bailian",
                "note": "" if pages else "联网搜索未返回条目",
            },
            "progress": f"联网搜索：已检索「{query[:18]}」",
        }
    except WebSearchMcpError as exc:
        return {
            "web_search": {"query": query, "pages": [], "source": "bailian", "note": str(exc)},
            "progress": "联网搜索：查询失败",
        }

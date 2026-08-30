from __future__ import annotations

from typing import Any


def extract_pages(payload: Any, limit: int = 6) -> list[dict[str, str]]:
    """百炼 bailian_web_search 返回 pages[]，只留标题/摘要/链接给 Compose。"""
    pages = []
    if isinstance(payload, dict):
        raw = payload.get("pages")
        if isinstance(raw, list):
            pages = raw
        elif isinstance(payload.get("raw"), str):
            pages = []
    out: list[dict[str, str]] = []
    for item in pages:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        url = str(item.get("url") or "").strip()
        hostname = str(item.get("hostname") or "").strip()
        if not title and not snippet:
            continue
        out.append(
            {
                "title": title,
                "snippet": snippet[:280],
                "url": url,
                "hostname": hostname,
            }
        )
        if len(out) >= limit:
            break
    return out

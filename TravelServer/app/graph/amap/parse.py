from __future__ import annotations

from typing import Any


def extract_pois(payload: Any, limit: int = 10) -> list[dict]:
    """高德关键词/周边搜返回结构不完全一致，这里抽出名称、地址、坐标。"""
    if isinstance(payload, dict) and isinstance(payload.get("raw"), str):
        payload = payload.get("raw")
    rows: list[Any] = []
    if isinstance(payload, dict):
        rows = payload.get("pois") or payload.get("data") or payload.get("results") or []
        if not rows and isinstance(payload.get("suggestion"), dict):
            rows = payload["suggestion"].get("cities") or []
    elif isinstance(payload, list):
        rows = payload
    pois: list[dict] = []
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        pois.append(
            {
                "name": name,
                "address": str(item.get("address") or item.get("adname") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "type": str(item.get("type") or item.get("typecode") or "").strip(),
                "id": str(item.get("id") or "").strip(),
            }
        )
    return pois


def extract_forecasts(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    forecasts = payload.get("forecasts") or payload.get("lives") or []
    if not forecasts and isinstance(payload.get("data"), dict):
        forecasts = payload["data"].get("forecasts") or []
    return [item for item in forecasts if isinstance(item, dict)]


def first_location(payload: Any) -> str:
    """地理编码结果里取出 lng,lat。"""
    if not isinstance(payload, dict):
        return ""
    geocodes = payload.get("geocodes") or payload.get("geocode") or []
    if isinstance(geocodes, dict):
        geocodes = [geocodes]
    if geocodes and isinstance(geocodes[0], dict):
        return str(geocodes[0].get("location") or "").strip()
    return str(payload.get("location") or "").strip()

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


def _first_row(payload: dict) -> dict | None:
    """官方 REST 用 geocodes，百炼 MCP 的 maps_geo 用 results。"""
    for key in ("geocodes", "geocode", "results", "data"):
        rows = payload.get(key)
        if isinstance(rows, dict):
            rows = [rows]
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return rows[0]
    return None


def first_location(payload: Any) -> str:
    """地理编码结果里取出 lng,lat；公交/驾车接口只接受坐标，不能回退成中文地址。"""
    if not isinstance(payload, dict):
        return ""
    row = _first_row(payload)
    if row:
        loc = str(row.get("location") or "").strip()
        if loc:
            return loc
    return str(payload.get("location") or "").strip()


def first_city(payload: Any) -> str:
    """从地理编码结果补城市名，避免 transit 的 city/cityd 为空。"""
    if not isinstance(payload, dict):
        return ""
    row = _first_row(payload)
    if not row:
        return ""
    city = str(row.get("city") or "").strip()
    if city.endswith("市") and len(city) > 2:
        city = city[:-1]
    return city


def is_lnglat(value: str) -> bool:
    parts = (value or "").split(",")
    if len(parts) != 2:
        return False
    try:
        lng, lat = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return False
    return -180 <= lng <= 180 and -90 <= lat <= 90

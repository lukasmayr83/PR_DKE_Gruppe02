from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from flask import current_app


def _base(key: str) -> str:
    return (current_app.config.get(key, "") or "").rstrip("/")


def _get_json(url: str, timeout: int = 8, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout, headers={"Accept": "application/json"}, params=params)
    r.raise_for_status()
    return r.json()


def parse_gmt_dt(s: Optional[str]) -> Optional[datetime]:
    """Parst zb 'Mon, 01 Dec 2025 19:30:00 GMT'"""
    if not s:
        return None
    dt = parsedate_to_datetime(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fahrplan_snapshot() -> Dict[str, Any]:
    base = _base("FAHRPLAN_API_BASE")
    return _get_json(f"{base}/api/fahrtdurchfuehrungen/snapshot")


def fahrplan_halteplaene(query: str = "") -> Dict[str, Any]:
    base = _base("FAHRPLAN_API_BASE")
    url = f"{base}/api/halteplaene"
    params = {"q": query} if query else None
    return _get_json(url, params=params)


def strecken_bahnhoefe(query: str = "") -> Dict[str, Any]:
    base = _base("STRECKEN_API_BASE")
    url = f"{base}/bahnhoefe"
    params = {"q": query} if query else None
    return _get_json(url, params=params)


def strecken_warnungen(query: str = "") -> Dict[str, Any]:
    base = _base("STRECKEN_API_BASE")
    url = f"{base}/warnungen"
    params = {"q": query} if query else None
    return _get_json(url, params=params)


def flotte_kapazitaet(zug_id: int) -> Dict[str, Any]:
    base = _base("FLOTTEN_API_BASE")
    return _get_json(f"{base}/flotte/kapazitaet/{zug_id}")

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import requests

from config import (
    DEFAULT_HEADERS,
    SELF_STOCK_HTTP_TIMEOUT,
    SELF_STOCK_V1_BASE_URL,
    SELF_STOCK_V1_MODIFY_PATH,
    SELF_STOCK_V1_QUERY_PATH,
)
from exceptions import THSAPIError, THSNetworkError
from models import StockEntry, StockListVersion


def download_self_stocks_v1(
    cookies: dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> StockListVersion:
    headers = {"User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo")}
    userid = cookies.get("userid")
    if userid:
        headers["userid"] = userid
    params: dict[str, str] = {"support_all": "0", "from": "thspc_hevo"}
    try:
        response = requests.get(
            f"{SELF_STOCK_V1_BASE_URL}{SELF_STOCK_V1_QUERY_PATH}",
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选(v1)", str(exc)) from exc

    payload = response.json()
    if payload.get("status_code") != 0:
        raise THSAPIError(
            "我的自选(v1)", payload.get("status_msg", "未知错误"), str(payload.get("status_code"))
        )
    data = payload.get("data", {})
    raw = data.get("selfstock", "")
    version = str(data.get("version", ""))
    items: list[StockEntry] = []
    if raw:
        comma_idx = raw.rfind(",")
        if comma_idx >= 0:
            codes_segment = raw[:comma_idx]
            types_segment = raw[comma_idx + 1 :]
            codes = [c for c in codes_segment.split("|") if c]
            type_codes = [t for t in types_segment.split("|") if t]
            for i, code in enumerate(codes):
                mtype = type_codes[i] if i < len(type_codes) else ""
                items.append(StockEntry(code, mtype))
    return StockListVersion(version=version, items=items)


def modify_self_stocks_v1(
    cookies: dict[str, str],
    stock_list: list[StockEntry],
    version: str,
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> dict[str, Any]:
    codes = "|".join(e.code for e in stock_list)
    types = "|".join(e.market_type for e in stock_list)
    selfstock_value = f"{codes},{types}"
    data: dict[str, str] = {
        "selfstock": selfstock_value,
        "from": "thspc_hevo",
        "version": str(version),
        "num": str(len(stock_list)),
    }
    encoded = urlencode(data)
    headers = {
        "User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo"),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    userid = cookies.get("userid")
    if userid:
        headers["userid"] = userid
    try:
        response = requests.post(
            f"{SELF_STOCK_V1_BASE_URL}{SELF_STOCK_V1_MODIFY_PATH}",
            data=encoded,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选(v1)", str(exc)) from exc

    payload = response.json()
    if payload.get("status_code") != 0:
        raise THSAPIError(
            "我的自选(v1)", payload.get("status_msg", "未知错误"), str(payload.get("status_code"))
        )
    return payload.get("data", {})

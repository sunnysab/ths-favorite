from __future__ import annotations

from typing import Any

import requests

from config import (
    DEFAULT_HEADERS,
    SELF_STOCK_HTTP_TIMEOUT,
    SELF_STOCK_V2_BASE_URL,
    SELF_STOCK_V2_LIST_PATH,
    SELF_STOCK_V2_MODIFY_PATH,
)
from exceptions import THSAPIError, THSNetworkError


def _extract_self_stock_v2_result(payload: Any, action_name: str) -> Any:
    if not isinstance(payload, dict):
        raise THSAPIError(action_name, "响应格式无效")
    error_code = payload.get("errorCode")
    if error_code != 0:
        raise THSAPIError(action_name, payload.get("errorMsg", "未知业务错误"), str(error_code))
    return payload.get("result")


def download_self_stocks_v2(
    cookies: dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    headers = {
        "User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo"),
    }
    try:
        response = requests.get(
            f"{SELF_STOCK_V2_BASE_URL}{SELF_STOCK_V2_LIST_PATH}",
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选", str(exc)) from exc
    payload = response.json()
    result = _extract_self_stock_v2_result(payload, "我的自选")
    if not isinstance(result, list):
        raise THSAPIError("我的自选", "响应缺少 result 列表")
    items: list[tuple[str, str]] = []
    for entry in result:
        if not isinstance(entry, dict):
            raise THSAPIError("我的自选", "result 条目格式不正确")
        code = entry.get("code")
        marketid = entry.get("marketid")
        if code is None or marketid is None:
            raise THSAPIError("我的自选", "result 条目缺少 code 或 marketid")
        items.append((str(code), str(marketid)))
    return payload, items


def modify_self_stock_v2(
    cookies: dict[str, str],
    *,
    op: str,
    stockcode: str,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{SELF_STOCK_V2_BASE_URL}{SELF_STOCK_V2_MODIFY_PATH}",
            params={"op": op, "stockcode": stockcode},
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选", str(exc)) from exc
    payload = response.json()
    _extract_self_stock_v2_result(payload, "我的自选")
    return payload


def download_self_stocks(
    cookies: dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    return download_self_stocks_v2(cookies, timeout=timeout)


def upload_self_stocks(
    cookies: dict[str, str],
    *,
    op: str | None = None,
    stockcode: str | None = None,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> dict[str, Any]:
    if op is not None and stockcode is not None:
        return modify_self_stock_v2(cookies, op=op, stockcode=stockcode, timeout=timeout)
    raise THSAPIError("我的自选", "仅支持基于 cookies 的新版自选接口，请提供 op 和 stockcode")

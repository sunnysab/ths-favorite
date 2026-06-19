from urllib.parse import quote

import requests

from client import SHARED_SESSION
from config import (
    DEFAULT_HEADERS,
    DYNAMIC_PLATE_BASE_URL,
    DYNAMIC_PLATE_SELECT_PATH,
    SELF_STOCK_HTTP_TIMEOUT,
)
from exceptions import THSNetworkError
from models import StockEntry


def query_dynamic_plate(
    group_name: str,
    cookies: dict[str, str],
    *,
    num: int = 1000,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> list[StockEntry]:
    url = (
        f"{DYNAMIC_PLATE_BASE_URL}{DYNAMIC_PLATE_SELECT_PATH}"
        f"?query={quote(group_name)}&num={num}"
    )
    headers = {"User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo")}
    try:
        response = SHARED_SESSION.get(url, headers=headers, cookies=cookies, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("动态分组", str(exc)) from exc

    payload = response.json()
    codes = payload.get("data", {}).get("codes", [])
    return [StockEntry(str(c["code"]), str(c["market"])) for c in codes]

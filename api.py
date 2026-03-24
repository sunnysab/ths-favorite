from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

import requests

from client import ApiClient
from config import (
    DEFAULT_FROM_PARAM,
    DEFAULT_HEADERS,
    ENDPOINTS,
    GROUP_QUERY_TYPES,
    HEXIN_SPECIAL_BASE64_EX_ALPHABET,
    SELF_STOCK_API_URL,
    SELF_STOCK_HTTP_TIMEOUT,
    SELF_STOCK_V2_BASE_URL,
    SELF_STOCK_V2_LIST_PATH,
    SELF_STOCK_V2_MODIFY_PATH,
)
from exceptions import THSAPIError, THSNetworkError
from utils import parse_ths_xml_response

SELFSTOCK_DETAIL_API_URL = "https://ugc.10jqka.com.cn/selfstock_detail"
SELFSTOCK_DETAIL_TIMEOUT = 10.0
STANDARD_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class FavoriteAPI:
    """Wrapper around the THS favorites HTTP endpoints."""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def query_groups(self) -> Dict[str, Any]:
        params: Dict[str, str] = {
            "from": DEFAULT_FROM_PARAM,
            "types": GROUP_QUERY_TYPES,
        }
        response = self._client.get(ENDPOINTS["query_groups"], params=params)
        return self._extract_data(response, "获取分组")

    def add_item(self, group_id: str, item_code: str, api_item_type: str, version: str) -> Dict[str, Any]:
        return self._item_operation(
            ENDPOINTS["add_item"],
            "添加股票",
            group_id,
            item_code,
            api_item_type,
            version,
        )

    def delete_item(self, group_id: str, item_code: str, api_item_type: str, version: str) -> Dict[str, Any]:
        return self._item_operation(
            ENDPOINTS["delete_item"],
            "删除股票",
            group_id,
            item_code,
            api_item_type,
            version,
        )

    def add_group(self, name: str, version: str) -> Dict[str, Any]:
        payload = {
            "name": name,
            "type": "0",
        }
        return self._post_with_version(
            ENDPOINTS["add_group"],
            payload,
            version,
            "添加分组",
        )

    def delete_group(self, group_id: str, version: str) -> Dict[str, Any]:
        payload = {
            "ids": group_id,
        }
        return self._post_with_version(
            ENDPOINTS["delete_group"],
            payload,
            version,
            "删除分组",
        )

    def _item_operation(
        self,
        endpoint: str,
        action_name: str,
        group_id: str,
        item_code: str,
        api_item_type: str,
        version: str,
    ) -> Dict[str, Any]:
        payload = {
            "id": group_id,
            "content": f"{item_code},{api_item_type}",
            "num": "1",
        }
        return self._post_with_version(endpoint, payload, version, action_name)

    def share_group(self, share_payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.post_form_json(ENDPOINTS["share_group"], data=share_payload)
        return self._extract_data(response, "分享分组")

    def download_self_stocks(
        self,
        *,
        account: Optional[str] = None,
        password: Optional[str] = None,
        marketcode: str = "1",
    ) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
        return download_self_stocks(
            self._client.get_cookies(),
            marketcode=marketcode,
        )

    def upload_self_stocks(
        self,
        *,
        op: Optional[str] = None,
        stockcode: Optional[str] = None,
        account: Optional[str] = None,
        password: Optional[str] = None,
        marketcode: str = "1",
        items: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        return upload_self_stocks(
            self._client.get_cookies(),
            op=op,
            stockcode=stockcode,
            account=account,
            password=password,
            marketcode=marketcode,
            items=items,
        )

    def _post_with_version(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        version: str,
        action_name: str,
    ) -> Dict[str, Any]:
        request_payload = payload.copy()
        request_payload["version"] = str(version)
        request_payload.setdefault("from", DEFAULT_FROM_PARAM)
        response = self._client.post_form_urlencoded(endpoint, data=request_payload)
        return self._extract_data(response, action_name)

    @staticmethod
    def _extract_data(response: Dict[str, Any], action_name: str) -> Dict[str, Any]:
        if not isinstance(response, dict):
            raise THSAPIError(action_name, "响应格式无效")
        status_code = response.get("status_code")
        if status_code != 0:
            raise THSAPIError(action_name, response.get("status_msg", "未知业务错误"), str(status_code))
        data = response.get("data")
        if data is None:
            raise THSAPIError(action_name, "响应缺少 data 字段")
        if not isinstance(data, dict):
            raise THSAPIError(action_name, "data 字段格式不正确")
        return data


def download_selfstock_detail(
    userid: str,
    cookies: Dict[str, str],
    *,
    timeout: float = SELFSTOCK_DETAIL_TIMEOUT,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    params = {
        "reqtype": "download",
        "app_flag": "0E",
        "userid": userid,
    }
    headers = {
        "userid": userid,
        "User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo"),
    }
    try:
        response = requests.get(
            SELFSTOCK_DETAIL_API_URL,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("selfstock_detail", str(exc)) from exc

    root = parse_ths_xml_response(response.text, "selfstock_detail")
    item = root.find("item")
    if item is None:
        raise THSAPIError("selfstock_detail", "响应缺少 <item> 节点")

    version = item.attrib.get("version")
    detail_blob = item.attrib.get("selfstock_detail", "")
    detail_data = _decode_detail_blob(detail_blob)
    return version, detail_data


def _decode_detail_blob(detail_blob: str) -> List[Dict[str, Any]]:
    if not detail_blob:
        return []
    decoded_bytes = base64.b64decode(detail_blob)
    decoded_str = decoded_bytes.decode("utf-8")
    if not decoded_str.strip():
        return []
    return json.loads(decoded_str)


def _decode_hexin_special_base64_ex(blob: str) -> bytes:
    translated = blob.translate(str.maketrans(HEXIN_SPECIAL_BASE64_EX_ALPHABET, STANDARD_BASE64_ALPHABET))
    return base64.b64decode(translated)


def _decode_self_stock_response_text(blob: str) -> Dict[str, str]:
    raw_bytes = _decode_hexin_special_base64_ex(blob)
    decoded_text = raw_bytes.decode("gbk").strip()
    result: Dict[str, str] = {}
    for index, part in enumerate(decoded_text.split("&")):
        if not part:
            continue
        if index == 0 and part.startswith("<meta "):
            part = part[len("<meta ") :]
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value
    return result


def _parse_self_stock_items(payload: str, expected_num: int) -> List[Tuple[str, str]]:
    if "," not in payload:
        raise THSAPIError("我的自选", "SelfStock 字段缺少市场码段")
    codes_blob, markets_blob = payload.split(",", 1)
    codes = [code for code in codes_blob.split("|") if code]
    markets = [market for market in markets_blob.split("|") if market]
    if len(codes) != len(markets) or len(codes) != expected_num:
        raise THSAPIError("我的自选", "SelfStock 条目数与 num 不一致")
    return list(zip(codes, markets))


def _encode_self_stock_request_payload(**fields: str) -> str:
    plain_text = "&".join(f"{key}={value}" for key, value in fields.items())
    encoded = base64.b64encode(plain_text.encode("gbk")).decode("ascii")
    return encoded.translate(str.maketrans(STANDARD_BASE64_ALPHABET, HEXIN_SPECIAL_BASE64_EX_ALPHABET))


def _extract_self_stock_v2_result(payload: Any, action_name: str) -> Any:
    if not isinstance(payload, dict):
        raise THSAPIError(action_name, "响应格式无效")
    error_code = payload.get("errorCode")
    if error_code != 0:
        raise THSAPIError(action_name, payload.get("errorMsg", "未知业务错误"), str(error_code))
    return payload.get("result")


def download_self_stocks_v2(
    cookies: Dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
    try:
        response = requests.get(
            f"{SELF_STOCK_V2_BASE_URL}{SELF_STOCK_V2_LIST_PATH}",
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
    items: List[Tuple[str, str]] = []
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
    cookies: Dict[str, str],
    *,
    op: str,
    stockcode: str,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
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


def download_self_stocks_old(
    cookies: Dict[str, str],
    *,
    account: str,
    password: str,
    marketcode: str = "1",
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
    """Deprecated: old my_stock.php selfstock protocol."""
    response = requests.post(
        SELF_STOCK_API_URL,
        data={
            "param": _encode_self_stock_request_payload(
                account=account,
                do="get",
                expand="1",
                marketcode=marketcode,
                passwd=password,
                selfcode_crc=" ",
            )
        },
        headers={
            "User-Agent": "HEVO",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        cookies=cookies,
        timeout=timeout,
    )
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选", str(exc)) from exc
    meta = _decode_self_stock_response_text(response.text.strip())
    retcode = meta.get("retcode")
    if retcode != "0":
        raise THSAPIError("我的自选", meta.get("ReturnMsg", "未知业务错误"), retcode)
    num_text = meta.get("num")
    self_stock = meta.get("SelfStock")
    if num_text is None or self_stock is None:
        raise THSAPIError("我的自选", "响应缺少 num 或 SelfStock 字段")
    items = _parse_self_stock_items(self_stock, int(num_text))
    return meta, items


def upload_self_stocks_old(
    cookies: Dict[str, str],
    *,
    account: str,
    password: str,
    marketcode: str,
    items: List[Tuple[str, str]],
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, str]:
    codes_blob = "|".join(code for code, _ in items)
    markets_blob = "|".join(market for _, market in items)
    payload = _encode_self_stock_request_payload(
        account=account,
        do="put",
        expand="1",
        marketcode=marketcode,
        passwd=password,
        selfcode_crc=" ",
        SelfStock=f"{codes_blob}|,{markets_blob}|",
    )
    try:
        response = requests.post(
            SELF_STOCK_API_URL,
            data={"param": payload},
            headers={
                "User-Agent": "HEVO",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("我的自选", str(exc)) from exc
    return _decode_self_stock_response_text(response.text.strip())


def download_self_stocks(
    cookies: Dict[str, str],
    *,
    account: Optional[str] = None,
    password: Optional[str] = None,
    marketcode: str = "1",
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
    return download_self_stocks_v2(cookies, timeout=timeout)


def upload_self_stocks(
    cookies: Dict[str, str],
    *,
    op: Optional[str] = None,
    stockcode: Optional[str] = None,
    account: Optional[str] = None,
    password: Optional[str] = None,
    marketcode: str = "1",
    items: Optional[List[Tuple[str, str]]] = None,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    if op is not None and stockcode is not None:
        return modify_self_stock_v2(cookies, op=op, stockcode=stockcode, timeout=timeout)
    if account is None or password is None or items is None:
        raise THSAPIError("我的自选", "缺少新旧协议所需参数")
    return upload_self_stocks_old(
        cookies,
        account=account,
        password=password,
        marketcode=marketcode,
        items=items,
        timeout=timeout,
    )

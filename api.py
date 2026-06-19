from __future__ import annotations

import base64
import io
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from client import ApiClient
from config import (
    BLOCKSTOCK_APPNAME,
    DEFAULT_FROM_PARAM,
    DEFAULT_HEADERS,
    ENDPOINTS,
    GROUP_QUERY_TYPES,
    MULTI_STORAGE_DEFAULT_CLIENTTYPE,
    MULTI_STORAGE_URL,
    SELF_STOCK_HTTP_TIMEOUT,
    SELF_STOCK_V1_BASE_URL,
    SELF_STOCK_V1_MODIFY_PATH,
    SELF_STOCK_V1_QUERY_PATH,
    SELF_STOCK_V2_BASE_URL,
    SELF_STOCK_V2_LIST_PATH,
    SELF_STOCK_V2_MODIFY_PATH,
)
from exceptions import THSAPIError, THSNetworkError
from utils import parse_ths_xml_response

SELFSTOCK_DETAIL_API_URL = "https://ugc.10jqka.com.cn/selfstock_detail"
SELFSTOCK_DETAIL_TIMEOUT = 10.0


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
    ) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
        return download_self_stocks(self._client.get_cookies())

    def upload_self_stocks(
        self,
        *,
        op: str,
        stockcode: str,
    ) -> Dict[str, Any]:
        return upload_self_stocks(
            self._client.get_cookies(),
            op=op,
            stockcode=stockcode,
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

def download_self_stocks(
    cookies: Dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
    return download_self_stocks_v2(cookies, timeout=timeout)


def upload_self_stocks(
    cookies: Dict[str, str],
    *,
    op: Optional[str] = None,
    stockcode: Optional[str] = None,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    if op is not None and stockcode is not None:
        return modify_self_stock_v2(cookies, op=op, stockcode=stockcode, timeout=timeout)
    raise THSAPIError("我的自选", "仅支持基于 cookies 的新版自选接口，请提供 op 和 stockcode")


_PB_WIRETYPE_VARINT = 0
_PB_WIRETYPE_LEN = 2


def _pb_encode_varint(value: int) -> bytes:
    buf = bytearray()
    while value > 127:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def _pb_decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        value |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return value, offset


def _pb_field_varint(field_number: int, value: int) -> bytes:
    tag = (field_number << 3) | _PB_WIRETYPE_VARINT
    return _pb_encode_varint(tag) + _pb_encode_varint(value)


def _pb_field_bytes(field_number: int, payload: bytes) -> bytes:
    tag = (field_number << 3) | _PB_WIRETYPE_LEN
    return _pb_encode_varint(tag) + _pb_encode_varint(len(payload)) + payload


# --- self-stock v1 (batch full-replace, my-stock only) ---

def download_self_stocks_v1(
    cookies: Dict[str, str],
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Tuple[str, List[Tuple[str, str]]]:
    headers = {"User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo")}
    userid = cookies.get("userid")
    if userid:
        headers["userid"] = userid
    params: Dict[str, str] = {"support_all": "0", "from": "thspc_hevo"}
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
        raise THSAPIError("我的自选(v1)", payload.get("status_msg", "未知错误"), str(payload.get("status_code")))
    data = payload.get("data", {})
    raw = data.get("selfstock", "")
    version = str(data.get("version", ""))
    items: List[Tuple[str, str]] = []
    if raw:
        comma_idx = raw.rfind(",")
        if comma_idx >= 0:
            codes_segment = raw[:comma_idx]
            types_segment = raw[comma_idx + 1:]
            codes = [c for c in codes_segment.split("|") if c]
            type_codes = [t for t in types_segment.split("|") if t]
            for i, code in enumerate(codes):
                mtype = type_codes[i] if i < len(type_codes) else ""
                items.append((code, mtype))
    return version, items


def modify_self_stocks_v1(
    cookies: Dict[str, str],
    stock_list: List[Tuple[str, str]],
    version: str,
    *,
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    codes = "|".join(code for code, _ in stock_list)
    types = "|".join(mtype for _, mtype in stock_list)
    selfstock_value = f"{codes},{types}"
    data: Dict[str, str] = {
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
        raise THSAPIError("我的自选(v1)", payload.get("status_msg", "未知错误"), str(payload.get("status_code")))
    return payload.get("data", {})


# --- multiStorage blockstock (batch full-replace, all groups) ---

def _encode_blockstock_payload(group_name: str, group_type: int, stock_list: List[Tuple[str, str]]) -> bytes:
    gbk_bytes = group_name.encode("gbk")
    group_id_b64 = base64.b64encode(gbk_bytes).decode("ascii")

    codes = "|".join(code for code, _ in stock_list)
    types = "|".join(mtype for _, mtype in stock_list)
    stock_str = f"{codes},{types}"

    group_data = (
        _pb_field_bytes(1, group_id_b64.encode("ascii"))
        + _pb_field_bytes(3, stock_str.encode("ascii"))
    )
    group_payload = (
        _pb_field_bytes(1, _pb_field_varint(1, group_type))
        + _pb_field_bytes(3, group_data)
    )
    return _pb_field_bytes(1, group_payload)


def _parse_blockstock_download(data: bytes) -> Dict[str, Any]:
    offset = 0
    result: Dict[str, Any] = {"count": 0, "version": 0, "groups": []}

    while offset < len(data):
        tag, offset = _pb_decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:
            value, offset = _pb_decode_varint(data, offset)
            if field_number == 1:
                result["count"] = value
            elif field_number == 2:
                result["version"] = value
        elif wire_type == 2:
            length, offset = _pb_decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 3:
                inner = _parse_group_payload(chunk)
                result["groups"].append(inner)

    return result


def _parse_group_payload(data: bytes) -> Dict[str, Any]:
    offset = 0
    result: Dict[str, Any] = {"group_type": 0, "group_name": "", "stock_list": []}

    while offset < len(data):
        tag, offset = _pb_decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:
            value, offset = _pb_decode_varint(data, offset)
            if field_number == 1:
                result["group_type"] = value
        elif wire_type == 2:
            length, offset = _pb_decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 1:
                inner_tag, _ = _pb_decode_varint(chunk, 0)
                if (inner_tag >> 3) == 1:
                    value, _ = _pb_decode_varint(chunk, 1)
                    result["group_type"] = value
            elif field_number == 3:
                inner = _parse_group_data(chunk)
                result["stock_list"] = inner.get("stock_list", [])
                gid = inner.get("group_id")
                if gid:
                    try:
                        gb = base64.b64decode(gid).decode("gbk")
                        result["group_name"] = gb
                    except Exception:
                        result["group_name"] = gid

    return result


def _parse_group_data(data: bytes) -> Dict[str, Any]:
    offset = 0
    result: Dict[str, Any] = {"group_id": None, "stock_list": []}

    while offset < len(data):
        tag, offset = _pb_decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, offset = _pb_decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 1:
                result["group_id"] = chunk.decode("ascii")
            elif field_number == 3:
                raw = chunk.decode("ascii")
                comma_idx = raw.rfind(",")
                if comma_idx >= 0:
                    codes_segment = raw[:comma_idx]
                    types_segment = raw[comma_idx + 1:]
                    codes = [c for c in codes_segment.split("|") if c]
                    type_codes = [t for t in types_segment.split("|") if t]
                    stock_list: List[Tuple[str, str]] = []
                    for i, code in enumerate(codes):
                        mtype = type_codes[i] if i < len(type_codes) else ""
                        stock_list.append((code, mtype))
                    result["stock_list"] = stock_list

    return result


def download_blockstock(
    auth_params: Dict[str, str],
    cookies: Dict[str, str],
    *,
    storepath: str = "/",
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    data: Dict[str, str] = {
        "reqtype": "download",
        "userid": auth_params.get("userid", ""),
        "storepath": storepath,
        "sessionid": auth_params.get("sessionid", ""),
        "expires": auth_params.get("expires", ""),
        "appname": BLOCKSTOCK_APPNAME,
        "storetype": "2",
        "clienttype": auth_params.get("clienttype", MULTI_STORAGE_DEFAULT_CLIENTTYPE),
        "version": "0",
    }
    headers = {
        "User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo"),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        response = requests.post(
            MULTI_STORAGE_URL,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("blockstock download", str(exc)) from exc

    return _parse_blockstock_download(response.content)


def upload_blockstock(
    auth_params: Dict[str, str],
    cookies: Dict[str, str],
    group_name: str,
    group_type: int,
    stock_list: List[Tuple[str, str]],
    version: str,
    *,
    storepath: str = "/",
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    boundary = f"----HevoFormBoundary{uuid.uuid4().hex[:10]}"
    payload_bytes = _encode_blockstock_payload(group_name, group_type, stock_list)

    parts: List[bytes] = []
    form_fields = [
        ("appname", BLOCKSTOCK_APPNAME),
        ("reqtype", "upload"),
        ("version", str(version)),
        ("storepath", storepath),
        ("clienttype", auth_params.get("clienttype", MULTI_STORAGE_DEFAULT_CLIENTTYPE)),
        ("compresstype", "none"),
        ("compresstype_upload", "none"),
        ("compresstype_download", "none"),
        ("userid", auth_params.get("userid", "")),
        ("sessionid", auth_params.get("sessionid", "")),
        ("expires", auth_params.get("expires", "")),
    ]
    for name, value in form_fields:
        parts.append(f"--{boundary}\r\n".encode("ascii"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n'.encode("ascii"))
        parts.append("Content-Type: text/plain; charset=US-ASCII\r\n".encode("ascii"))
        parts.append("Content-Encoding: 8bit\r\n\r\n".encode("ascii"))
        parts.append(value.encode("ascii"))
        parts.append(b"\r\n")

    parts.append(f"--{boundary}\r\n".encode("ascii"))
    parts.append(f'Content-Disposition: form-data; name="uploadFile"; filename="testFileList"\r\n'.encode("ascii"))
    parts.append("Content-Type: application/octet-stream\r\n".encode("ascii"))
    parts.append("Content-Encoding: binary\r\n\r\n".encode("ascii"))
    parts.append(payload_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(parts)

    headers = {
        "User-Agent": DEFAULT_HEADERS.get("User-Agent", "hevo"),
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    try:
        response = requests.post(
            MULTI_STORAGE_URL,
            data=body,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError("blockstock upload", str(exc)) from exc

    parsed = _parse_blockstock_download(response.content)
    return parsed

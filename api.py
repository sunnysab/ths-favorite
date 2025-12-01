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

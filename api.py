import base64
import json
from typing import Any, Literal

import requests

from blockstock import (
    download_blockstock as _download_blockstock,
)
from blockstock import (
    extract_auth_params_from_cookies,
)
from blockstock import (
    upload_blockstock as _upload_blockstock,
)
from client import SHARED_SESSION, ApiClient
from config import (
    DEFAULT_FROM_PARAM,
    DEFAULT_HEADERS,
    ENDPOINTS,
    GROUP_QUERY_TYPES,
)
from dynamicplate import query_dynamic_plate as _query_dynamic_plate
from exceptions import THSAPIError, THSNetworkError
from models import BlockstockDownload, StockEntry
from selfstock_v1 import download_self_stocks_v1 as _download_self_stocks_v1
from selfstock_v1 import modify_self_stocks_v1 as _modify_self_stocks_v1
from selfstock_v2 import (
    download_self_stocks as _download_self_stocks_v2,
)
from selfstock_v2 import (
    upload_self_stocks as _upload_self_stocks_v2,
)
from utils import parse_ths_xml_response

SELFSTOCK_DETAIL_API_URL = 'https://ugc.10jqka.com.cn/selfstock_detail'
SELFSTOCK_DETAIL_TIMEOUT = 10.0

# ── Shared helpers ──


def _merge_entries(
    current_list: list[StockEntry],
    parsed_new: list[StockEntry],
    action: Literal['add', 'delete'],
    context: str = '批量操作',
) -> list[StockEntry]:
    """Merge current entries with add/delete changes, deduplicated by stock code."""
    current_map = {e.code: e for e in current_list}
    if action == 'add':
        merged = dict(current_map)
        for e in parsed_new:
            merged[e.code] = e
    elif action == 'delete':
        delete_codes = {e.code for e in parsed_new}
        merged = {c: e for c, e in current_map.items() if c not in delete_codes}
    else:
        raise THSAPIError(context, f'未知操作: {action}')
    return list(merged.values())


_DYNAMIC_GROUP_PREFIX = '1_'


class FavoriteAPI:
    """Internal API layer for THS favorites.

    Routes between v1/v2/blockstock/JSON protocols automatically.
    PortfolioManager should use this class, not the raw protocol modules.
    """

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    # ══════════════════════════════════════════
    # Group CRUD
    # ══════════════════════════════════════════

    def query_groups(self) -> dict[str, Any]:
        """Fetch all groups metadata from the server."""
        params: dict[str, str] = {
            'from': DEFAULT_FROM_PARAM,
            'types': GROUP_QUERY_TYPES,
        }
        response = self._client.get(ENDPOINTS['query_groups'], params=params)
        return self._extract_data(response, '获取分组')

    def create_group(self, name: str, version: str) -> dict[str, Any]:
        """Create a new custom group."""
        payload = {'name': name, 'type': '0'}
        return self._post_with_version(ENDPOINTS['add_group'], payload, version, '添加分组')

    def delete_group(self, group_id: str, version: str) -> dict[str, Any]:
        """Delete a custom group."""
        payload = {'ids': group_id}
        return self._post_with_version(ENDPOINTS['delete_group'], payload, version, '删除分组')

    def share_group(self, share_payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a share link for a group."""
        response = self._client.post_form_json(ENDPOINTS['share_group'], data=share_payload)
        return self._extract_data(response, '分享分组')

    # ══════════════════════════════════════════
    # Stock operations (unified — routing is internal)
    # ══════════════════════════════════════════

    def add_item(
        self,
        group_id: str,
        symbol: StockEntry,
        version: str,
        *,
        is_self_stock: bool = False,
    ) -> dict[str, Any]:
        """Add a single stock to a group.

        Self-stock → v2 upload; custom group → per-item JSON API.
        """
        if is_self_stock:
            return _upload_self_stocks_v2(
                self._client.get_cookies(), op='add',
                stockcode=f'{symbol.code}_{symbol.market_type}',
            )
        return self._item_operation(
            ENDPOINTS['add_item'], '添加股票',
            group_id, symbol.code, symbol.market_type, version,
        )

    def add_items(
        self,
        group_id: str,
        symbols: list[StockEntry],
        *,
        is_self_stock: bool = False,
        group_name: str | None = None,
    ) -> dict[str, Any]:
        """Add multiple stocks to a group in one request.

        Self-stock → v1 read-modify-write; custom → multiStorage.
        """
        if not symbols:
            raise THSAPIError('添加股票', '股票列表不能为空')
        if is_self_stock:
            return self._batch_self_stock(symbols, action='add')
        if group_name and self._get_auth_params() is not None:
            return self._batch_group_stock(group_name, symbols, action='add')
        raise THSAPIError('添加股票', '批量添加自定义分组需要登录态')

    def remove_item(
        self,
        group_id: str,
        symbol: StockEntry,
        version: str,
        *,
        is_self_stock: bool = False,
    ) -> dict[str, Any]:
        """Remove a single stock from a group."""
        if is_self_stock:
            return _upload_self_stocks_v2(
                self._client.get_cookies(), op='del',
                stockcode=f'{symbol.code}_{symbol.market_type}',
            )
        return self._item_operation(
            ENDPOINTS['delete_item'], '删除股票',
            group_id, symbol.code, symbol.market_type, version,
        )

    def remove_items(
        self,
        group_id: str,
        symbols: list[StockEntry],
        *,
        is_self_stock: bool = False,
        group_name: str | None = None,
    ) -> dict[str, Any]:
        """Remove multiple stocks from a group in one request."""
        if not symbols:
            raise THSAPIError('删除股票', '股票列表不能为空')
        if is_self_stock:
            return self._batch_self_stock(symbols, action='delete')
        if group_name and self._get_auth_params() is not None:
            return self._batch_group_stock(group_name, symbols, action='delete')
        raise THSAPIError('删除股票', '批量删除自定义分组需要登录态')

    # ══════════════════════════════════════════
    # Data fetching
    # ══════════════════════════════════════════

    def list_self_stocks(self) -> list[StockEntry]:
        """Download the user's 我的自选 list (v2 protocol)."""
        _, items = _download_self_stocks_v2(self._client.get_cookies())
        return [StockEntry(code, market_id) for code, market_id in items]

    def list_group_stocks(self) -> BlockstockDownload:
        """Download all group stocks via multiStorage protocol."""
        auth_params = self._get_auth_params()
        if auth_params is None:
            raise THSAPIError('获取分组', '缺少 multiStorage 凭据，无法同步分组数据')
        return _download_blockstock(auth_params, self._client.get_cookies())

    def query_dynamic_plate(self, group_name: str) -> list[StockEntry]:
        """Query stocks in a dynamic plate group."""
        return _query_dynamic_plate(group_name, self._client.get_cookies())

    @staticmethod
    def is_dynamic_group(group_id: str) -> bool:
        """Check whether a group is a dynamic plate (read-only)."""
        return group_id.startswith(_DYNAMIC_GROUP_PREFIX)

    def _get_auth_params(self) -> dict[str, str] | None:
        """Derive multiStorage auth params from current cookies."""
        cookies = self._client.get_cookies()
        if not cookies.get('userid'):
            return None
        result = extract_auth_params_from_cookies(cookies)
        if not result.get('sessionid'):
            return None
        return result

    # ══════════════════════════════════════════
    # Internal: self-stock protocol
    # ══════════════════════════════════════════

    def _batch_self_stock(self, symbols: list[StockEntry], *, action: Literal['add', 'delete']) -> dict[str, Any]:
        """Read-modify-write for self-stock batch operations (v1 protocol)."""
        current = _download_self_stocks_v1(self._client.get_cookies())
        merged = _merge_entries(current.items, symbols, action, '我的自选')
        return _modify_self_stocks_v1(self._client.get_cookies(), merged, current.version)

    # ══════════════════════════════════════════
    # Internal: group stock batch protocol
    # ══════════════════════════════════════════

    def _add_group_stocks_batch(
        self,
        group_name: str,
        symbols: list[StockEntry],
    ) -> dict[str, Any]:
        return self._batch_group_stock(group_name, symbols, action='add')

    def _remove_group_stocks_batch(
        self,
        group_name: str,
        symbols: list[StockEntry],
    ) -> dict[str, Any]:
        return self._batch_group_stock(group_name, symbols, action='delete')

    def _batch_group_stock(
        self,
        group_name: str,
        symbols: list[StockEntry],
        *,
        action: Literal['add', 'delete'],
    ) -> dict[str, Any]:
        """Read-modify-write for custom group batch operations (multiStorage protocol)."""
        auth_params = self._get_auth_params()
        if auth_params is None:
            raise THSAPIError('批量操作', '缺少 multiStorage 凭据，批量自定义分组操作需要登录态')
        data = _download_blockstock(auth_params, self._client.get_cookies())
        group_type = 0
        current: list[StockEntry] = []
        for g in data.groups:
            if g.group_name == group_name:
                group_type = g.group_type
                current = g.stock_list
                break
        merged = _merge_entries(current, symbols, action)
        return _upload_blockstock(
            auth_params, self._client.get_cookies(),
            group_name, group_type, merged, str(data.version),
        )

    # ══════════════════════════════════════════
    # Internal: JSON API helpers (single item)
    # ══════════════════════════════════════════

    def _item_operation(
        self,
        endpoint: str,
        action_name: str,
        group_id: str,
        item_code: str,
        api_item_type: str,
        version: str,
    ) -> dict[str, Any]:
        payload = {
            'id': group_id,
            'content': f'{item_code},{api_item_type}',
            'num': '1',
        }
        return self._post_with_version(endpoint, payload, version, action_name)

    def _post_with_version(
        self,
        endpoint: str,
        payload: dict[str, Any],
        version: str,
        action_name: str,
    ) -> dict[str, Any]:
        request_payload = payload.copy()
        request_payload['version'] = str(version)
        request_payload.setdefault('from', DEFAULT_FROM_PARAM)
        response = self._client.post_form_urlencoded(endpoint, data=request_payload)
        return self._extract_data(response, action_name)

    @staticmethod
    def _extract_data(response: dict[str, Any], action_name: str) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise THSAPIError(action_name, '响应格式无效')
        status_code = response.get('status_code')
        if status_code != 0:
            raise THSAPIError(
                action_name, response.get('status_msg', '未知业务错误'), str(status_code)
            )
        data = response.get('data')
        if data is None:
            raise THSAPIError(action_name, '响应缺少 data 字段')
        if not isinstance(data, dict):
            raise THSAPIError(action_name, 'data 字段格式不正确')
        return data


# ══════════════════════════════════════════════════════════════
# Standalone helpers (not part of FavoriteAPI)
# ══════════════════════════════════════════════════════════════


def download_selfstock_detail(
    userid: str,
    cookies: dict[str, str],
    *,
    timeout: float = SELFSTOCK_DETAIL_TIMEOUT,
) -> tuple[str | None, list[dict[str, Any]]]:
    params = {
        'reqtype': 'download',
        'app_flag': '0E',
        'userid': userid,
    }
    headers = {
        'userid': userid,
        'User-Agent': DEFAULT_HEADERS.get('User-Agent', 'hevo'),
    }
    try:
        response = SHARED_SESSION.get(
            SELFSTOCK_DETAIL_API_URL,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError('selfstock_detail', str(exc)) from exc

    root = parse_ths_xml_response(response.text, 'selfstock_detail')
    item = root.find('item')
    if item is None:
        raise THSAPIError('selfstock_detail', '响应缺少 <item> 节点')

    version = item.attrib.get('version')
    detail_blob = item.attrib.get('selfstock_detail', '')
    detail_data = _decode_detail_blob(detail_blob)
    return version, detail_data


def _decode_detail_blob(detail_blob: str) -> list[dict[str, Any]]:
    if not detail_blob:
        return []
    decoded_bytes = base64.b64decode(detail_blob)
    decoded_str = decoded_bytes.decode('utf-8')
    if not decoded_str.strip():
        return []
    return json.loads(decoded_str)

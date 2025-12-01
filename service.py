from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from api import FavoriteAPI, download_selfstock_detail
from auth import SessionManager
from client import ApiClient
from config import (
    API_BASE_URL,
    COOKIE_CACHE_FILE,
    COOKIE_CACHE_TTL_SECONDS,
    DEFAULT_HEADERS,
    GROUP_CACHE_FILE,
)
from constant import market_abbr, market_code
from exceptions import THSAPIError, THSNetworkError
from models import StockGroup, StockItem
from storage import load_groups_cache, save_groups_cache


class PortfolioManager:
    """High level service that manages a user's THS favorites."""

    def __init__(
        self,
        cookies: Union[str, Dict[str, str], None] = None,
        api_client: Optional[ApiClient] = None,
        *,
        auth_method: str = "browser",
        browser_name: str = "firefox",
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie_cache_path: Optional[str] = None,
        cookie_cache_ttl_seconds: int = COOKIE_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize the manager.

        Args:
            cookies: Optional raw cookie string or dict to bypass authentication.
            api_client: Custom ApiClient instance for advanced integrations.
            auth_method: How to acquire cookies (`browser`, `credentials`, or `none`).
            browser_name: Browser to read cookies from when auth_method="browser".
            username: Account username when using credential authentication.
            password: Account password when using credential authentication.
            cookie_cache_path: Override path for cached cookies.
            cookie_cache_ttl_seconds: Custom TTL (seconds) for cached cookies.
        """
        self._group_cache_path: str = GROUP_CACHE_FILE
        self._groups_cache: Dict[str, StockGroup] = load_groups_cache(self._group_cache_path)
        self._current_version: Optional[Union[str, int]] = None
        self._selfstock_detail_version: Optional[str] = None
        self._selfstock_detail_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._selfstock_detail_raw: List[Dict[str, Any]] = []

        self._session_manager = SessionManager(
            cookies=cookies,
            auth_method=auth_method,
            browser_name=browser_name,
            username=username,
            password=password,
            cookie_cache_path=cookie_cache_path or COOKIE_CACHE_FILE,
            cookie_cache_ttl_seconds=cookie_cache_ttl_seconds,
        )
        resolved_cookies = self._session_manager.resolve()

        if api_client is not None:
            self.api_client = api_client
            self._is_external_api_client = True
            if resolved_cookies:
                self.api_client.set_cookies(resolved_cookies)
        else:
            self.api_client = ApiClient(
                base_url=API_BASE_URL,
                cookies=resolved_cookies,
                headers=DEFAULT_HEADERS,
            )
            self._is_external_api_client = False

        self._api = FavoriteAPI(self.api_client)

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        logger.info("通过 PortfolioManager 设置 API 客户端 cookies...")
        self.api_client.set_cookies(cookies_input)

    def get_all_groups(self, use_cache: bool = False) -> Dict[str, StockGroup]:
        logger.info("开始获取所有自选股分组信息...")
        try:
            raw_data = self._api.query_groups()
        except THSNetworkError:
            if use_cache and self._groups_cache:
                logger.warning("获取分组失败，返回内存缓存数据。")
                return self._groups_cache.copy()
            raise

        self._update_version_from_response_data(raw_data)
        parsed_groups = self._parse_group_list(raw_data)
        self.refresh_selfstock_detail(force=True)

        formatted: Dict[str, StockGroup] = {}
        for group_raw in parsed_groups:
            name: Optional[str] = group_raw.get("name")
            group_id: Optional[str] = group_raw.get("id")
            if not name or not group_id:
                logger.warning("解析时发现无名称或ID的分组原始数据，已跳过: %s", group_raw)
                continue

            items: List[StockItem] = []
            for detail in group_raw.get("item_details", []):
                item_code: Optional[str] = detail.get("code")
                api_type: Optional[str] = detail.get("api_type")
                market_short = market_abbr(api_type) if api_type else None
                if item_code:
                    items.append(StockItem(code=item_code, market=market_short))
            self._attach_selfstock_metadata(items)
            formatted[name] = StockGroup(name=name, group_id=group_id, items=items)

        self._groups_cache = formatted
        save_groups_cache(self._group_cache_path, formatted)
        logger.info("成功获取并处理了 %d 个分组。", len(formatted))
        return formatted

    def add_item_to_group(self, group_identifier: str, symbol: str) -> Dict[str, Any]:
        logger.info("尝试添加项目 '%s' 到分组 '%s'...", symbol, group_identifier)
        target_group_id = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            raise THSAPIError("添加股票", f"未能找到分组 '{group_identifier}'")

        item_code, api_item_type = self._parse_symbol(symbol)
        version = self._ensure_version_available()
        result = self._api.add_item(target_group_id, item_code, api_item_type, version)
        self.get_all_groups(use_cache=False)
        return result

    def delete_item_from_group(self, group_identifier: str, symbol: str) -> Dict[str, Any]:
        logger.info("尝试删除项目 '%s' 从分组 '%s'...", symbol, group_identifier)
        target_group_id = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            raise THSAPIError("删除股票", f"未能找到分组 '{group_identifier}'")

        item_code, api_item_type = self._parse_symbol(symbol)
        version = self._ensure_version_available()
        result = self._api.delete_item(target_group_id, item_code, api_item_type, version)
        self.get_all_groups(use_cache=False)
        return result

    def add_group(self, group_name: str) -> Dict[str, Any]:
        if not group_name:
            raise THSAPIError("添加分组", "分组名称不能为空")
        version = self._ensure_version_available()
        result = self._api.add_group(group_name, version)
        self.get_all_groups(use_cache=False)
        return result

    def delete_group(self, group_identifier: str) -> Dict[str, Any]:
        target_group_id = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            raise THSAPIError("删除分组", f"未能找到 '{group_identifier}'")
        version = self._ensure_version_available()
        result = self._api.delete_group(target_group_id, version)
        self.get_all_groups(use_cache=False)
        return result

    def share_group(self, group_identifier: str, valid_time: int) -> Dict[str, Any]:
        target_group_id = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            raise THSAPIError("分享分组", f"未能找到 '{group_identifier}'")
        cookies = self.api_client.get_cookies()
        userid = cookies.get("userid")
        if not userid:
            raise THSAPIError("分享分组", "当前 cookies 中缺少 userid，无法分享")
        biz_suffix = target_group_id.split("_", 1)[1] if "_" in target_group_id else target_group_id
        payload = {
            "biz": "selfstock",
            "valid_time": int(valid_time),
            "biz_key": f"{userid}_{biz_suffix}",
            "name": group_identifier,
            "url_style": 0,
        }
        return self._api.share_group(payload)

    def refresh_selfstock_detail(self, force: bool = False) -> Optional[str]:
        if not force and self._selfstock_detail_map:
            return self._selfstock_detail_version

        cookies = self.api_client.get_cookies()
        userid = cookies.get("userid")
        if not userid:
            logger.warning("刷新 selfstock_detail 失败：cookies 中缺少 userid。")
            return None
        version, detail_list = download_selfstock_detail(userid, cookies)
        index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for entry in detail_list:
            code = entry.get("C")
            market_type = entry.get("M")
            if not code:
                continue
            market_short = market_abbr(market_type) if market_type else None
            key = self._detail_key(code, market_short)
            price_raw = entry.get("P")
            price_value: Optional[float] = None
            if price_raw not in (None, ""):
                try:
                    price_value = float(price_raw)
                except (TypeError, ValueError):
                    logger.debug("无法解析价格 '%s' (%s)", price_raw, entry)
            index[key] = {
                "price": price_value,
                "timestamp": entry.get("T"),
            }

        self._selfstock_detail_raw = detail_list
        self._selfstock_detail_map = index
        self._selfstock_detail_version = version
        logger.info(
            "selfstock_detail 数据刷新成功：版本 %s，记录 %d 条。",
            version or "未知",
            len(index),
        )
        return version

    def get_item_snapshot(self, symbol: str, *, refresh: bool = False) -> Optional[Dict[str, Any]]:
        if refresh or not self._selfstock_detail_map:
            self.refresh_selfstock_detail(force=True)

        if "." not in symbol:
            raise THSAPIError("查询股票", "股票代码需包含市场后缀，例如 '600519.SH'")

        code_part, market_suffix = symbol.rsplit(".", 1)
        key = self._detail_key(code_part, market_suffix)
        meta = self._selfstock_detail_map.get(key) or self._selfstock_detail_map.get((code_part, ""))
        if not meta:
            return None
        return {
            "code": code_part,
            "market": market_suffix.upper(),
            "price": meta.get("price"),
            "added_at": meta.get("timestamp"),
            "version": self._selfstock_detail_version,
        }

    def close(self) -> None:
        logger.info("准备关闭 PortfolioManager 服务...")
        save_groups_cache(self._group_cache_path, self._groups_cache)
        if not self._is_external_api_client:
            self.api_client.close()
        logger.info("PortfolioManager 服务已关闭。")

    def __enter__(self) -> "PortfolioManager":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()

    def _get_group_id_by_identifier(self, group_identifier: str) -> Optional[str]:
        if not self._groups_cache:
            self.get_all_groups(use_cache=False)
        for group_obj in self._groups_cache.values():
            if group_obj.group_id == group_identifier:
                return group_obj.group_id
        if group_identifier in self._groups_cache:
            return self._groups_cache[group_identifier].group_id
        return None

    def _parse_symbol(self, symbol: str) -> Tuple[str, str]:
        if "." not in symbol:
            raise THSAPIError("解析股票代码", f"股票代码格式无效: '{symbol}'")
        code_part, market_suffix_part = symbol.rsplit(".", 1)
        api_market_type_code = market_code(market_suffix_part.upper())
        if not api_market_type_code:
            raise THSAPIError("解析股票代码", f"未知的市场后缀: '{market_suffix_part}'")
        return code_part, api_market_type_code

    def _update_version_from_response_data(self, response_data: Optional[Dict[str, Any]]) -> None:
        if response_data and isinstance(response_data, dict) and "version" in response_data:
            new_version = response_data["version"]
            logger.debug("自选列表版本号从 %s 更新为 %s", self._current_version, new_version)
            self._current_version = new_version

    def _ensure_version_available(self) -> str:
        if self._current_version is None:
            logger.info("当前自选列表版本号未知，尝试刷新分组数据以获取最新版本…")
            self.get_all_groups(use_cache=False)
            if self._current_version is None:
                raise THSAPIError("版本检查", "仍未能获取有效的自选列表版本号")
        return str(self._current_version)

    def _parse_group_list(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed_groups_raw_info: List[Dict[str, Any]] = []
        if not raw_data or not isinstance(raw_data, dict) or "group_list" not in raw_data:
            return parsed_groups_raw_info
        api_group_list = raw_data.get("group_list", [])
        for i, group_dict_from_api in enumerate(api_group_list):
            if not isinstance(group_dict_from_api, dict):
                logger.warning(
                    "API返回的group_list中第 %d 个元素不是预期的字典类型，已跳过", i + 1
                )
                continue
            current_group_parsed_info: Dict[str, Any] = {
                "id": group_dict_from_api.get("id"),
                "name": group_dict_from_api.get("name"),
                "api_type_code": group_dict_from_api.get("type"),
                "num_items_api": group_dict_from_api.get("num"),
                "attrs": group_dict_from_api.get("attrs", {}),
                "item_details": [],
            }
            content_str: Optional[str] = group_dict_from_api.get("content")
            if isinstance(content_str, str) and content_str:
                parts = content_str.split(",", 1)
                item_codes_segment = parts[0]
                api_item_type_codes_segment = parts[1] if len(parts) > 1 else ""
                item_codes_list = [code for code in item_codes_segment.split("|") if code]
                api_item_type_codes_list = [tc for tc in api_item_type_codes_segment.split("|") if tc]
                for j, item_code_str in enumerate(item_codes_list):
                    api_item_type_code = (
                        api_item_type_codes_list[j] if j < len(api_item_type_codes_list) else None
                    )
                    current_group_parsed_info["item_details"].append(
                        {
                            "code": item_code_str,
                            "api_type": api_item_type_code,
                        }
                    )
            parsed_groups_raw_info.append(current_group_parsed_info)
        return parsed_groups_raw_info

    def _attach_selfstock_metadata(self, favorites: List[StockItem]) -> None:
        if not self._selfstock_detail_map:
            return
        for item in favorites:
            market_key = (item.market or "").upper()
            meta = self._selfstock_detail_map.get((item.code, market_key))
            if meta is None:
                meta = self._selfstock_detail_map.get((item.code, ""))
            if not meta:
                continue
            if meta.get("price") is not None:
                object.__setattr__(item, "price", meta["price"])
            if meta.get("timestamp"):
                object.__setattr__(item, "added_at", meta["timestamp"])

    @staticmethod
    def _detail_key(code: str, market_short: Optional[str]) -> Tuple[str, str]:
        return (code, (market_short or "").upper())


__all__ = ["PortfolioManager"]

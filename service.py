from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

from loguru import logger
from requests.exceptions import HTTPError, RequestException

from auth import create_session
from client import THSHttpApiClient
from config import (
    API_BASE_URL,
    COOKIE_CACHE_FILE,
    COOKIE_CACHE_TTL_SECONDS,
    DEFAULT_HEADERS,
    DEFAULT_FROM_PARAM,
    ENDPOINTS,
    GROUP_CACHE_FILE,
    GROUP_QUERY_TYPES,
)
from constant import market_abbr, market_code
from cookie import load_browser_cookie
from models import THSFavorite, THSFavoriteGroup
from storage import load_groups_cache, read_cached_cookies, save_groups_cache, write_cookie_cache

T_UserFavorite = TypeVar("T_UserFavorite", bound="THSUserFavorite")

QUERY_ENDPOINT = ENDPOINTS["query_groups"]
ADD_ITEM_ENDPOINT = ENDPOINTS["add_item"]
DELETE_ITEM_ENDPOINT = ENDPOINTS["delete_item"]
ADD_GROUP_ENDPOINT = ENDPOINTS["add_group"]
DELETE_GROUP_ENDPOINT = ENDPOINTS["delete_group"]
SHARE_GROUP_ENDPOINT = ENDPOINTS["share_group"]


class THSUserFavorite:
    """管理同花顺用户自选股的业务逻辑层。

    Args:
        cookies: 直接传入的 Cookie 字符串/字典，如果为 ``None`` 将根据
            ``auth_method`` 自动获取。
        api_client: 可注入的 :class:`THSHttpApiClient` 实例，用于自定义超时或
            复用 Session。
        auth_method: ``"browser"``、``"credentials"`` 或 ``"none"``，决定如何
            获取 cookies。
        browser_name: 当 ``auth_method="browser"`` 时使用的浏览器名称。
        username: 账号登录模式下的用户名。
        password: 账号登录模式下的密码。
        cookie_cache_path: cookies 缓存文件路径，默认为 ``config.COOKIE_CACHE_FILE``。
        cookie_cache_ttl_seconds: cookies 缓存有效期，单位秒。

    Attributes:
        api_client: 当前使用的 HTTP 客户端。
        _groups_cache: 最近一次获取到的分组缓存，键为分组名称。

    Note:
        如果传入自定义 ``api_client``，且同时提供了 ``cookies``/认证参数，
        会调用 :meth:`THSHttpApiClient.set_cookies` 覆盖该客户端的 cookie。
        若希望完全由外部管理 cookie，可省略认证参数或在实例化后自行更新。
    """

    def __init__(
        self,
        cookies: Union[str, Dict[str, str], None] = None,
        api_client: Optional[THSHttpApiClient] = None,
        *,
        auth_method: str = "browser",
        browser_name: str = "firefox",
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie_cache_path: Optional[str] = None,
        cookie_cache_ttl_seconds: int = COOKIE_CACHE_TTL_SECONDS,
    ) -> None:
        logger.info("THSUserFavorite 服务初始化...")
        self._cookie_cache_path: str = cookie_cache_path or COOKIE_CACHE_FILE
        self._cookie_cache_ttl_seconds: int = cookie_cache_ttl_seconds
        self._group_cache_path: str = GROUP_CACHE_FILE

        resolved_cookies: Union[str, Dict[str, str], None] = cookies
        if resolved_cookies is None:
            resolved_cookies = self._resolve_cookies_via_auth_method(
                auth_method=auth_method,
                browser_name=browser_name,
                username=username,
                password=password,
            )

        if api_client:
            self.api_client = api_client
            self._is_external_api_client = True
            logger.info("使用外部传入的 THSHttpApiClient 实例。")
            if resolved_cookies:
                self.set_cookies(resolved_cookies)
        else:
            logger.info("创建内部 THSHttpApiClient 实例。")
            self.api_client = THSHttpApiClient(
                base_url=API_BASE_URL,
                cookies=resolved_cookies,
                headers=DEFAULT_HEADERS,
            )
            self._is_external_api_client = False

        self._current_version: Optional[Union[str, int]] = None
        self._groups_cache: Dict[str, THSFavoriteGroup] = load_groups_cache(self._group_cache_path)

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        logger.info("通过 THSUserFavorite 设置 API 客户端 cookies...")
        self.api_client.set_cookies(cookies_input)

    def _update_version_from_response_data(self, response_data: Optional[Dict[str, Any]]) -> None:
        if response_data and isinstance(response_data, dict) and "version" in response_data:
            new_version: Union[str, int] = response_data["version"]
            logger.debug("自选列表版本号从 %s 更新为 %s", self._current_version, new_version)
            self._current_version = new_version
        else:
            logger.debug("响应数据中未找到版本号，或数据格式不符，版本号未更新。")

    def _ensure_version_available(self) -> bool:
        if self._current_version is None:
            logger.info("当前自选列表版本号未知，尝试刷新分组数据以获取最新版本…")
            self.get_all_groups(use_cache=False)
            if self._current_version is None:
                logger.error("仍未能获取有效的自选列表版本号。")
                return False
        return True

    def get_raw_group_data(self) -> Optional[Dict[str, Any]]:
        """Fetch raw group payload from the THS open API.

        Returns:
            dict | None: 当调用成功时返回 ``{"group_list": [...], "version": ...}``
            结构的字典，否则返回 ``None``。
        """

        logger.info("尝试从API获取原始分组数据: %s", QUERY_ENDPOINT)
        params: Dict[str, str] = {
            "from": DEFAULT_FROM_PARAM,
            "types": GROUP_QUERY_TYPES,
        }
        api_response: Optional[Dict[str, Any]] = None
        try:
            api_response = self.api_client.get(QUERY_ENDPOINT, params=params)
        except HTTPError as exc:
            status = exc.response.status_code if exc.response else "未知"
            logger.error("获取原始分组数据时发生HTTP状态错误 (已由APIClient记录): %s", status)
            return None
        except RequestException as exc:
            logger.error("获取原始分组数据时发生请求错误 (已由APIClient记录): %s", exc)
            return None
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("获取原始分组数据时发生JSON解码错误 (已由APIClient记录): %s", exc)
            return None
        except Exception:
            logger.exception("获取原始分组数据时发生未预料的错误。")
            return None

        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = api_response.get("data")
            self._update_version_from_response_data(data)
            logger.info("成功获取并解析了原始分组数据。")
            return data
        if api_response and isinstance(api_response, dict):
            status_msg: str = api_response.get("status_msg", "未知业务错误")
            status_code: int = api_response.get("status_code", -1)
            logger.error("获取分组API业务逻辑错误: %s (代码: %s)", status_msg, status_code)
        elif api_response is not None:
            logger.error("获取分组API返回了非预期的格式: %s", type(api_response))
        return None

    def parse_group_list(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert the API ``group_list`` payload into a normalized structure.

        Args:
            raw_data: ``get_raw_group_data`` 返回的 ``data`` 节点。

        Returns:
            list[dict]: 包含 ``id``、``name``、``item_details`` 等字段的字典列表，
            供后续转换为 :class:`THSFavoriteGroup` 使用。
        """

        logger.debug("开始解析API返回的原始分组数据...")
        parsed_groups_raw_info: List[Dict[str, Any]] = []
        if not raw_data or not isinstance(raw_data, dict) or "group_list" not in raw_data:
            logger.warning("原始数据无效或不包含 'group_list' 键，无法解析。返回空列表。")
            return parsed_groups_raw_info

        api_group_list: List[Dict[str, Any]] = raw_data.get("group_list", [])
        logger.debug("API返回了 %d 个原始分组条目。", len(api_group_list))

        for i, group_dict_from_api in enumerate(api_group_list):
            if not isinstance(group_dict_from_api, dict):
                logger.warning(
                    "API返回的group_list中第 %d 个元素不是预期的字典类型，已跳过: %s",
                    i + 1,
                    group_dict_from_api,
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
            logger.debug(
                "正在解析分组 '%s' (ID: %s)...",
                current_group_parsed_info["name"],
                current_group_parsed_info["id"],
            )

            content_str: Optional[str] = group_dict_from_api.get("content")
            if isinstance(content_str, str) and content_str:
                parts: List[str] = content_str.split(",", 1)
                item_codes_segment: str = parts[0]
                api_item_type_codes_segment: str = parts[1] if len(parts) > 1 else ""

                item_codes_list: List[str] = [code for code in item_codes_segment.split("|") if code]
                api_item_type_codes_list: List[str] = [tc for tc in api_item_type_codes_segment.split("|") if tc]

                logger.debug(
                    "分组 '%s' 包含 %d 个项目代码，%d 个API类型代码。",
                    current_group_parsed_info["name"],
                    len(item_codes_list),
                    len(api_item_type_codes_list),
                )

                for j, item_code_str in enumerate(item_codes_list):
                    api_item_type_code: Optional[str] = (
                        api_item_type_codes_list[j] if j < len(api_item_type_codes_list) else None
                    )
                    current_group_parsed_info["item_details"].append(
                        {
                            "code": item_code_str,
                            "api_type": api_item_type_code,
                        }
                    )
            else:
                logger.debug("分组 '%s' 的 'content' 字段为空或格式不正确。", current_group_parsed_info["name"])

            parsed_groups_raw_info.append(current_group_parsed_info)
        logger.info("成功解析了 %d 个分组的原始信息。", len(parsed_groups_raw_info))
        return parsed_groups_raw_info

    def get_all_groups(self, use_cache: bool = False) -> Dict[str, THSFavoriteGroup]:
        """Return all favorite groups managed under the current account.

        Args:
            use_cache: 当 API 请求失败时是否回退到内存缓存。

        Returns:
            dict[str, THSFavoriteGroup]: 以分组名称为键的分组字典。
        """

        logger.info("开始获取所有自选股分组信息...")
        formatted_groups: Dict[str, THSFavoriteGroup] = {}
        raw_data_from_api = self.get_raw_group_data()

        if raw_data_from_api:
            logger.info("成功从API获取原始数据，开始转换为 THSFavoriteGroup 对象...")
            parsed_group_list_raw_info = self.parse_group_list(raw_data_from_api)

            for group_raw_info in parsed_group_list_raw_info:
                group_name: Optional[str] = group_raw_info.get("name")
                group_id: Optional[str] = group_raw_info.get("id")

                if group_name and group_id:
                    favorite_items_list: List[THSFavorite] = []
                    item_details_from_parse: List[Dict[str, Optional[str]]] = group_raw_info.get("item_details", [])

                    for detail in item_details_from_parse:
                        item_code_str: Optional[str] = detail.get("code")
                        api_item_type_code: Optional[str] = detail.get("api_type")
                        market_short_name: Optional[str] = market_abbr(api_item_type_code) if api_item_type_code else None

                        if item_code_str:
                            favorite_items_list.append(THSFavorite(code=item_code_str, market=market_short_name))
                        else:
                            logger.warning("在分组 '%s' 中发现无代码的项目详情: %s", group_name, detail)

                    ths_favorite_group = THSFavoriteGroup(name=group_name, group_id=group_id, items=favorite_items_list)
                    formatted_groups[group_name] = ths_favorite_group
                    logger.debug(
                        "已创建 THSFavoriteGroup 对象: '%s' (ID: %s), 项目数: %d",
                        group_name,
                        group_id,
                        len(favorite_items_list),
                    )
                else:
                    logger.warning("解析时发现无名称或ID的分组原始数据，已跳过: %s", group_raw_info)

            self._groups_cache = formatted_groups
            save_groups_cache(self._group_cache_path, self._groups_cache)
            logger.info("成功获取并处理了 %d 个分组。缓存已更新。", len(formatted_groups))
            return formatted_groups

        logger.error("从API获取分组数据失败。")
        if use_cache:
            logger.warning("尝试使用内存中的旧缓存数据。")
            return self._groups_cache.copy()
        logger.warning("未启用缓存或缓存为空，返回空的分组列表。")
        return {}

    def _get_group_id_by_identifier(self, group_identifier: str) -> Optional[str]:
        logger.debug("尝试通过标识符 '%s' 获取分组ID...", group_identifier)
        if not self._groups_cache:
            logger.info("内部缓存为空，将尝试从API获取最新分组数据以查找分组ID...")
            self.get_all_groups(use_cache=False)

        for group_obj in self._groups_cache.values():
            if group_obj.group_id == group_identifier:
                logger.debug("通过分组ID '%s' 匹配成功。", group_identifier)
                return group_obj.group_id
        if group_identifier in self._groups_cache:
            logger.debug("通过分组名称 '%s' 匹配成功。", group_identifier)
            return self._groups_cache[group_identifier].group_id

        logger.warning("未能通过标识符 '%s' 找到对应的分组ID。当前缓存中有 %d 个分组。", group_identifier, len(self._groups_cache))
        return None

    def _parse_code_with_market_suffix(self, code_with_market_suffix: str) -> Tuple[str, str]:
        logger.debug("尝试解析带市场后缀的代码: '%s'", code_with_market_suffix)
        if "." not in code_with_market_suffix:
            logger.error("股票代码格式无效: '%s'。缺少 '.' 分隔符。", code_with_market_suffix)
            raise ValueError(f"股票代码格式无效: '{code_with_market_suffix}'。预期格式: CODE.MARKET_SUFFIX")

        code_part, market_suffix_part = code_with_market_suffix.rsplit(".", 1)
        api_market_type_code: Optional[str] = market_code(market_suffix_part.upper())

        if not api_market_type_code:
            logger.error("未知的市场后缀: '%s' (来自代码 '%s')", market_suffix_part, code_with_market_suffix)
            raise ValueError(f"未知的市场后缀: '{market_suffix_part}' (来自 '{code_with_market_suffix}')")

        logger.debug(
            "代码 '%s' 解析为: code='%s', api_market_type='%s'",
            code_with_market_suffix,
            code_part,
            api_market_type_code,
        )
        return code_part, api_market_type_code

    def _call_api_with_version_check(
        self,
        *,
        endpoint: str,
        payload: Dict[str, Any],
        action_name: str,
        request_kind: str = "form",
        require_version: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Execute a POST request with reusable error handling helpers."""

        if require_version and not self._ensure_version_available():
            logger.error("%s失败：仍未能获取有效的自选列表版本号。", action_name)
            return None

        request_payload = payload.copy()
        if require_version:
            request_payload["version"] = str(self._current_version)
            request_payload.setdefault("from", DEFAULT_FROM_PARAM)

        logger.debug("%sAPI请求载荷: %s", action_name, request_payload)

        try:
            if request_kind == "json":
                response = self.api_client.post_form_json(endpoint, data=request_payload)
            else:
                response = self.api_client.post_form_urlencoded(endpoint, data=request_payload)
        except HTTPError as exc:
            status = exc.response.status_code if exc.response else "未知"
            logger.error("%sAPI HTTP错误 (已由APIClient记录): %s", action_name, status)
            return None
        except RequestException as exc:
            logger.error("%sAPI请求错误 (已由APIClient记录): %s", action_name, exc)
            return None
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("%sAPI响应JSON解析错误 (已由APIClient记录): %s", action_name, exc)
            return None
        except Exception:
            logger.exception("%sAPI调用时发生未预料的错误。", action_name)
            return None

        if response and isinstance(response, dict) and response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = response.get("data")
            if require_version:
                self._update_version_from_response_data(data)
            logger.info("%s 成功。", action_name)
            return data

        if response and isinstance(response, dict):
            status_msg: str = response.get("status_msg", "未知业务错误")
            status_code: int = response.get("status_code", -1)
            logger.error("%sAPI业务逻辑错误: %s (代码: %s)", action_name, status_msg, status_code)
        elif response is not None:
            logger.error("%sAPI返回了非预期的格式: %s", action_name, type(response))
        return None

    def _modify_group_item_api_call(
        self,
        endpoint: str,
        group_id: str,
        item_code: str,
        api_item_type_code: str,
        action_name: str = "操作",
    ) -> Optional[Dict[str, Any]]:
        """Internal helper shared by add & delete stock flows."""

        logger.info(
            "准备 %s 项目 '%s' (类型: %s) 到分组ID '%s'，API端点: %s",
            action_name,
            item_code,
            api_item_type_code,
            group_id,
            endpoint,
        )

        payload: Dict[str, Any] = {
            "id": group_id,
            "content": f"{item_code},{api_item_type_code}",
            "num": "1",
        }

        return self._call_api_with_version_check(
            endpoint=endpoint,
            payload=payload,
            action_name=f"{action_name}项目",
        )

    def _modify_group_api_call(
        self,
        endpoint: str,
        payload: Dict[str, str],
        action_name: str = "操作",
    ) -> Optional[Dict[str, Any]]:
        """Wrap add/delete group calls with shared boilerplate."""

        return self._call_api_with_version_check(
            endpoint=endpoint,
            payload=payload,
            action_name=f"{action_name}分组",
        )

    def _share_group_api_call(
        self,
        endpoint: str,
        group_id: str,
        group_name: str,
        valid_time: int,
        action_name: str = "操作",
    ) -> Optional[Dict[str, Any]]:
        """Trigger the sharing endpoint which does not require a version stamp."""

        cookies = self.api_client.get_cookies()
        userid = cookies.get("userid")
        if not userid:
            logger.error("分享分组失败：cookies 中缺少 userid 字段。")
            return None

        biz_suffix = group_id.split("_", 1)[1] if "_" in group_id else group_id
        payload: Dict[str, Any] = {
            "biz": "selfstock",
            "valid_time": int(valid_time),
            "biz_key": f"{userid}_{biz_suffix}",
            "name": group_name,
            "url_style": 0,
        }

        result = self._call_api_with_version_check(
            endpoint=endpoint,
            payload=payload,
            action_name=f"{action_name}分享",
            request_kind="json",
            require_version=False,
        )

        if result:
            share_url = result.get("share_url") if isinstance(result, dict) else None
            logger.info("分享分组 '%s' 成功。链接: %s", group_name, share_url or "未知")
        return result

    def add_item_to_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        """Add a security into a target group.

        Args:
            group_identifier: 分组名称或分组 ID。
            code_with_market_suffix: ``CODE.MARKET`` 形式的股票代码。

        Returns:
            dict | None: API ``data`` 节点（包含最新 ``version`` 等字段），失败时为
            ``None``。
        """

        logger.info("尝试添加项目 '%s' 到分组 '%s'...", code_with_market_suffix, group_identifier)
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error("添加项目失败: 未能找到分组 '%s'。", group_identifier)
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as exc:
            logger.error("添加项目失败: 解析代码 '%s' 时出错 - %s", code_with_market_suffix, exc)
            return None

        api_result = self._modify_group_item_api_call(
            ADD_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="添加",
        )

        if api_result:
            logger.info("项目 '%s' 添加API调用成功，正在刷新分组缓存...", code_with_market_suffix)
            self.get_all_groups(use_cache=False)
        else:
            logger.error("添加项目 '%s' 到分组 '%s' 最终失败。", code_with_market_suffix, group_identifier)
        return api_result

    def delete_item_from_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        """Remove a security from the given group.

        Args:
            group_identifier: 分组名称或 ID。
            code_with_market_suffix: ``CODE.MARKET`` 形式的股票代码。

        Returns:
            dict | None: API ``data`` 节点，失败时为 ``None``。
        """

        logger.info("尝试删除项目 '%s' 从分组 '%s'...", code_with_market_suffix, group_identifier)
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error("删除项目失败: 未能找到分组 '%s'。", group_identifier)
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as exc:
            logger.error("删除项目失败: 解析代码 '%s' 时出错 - %s", code_with_market_suffix, exc)
            return None

        api_result = self._modify_group_item_api_call(
            DELETE_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="删除",
        )

        if api_result:
            logger.info("项目 '%s' 删除API调用成功，正在刷新分组缓存...", code_with_market_suffix)
            self.get_all_groups(use_cache=False)
        else:
            logger.error("删除项目 '%s' 从分组 '%s' 最终失败。", code_with_market_suffix, group_identifier)
        return api_result

    def add_group(self, group_name: str) -> Optional[Dict[str, Any]]:
        """Create a new empty group on the server.

        Args:
            group_name: 新分组的展示名称。

        Returns:
            dict | None: API ``data`` 节点，包含新分组 ID 等信息。
        """

        logger.info("尝试添加分组 '%s'…", group_name)
        if not group_name:
            logger.error("添加分组失败：分组名称不能为空。")
            return None

        payload = {
            "name": group_name,
            "type": "0",
        }
        api_result = self._modify_group_api_call(ADD_GROUP_ENDPOINT, payload, action_name="添加")

        if api_result:
            logger.info("添加分组 '%s' 成功，刷新分组缓存…", group_name)
            self.get_all_groups(use_cache=False)
        else:
            logger.error("添加分组 '%s' 最终失败。", group_name)
        return api_result

    def delete_group(self, group_identifier: str) -> Optional[Dict[str, Any]]:
        """Delete an existing group by name or ID.

        Args:
            group_identifier: 分组名称或 ID。

        Returns:
            dict | None: API ``data`` 节点，失败时为 ``None``。
        """

        logger.info("尝试删除分组 '%s'…", group_identifier)
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error("删除分组失败：未能找到 '%s'。", group_identifier)
            return None

        payload = {
            "ids": target_group_id,
        }
        api_result = self._modify_group_api_call(DELETE_GROUP_ENDPOINT, payload, action_name="删除")

        if api_result:
            logger.info("删除分组 '%s' 成功，刷新分组缓存…", group_identifier)
            self.get_all_groups(use_cache=False)
        else:
            logger.error("删除分组 '%s' 最终失败。", group_identifier)
        return api_result

    def share_group(self, group_identifier: str, valid_time: int) -> Optional[Dict[str, Any]]:
        """Create a share link for a group.

        Args:
            group_identifier: 分组名称或 ID。
            valid_time: 链接有效期（秒）。

        Returns:
            dict | None: API ``data`` 节点（通常包含 ``share_url``）。
        """

        logger.info("尝试分享分组 '%s'，有效期 %s 秒…", group_identifier, valid_time)
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error("分享分组失败：未能找到 '%s'。", group_identifier)
            return None

        api_result = self._share_group_api_call(
            SHARE_GROUP_ENDPOINT,
            target_group_id,
            group_identifier,
            valid_time,
            action_name="分享",
        )

        if not api_result:
            logger.error("分享分组 '%s' 最终失败。", group_identifier)
        return api_result

    def _resolve_cookies_via_auth_method(
        self,
        auth_method: str,
        browser_name: str,
        username: Optional[str],
        password: Optional[str],
    ) -> Optional[Dict[str, str]]:
        method = (auth_method or "").strip().lower()
        if not method:
            logger.info("未指定 auth_method，跳过自动加载 cookies。")
            return None

        if method == "browser":
            cache_key = self._browser_cache_key(browser_name)
            return self._fetch_cookies_with_cache(cache_key, lambda: self._load_cookies_from_browser(browser_name))
        if method in {"credentials", "login"}:
            if not username or not password:
                logger.error("auth_method=credentials 需要提供 username 与 password。")
                return None
            cache_key = self._credentials_cache_key(username)
            return self._fetch_cookies_with_cache(
                cache_key,
                lambda: self._load_cookies_from_credentials(username, password),
            )
        if method in {"none", "skip"}:
            logger.info("auth_method 设为 %s，跳过自动加载 cookies。", auth_method)
            return None

        logger.error("未知的 auth_method: %s。可选值: browser, credentials。", auth_method)
        return None

    def _fetch_cookies_with_cache(
        self,
        cache_key: str,
        loader: Callable[[], Optional[Dict[str, str]]],
    ) -> Optional[Dict[str, str]]:
        cached = read_cached_cookies(self._cookie_cache_path, cache_key, self._cookie_cache_ttl_seconds)
        if cached:
            logger.info("命中 cookies 缓存: %s", cache_key)
            return cached

        logger.info("缓存未命中，准备刷新 cookies: %s", cache_key)
        fresh = loader()
        if fresh:
            write_cookie_cache(self._cookie_cache_path, cache_key, fresh)
        return fresh

    def _load_cookies_from_browser(self, browser_name: str) -> Optional[Dict[str, str]]:
        logger.info("尝试从浏览器 '%s' 读取 cookies…", browser_name)
        try:
            raw_cookies = load_browser_cookie(browser_name)
        except Exception:
            logger.exception("从浏览器读取 cookies 失败。")
            return None

        cookie_dict: Dict[str, str] = {}
        for cookie in raw_cookies:
            name = getattr(cookie, "name", None)
            value = getattr(cookie, "value", None)
            if name and value is not None:
                cookie_dict[str(name)] = str(value)

        if cookie_dict:
            logger.info("成功从浏览器 '%s' 读取 %d 个 cookies。", browser_name, len(cookie_dict))
            return cookie_dict

        logger.warning("浏览器 '%s' 中未找到有效的 cookies。", browser_name)
        return None

    def _load_cookies_from_credentials(self, username: str, password: str) -> Optional[Dict[str, str]]:
        logger.info("使用账号密码登录获取 cookies…")
        try:
            session_result = create_session(username=username, password=password)
        except Exception:
            logger.exception("账号密码登录失败，无法获取 cookies。")
            return None

        cookies_payload = session_result.cookies
        if cookies_payload:
            logger.info("账号登录成功，获得 %d 个 cookies。", len(cookies_payload))
            return cookies_payload

        logger.warning("账号登录成功但未返回任何 cookies。")
        return None

    @staticmethod
    def _browser_cache_key(browser_name: str) -> str:
        normalized = (browser_name or "default").lower()
        return f"browser::{normalized}"

    @staticmethod
    def _credentials_cache_key(username: str) -> str:
        digest = hashlib.sha256(username.encode("utf-8")).hexdigest()
        return f"credentials::{digest}"

    def close(self) -> None:
        logger.info("准备关闭 THSUserFavorite 服务...")
        save_groups_cache(self._group_cache_path, self._groups_cache)
        if not self._is_external_api_client:
            self.api_client.close()
        else:
            logger.debug("THSUserFavorite 使用的是外部API客户端，不在此处关闭。")
        logger.info("THSUserFavorite 服务已关闭。")

    def __enter__(self: T_UserFavorite) -> T_UserFavorite:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()

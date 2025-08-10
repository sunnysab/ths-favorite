from dataclasses import dataclass
import httpx
import json
import os
from loguru import logger # 导入 loguru
# 假设 constant.py 和 cookie.py 中的函数已定义
# 建议显式导入，例如:
from constant import market_abbr, market_code
from cookie import load_browser_cookie
from typing import List, Optional, Dict, Any, Set, Union, Tuple, TypeVar, Type

# 全局默认请求头
_DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": "Hexin_Gphone/11.28.03 (Royal Flush) hxtheme/0 innerversion/G037.09.028.1.32 followPhoneSystemTheme/0 userid/500780707 getHXAPPAccessibilityMode/0 hxNewFont/1 isVip/0 getHXAPPFontSetting/normal getHXAPPAdaptOldSetting/0 okhttp/3.14.9",
}


@dataclass(frozen=True)
class THSFavorite:
    """
    同花顺自选股的单个项目数据类。

    Attributes:
        code (str): 项目代码 (例如股票代码 "000001")。
        market (Optional[str]): 项目所属市场的缩写 (例如 "SZ", "SH")。可能为 None。
    """
    code: str
    market: Optional[str] = None

    def __repr__(self) -> str:
        if self.market:
            return f"THSFavorite(code='{self.code}', market='{self.market}')"
        return f"THSFavorite(code='{self.code}')"


class THSFavoriteGroup:
    """
    同花顺自选股的分组类。

    Attributes:
        group_id (str): 分组的唯一标识符。
        name (str): 分组的名称。
        items (List[THSFavorite]): 该分组包含的自选项目列表。
    """
    group_id: str
    name: str
    items: List[THSFavorite]

    def __init__(self, name: str, group_id: str, items: List[THSFavorite]):
        self.name = name
        self.group_id = group_id
        self.items = items

    def __repr__(self) -> str:
        return f"THSFavoriteGroup(name='{self.name}', group_id='{self.group_id}', items_count={len(self.items)})"

    def diff(self, other: 'THSFavoriteGroup') -> Tuple[List[THSFavorite], List[THSFavorite]]:
        if not isinstance(other, THSFavoriteGroup):
            # 可以在这里记录错误，或者让调用者处理
            logger.error(f"类型错误: 比较对象 'other' 必须是 THSFavoriteGroup 类型，而非 {type(other)}。")
            raise TypeError("比较对象 'other' 必须是 THSFavoriteGroup 类型。")

        self_items_set: Set[THSFavorite] = set(self.items)
        other_items_set: Set[THSFavorite] = set(other.items)

        added_items: List[THSFavorite] = list(other_items_set - self_items_set)
        removed_items: List[THSFavorite] = list(self_items_set - other_items_set)
        
        logger.debug(f"分组 '{self.name}' 与 '{other.name}' 比较: 新增 {len(added_items)} 项, 删除 {len(removed_items)} 项。")
        return added_items, removed_items


T_HttpApiClient = TypeVar('T_HttpApiClient', bound='THSHttpApiClient')

class THSHttpApiClient:
    """
    一个通用的 HTTP API 客户端，封装了 httpx 请求的发送、
    Cookie 管理、基本头部设置和错误处理。
    """
    _DEFAULT_RETRY_COUNT: int = 3

    def __init__(self,
                 base_url: str,
                 cookies: Union[str, Dict[str, str], None] = None,
                 headers: Optional[Dict[str, str]] = None,
                 client: Optional[httpx.Client] = None,
                 timeout: float = 10.0,
                 http2: bool = False): # 默认不启用 HTTP/2，与您提供的一致
        self.base_url: str = base_url.rstrip('/')
        logger.debug(f"THSHttpApiClient 初始化: base_url='{self.base_url}', http2={http2}, timeout={timeout}s")
        self._internal_cookies: Dict[str, str] = {}

        if client:
            self._client: httpx.Client = client
            self._is_external_client: bool = True
            logger.info("使用外部传入的 httpx.Client 实例。")
            if cookies:
                self.set_cookies(cookies)
        else:
            logger.info(f"创建内部 httpx.Client 实例: http2={http2}, timeout={timeout}s。")
            self._client = httpx.Client(http2=http2, timeout=timeout)
            self._is_external_client = False
            if cookies:
                self.set_cookies(cookies)
            elif os.environ.get("AUTO_LOAD_BROWSER_COOKIES", "true").lower() == "true":
                logger.info("未直接提供cookies，且 AUTO_LOAD_BROWSER_COOKIES 环境变量为 true，尝试从浏览器加载...")
                self.load_cookies_from_browser("firefox") # 示例浏览器
            else:
                logger.warning("未提供cookies，且未启用从浏览器自动加载cookies功能。请求可能因缺少认证而失败。")


        self._default_headers: Dict[str, str] = headers.copy() if headers else _DEFAULT_HEADERS.copy()
        logger.debug(f"默认请求头已设置: {self._default_headers}")

    def _parse_cookies_str(self, cookies_str: str) -> Dict[str, str]:
        cookie_dict: Dict[str, str] = {}
        if not cookies_str or not isinstance(cookies_str, str):
            return cookie_dict
        pairs: List[str] = cookies_str.split(';')
        for pair_str in pairs:
            pair_str = pair_str.strip()
            if '=' in pair_str:
                name, value = pair_str.split('=', 1)
                cookie_dict[name.strip()] = value.strip()
        logger.debug(f"从字符串解析得到 {len(cookie_dict)} 个cookies。")
        return cookie_dict

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        if isinstance(cookies_input, str):
            self._internal_cookies = self._parse_cookies_str(cookies_input)
        elif isinstance(cookies_input, dict):
            self._internal_cookies = cookies_input.copy()
        else:
            logger.error(f"设置cookies失败: cookies_input 类型错误，应为字符串或字典，得到 {type(cookies_input)}。")
            raise TypeError("cookies_input 参数必须是字符串或字典类型。")

        if hasattr(self, '_client'):
            self._client.cookies.clear()
            self._client.cookies.update(self._internal_cookies)
            logger.info(f"客户端 cookies 已更新，共 {len(self._internal_cookies)} 个。")
        else:
            logger.warning("尝试设置 cookies，但内部 _client 尚未初始化。")


    def get_cookies(self) -> Dict[str, str]:
        logger.debug(f"获取当前 cookies 副本，共 {len(self._internal_cookies)} 个。")
        return self._internal_cookies.copy()

    def load_cookies_from_browser(self, browser_name: str) -> None:
        logger.info(f"尝试从浏览器 '{browser_name}' 加载 cookies...")
        try:
            raw_cookies = load_browser_cookie(browser_name) # 您可能需要根据 load_browser_cookie 的实际行为调整
            if not raw_cookies:
                logger.warning(f"从浏览器 '{browser_name}' 未能加载到任何 cookies 数据。")
                return

            cookies_dict: Dict[str, str]
            if isinstance(raw_cookies, dict): # 如果直接返回字典
                 cookies_dict = {k: v for k, v in raw_cookies.items() if v is not None}
            elif all(hasattr(c, 'name') and hasattr(c, 'value') for c in raw_cookies): # 假设是 Cookie 对象列表
                cookies_dict = {cookie.name: cookie.value
                                for cookie in raw_cookies
                                if cookie.value is not None and cookie.name is not None}
            else:
                logger.error(f"从浏览器 '{browser_name}' 加载的 cookies 格式未知或不兼容: {type(raw_cookies)}")
                return

            if cookies_dict:
                self.set_cookies(cookies_dict)
                logger.info(f"已成功从浏览器 '{browser_name}' 加载并设置 {len(cookies_dict)} 个 cookies。")
            else:
                logger.warning(f"从浏览器 '{browser_name}' 解析后未得到有效的 cookies。")

        except Exception as e:
            logger.exception(f"从浏览器 '{browser_name}' 加载 cookies 时发生严重错误。")


    def _prepare_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        final_headers: Dict[str, str] = self._default_headers.copy()
        if additional_headers:
            final_headers.update(additional_headers)
        logger.debug(f"准备请求头: {final_headers}")
        return final_headers

    def request(self,
                method: str,
                endpoint: str,
                params: Optional[Dict[str, Any]] = None,
                data: Optional[Dict[str, Any]] = None,
                json_payload: Optional[Any] = None,
                headers: Optional[Dict[str, str]] = None
               ) -> Dict[str, Any]:
        full_url: str = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers: Dict[str, str] = self._prepare_headers(headers)

        logger.info(f"发送 {method} 请求到 {full_url}")
        logger.debug(f"请求参数: {params}, 表单数据: {data}, JSON载荷: {json_payload is not None}")

        response = None
        try:
            response: httpx.Response = self._client.request(
                method,
                full_url,
                params=params,
                data=data,
                json=json_payload,
                headers=request_headers
            )
            logger.debug(f"收到响应: 状态码 {response.status_code}, URL: {response.url}")
            response.raise_for_status()
            
            # 尝试解析JSON
            # 如果API可能返回空字符串作为成功响应，并且希望将其视为空字典，则需要特殊处理
            if not response.text: # 检查响应体是否为空
                logger.info(f"请求 {full_url} 成功，但响应体为空。返回空字典。")
                return {}
            
            json_response = response.json()
            logger.debug(f"成功解析响应为JSON: {str(json_response)[:200]}...") # 截断过长的日志
            return json_response

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误 ({method} {full_url}): 状态码 {e.response.status_code}, 响应: {e.response.text[:200]}...")
            raise # 重新抛出，让调用者处理
        except httpx.RequestError as e:
            logger.error(f"请求错误 ({method} {full_url}): {e}")
            raise
        except json.JSONDecodeError as e:
            resp_text_preview = ''
            try:
                # 在此作用域中，response 仅在 try 块成功时存在
                resp_text_preview = response.text[:200]  # type: ignore[name-defined]
            except Exception:
                pass
            logger.error(f"JSON解码错误 ({method} {full_url}): {e}. 响应文本: {resp_text_preview}...")
            raise


    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        return self.request("GET", endpoint, params=params, **kwargs)

    def post_form_urlencoded(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        custom_headers: Dict[str, str] = kwargs.pop('headers', {})
        if 'Content-Type' not in custom_headers and 'content-type' not in custom_headers:
             custom_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        return self.request("POST", endpoint, data=data, headers=custom_headers, **kwargs)

    def post_json(self, endpoint: str, json_payload: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        return self.request("POST", endpoint, json_payload=json_payload, **kwargs)

    def close(self) -> None:
        if not self._is_external_client and hasattr(self._client, "is_closed") and not self._client.is_closed:
            self._client.close()
            logger.info("内部 THSHttpApiClient 的 httpx.Client 已关闭。")
        elif self._is_external_client:
            logger.debug("THSHttpApiClient 使用的是外部 Client，不在此处关闭。")


    def __enter__(self: T_HttpApiClient) -> T_HttpApiClient:
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        self.close()

T_UserFavorite = TypeVar('T_UserFavorite', bound='THSUserFavorite')

class THSUserFavorite:
    """
    管理同花顺用户自选股的服务类。
    提供获取分组、添加/删除自选项目等功能，并支持本地缓存。
    """
    _API_BASE_URL: str = "https://ugc.10jqka.com.cn"
    _QUERY_ENDPOINT: str = "/optdata/selfgroup/open/api/group/v1/query"
    _ADD_ITEM_ENDPOINT: str = "/optdata/selfgroup/open/api/content/v1/add"
    _DELETE_ITEM_ENDPOINT: str = "/optdata/selfgroup/open/api/content/v1/delete"
    _CACHE_FILE: str = "ths_favorite_cache.json"

    def __init__(self,
                 cookies: Union[str, Dict[str, str], None] = None,
                 api_client: Optional[THSHttpApiClient] = None):
        logger.info("THSUserFavorite 服务初始化...")
        if api_client:
            self.api_client: THSHttpApiClient = api_client
            self._is_external_api_client: bool = True
            logger.info("使用外部传入的 THSHttpApiClient 实例。")
        else:
            logger.info("创建内部 THSHttpApiClient 实例。")
            self.api_client = THSHttpApiClient(
                base_url=self._API_BASE_URL,
                cookies=cookies,
                headers=_DEFAULT_HEADERS
            )
            self._is_external_api_client = False

        self._current_version: Optional[Union[str, int]] = None
        self._groups_cache: Dict[str, THSFavoriteGroup] = {}
        self._load_cache()

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        logger.info("通过 THSUserFavorite 设置 API 客户端 cookies...")
        self.api_client.set_cookies(cookies_input)

    def _update_version_from_response_data(self, response_data: Optional[Dict[str, Any]]) -> None:
        if response_data and isinstance(response_data, dict) and "version" in response_data:
            new_version: Union[str, int] = response_data["version"]
            logger.debug(f"自选列表版本号从 {self._current_version} 更新为 {new_version}")
            self._current_version = new_version
        else:
            logger.debug("响应数据中未找到版本号，或数据格式不符，版本号未更新。")


    def get_raw_group_data(self) -> Optional[Dict[str, Any]]:
        logger.info(f"尝试从API获取原始分组数据: {self._QUERY_ENDPOINT}")
        params: Dict[str, str] = {
            "from": "sjcg_gphone",
            "types": "0,1"
        }
        api_response: Optional[Dict[str, Any]] = None
        try:
            api_response = self.api_client.get(self._QUERY_ENDPOINT, params=params)
        except httpx.HTTPStatusError as e: # 已在api_client.request中记录，这里可选择再次记录或简化
            logger.error(f"获取原始分组数据时发生HTTP状态错误 (已由APIClient记录): {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"获取原始分组数据时发生请求错误 (已由APIClient记录): {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"获取原始分组数据时发生JSON解码错误 (已由APIClient记录): {e}")
            return None
        except Exception as e:
            logger.exception("获取原始分组数据时发生未预料的错误。")
            return None

        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = api_response.get("data")
            self._update_version_from_response_data(data)
            logger.info("成功获取并解析了原始分组数据。")
            return data
        elif api_response and isinstance(api_response, dict):
            status_msg: str = api_response.get("status_msg", "未知业务错误")
            status_code: int = api_response.get("status_code", -1)
            logger.error(f"获取分组API业务逻辑错误: {status_msg} (代码: {status_code})")
        elif api_response is not None:
            logger.error(f"获取分组API返回了非预期的格式: {type(api_response)}")
        # 如果 api_response 为 None，说明在APIClient层面或此处的try-except中已处理并记录错误
        return None

    def _load_cache(self) -> None:
        logger.info(f"尝试从文件 '{self._CACHE_FILE}' 加载分组缓存...")
        if not os.path.exists(self._CACHE_FILE):
            logger.info(f"缓存文件 '{self._CACHE_FILE}' 不存在，跳过加载。")
            return
        try:
            with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_groups_data: List[Dict[str, Any]] = json.load(f)
            temp_cache: Dict[str, THSFavoriteGroup] = {}
            for group_data in cached_groups_data:
                items: List[THSFavorite] = [
                    THSFavorite(code=item_dict['code'], market=item_dict.get('market'))
                    for item_dict in group_data.get('items', [])
                ]
                group_name: Optional[str] = group_data.get('name')
                group_id: Optional[str] = group_data.get('group_id')

                if group_name and group_id:
                    group = THSFavoriteGroup(name=group_name, group_id=group_id, items=items)
                    temp_cache[group.name] = group
                else:
                    logger.warning(f"缓存中发现不完整的分组数据，已跳过: {group_data}")
            self._groups_cache = temp_cache
            logger.info(f"已从 '{self._CACHE_FILE}' 加载 {len(self._groups_cache)} 个分组到缓存。")
        except json.JSONDecodeError:
            logger.error(f"错误: 缓存文件 '{self._CACHE_FILE}' 内容不是有效的JSON格式。缓存未加载。")
        except Exception as e:
            logger.exception(f"从文件加载缓存时发生未知错误。")


    def _save_cache(self) -> None:
        logger.info(f"尝试将 {len(self._groups_cache)} 个分组保存到缓存文件 '{self._CACHE_FILE}'...")
        # if not self._groups_cache:
        #     logger.debug("当前缓存为空，跳过保存到文件。")
        #     return
        try:
            cache_data_to_save: List[Dict[str, Any]] = []
            for group_obj in self._groups_cache.values(): # Iterate over values directly
                group_data: Dict[str, Any] = {
                    'name': group_obj.name,
                    'group_id': group_obj.group_id,
                    'items': [{'code': item.code, 'market': item.market} for item in group_obj.items]
                }
                cache_data_to_save.append(group_data)

            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data_to_save, f, ensure_ascii=False, indent=2)
            logger.info(f"已成功将 {len(cache_data_to_save)} 个分组保存到缓存文件 '{self._CACHE_FILE}'。")
        except Exception as e:
            logger.exception(f"保存缓存到文件时发生错误。")


    def parse_group_list(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.debug("开始解析API返回的原始分组数据...")
        parsed_groups_raw_info: List[Dict[str, Any]] = []
        if not raw_data or not isinstance(raw_data, dict) or "group_list" not in raw_data:
            logger.warning("原始数据无效或不包含 'group_list' 键，无法解析。返回空列表。")
            return parsed_groups_raw_info

        api_group_list: List[Dict[str, Any]] = raw_data.get("group_list", [])
        logger.debug(f"API返回了 {len(api_group_list)} 个原始分组条目。")

        for i, group_dict_from_api in enumerate(api_group_list):
            if not isinstance(group_dict_from_api, dict):
                logger.warning(f"API返回的group_list中第 {i+1} 个元素不是预期的字典类型，已跳过: {group_dict_from_api}")
                continue

            current_group_parsed_info: Dict[str, Any] = {
                "id": group_dict_from_api.get("id"),
                "name": group_dict_from_api.get("name"),
                "api_type_code": group_dict_from_api.get("type"),
                "num_items_api": group_dict_from_api.get("num"),
                "attrs": group_dict_from_api.get("attrs", {}),
                "item_details": []
            }
            logger.debug(f"正在解析分组 '{current_group_parsed_info['name']}' (ID: {current_group_parsed_info['id']})...")

            content_str: Optional[str] = group_dict_from_api.get("content")
            if isinstance(content_str, str) and content_str:
                parts: List[str] = content_str.split(',', 1)
                item_codes_segment: str = parts[0]
                api_item_type_codes_segment: str = parts[1] if len(parts) > 1 else ""

                item_codes_list: List[str] = [code for code in item_codes_segment.split('|') if code]
                api_item_type_codes_list: List[str] = [tc for tc in api_item_type_codes_segment.split('|') if tc]
                
                logger.debug(f"分组 '{current_group_parsed_info['name']}' 包含 {len(item_codes_list)} 个项目代码，{len(api_item_type_codes_list)} 个API类型代码。")

                for j, item_code_str in enumerate(item_codes_list):
                    api_item_type_code: Optional[str] = api_item_type_codes_list[j] if j < len(api_item_type_codes_list) else None
                    current_group_parsed_info["item_details"].append({
                        "code": item_code_str,
                        "api_type": api_item_type_code
                    })
            else:
                logger.debug(f"分组 '{current_group_parsed_info['name']}' 的 'content' 字段为空或格式不正确。")
            
            parsed_groups_raw_info.append(current_group_parsed_info)
        logger.info(f"成功解析了 {len(parsed_groups_raw_info)} 个分组的原始信息。")
        return parsed_groups_raw_info


    def get_all_groups(self, use_cache: bool = False) -> Dict[str, THSFavoriteGroup]:
        logger.info("开始获取所有自选股分组信息...")
        formatted_groups: Dict[str, THSFavoriteGroup] = {}
        raw_data_from_api = self.get_raw_group_data() # 此方法内部已有日志

        if raw_data_from_api:
            logger.info("成功从API获取原始数据，开始转换为 THSFavoriteGroup 对象...")
            parsed_group_list_raw_info = self.parse_group_list(raw_data_from_api) # 此方法内部已有日志

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
                            logger.warning(f"在分组 '{group_name}' 中发现无代码的项目详情: {detail}")


                    ths_favorite_group = THSFavoriteGroup(name=group_name, group_id=group_id, items=favorite_items_list)
                    formatted_groups[group_name] = ths_favorite_group
                    logger.debug(f"已创建 THSFavoriteGroup 对象: '{group_name}' (ID: {group_id}), 项目数: {len(favorite_items_list)}")
                else:
                    logger.warning(f"解析时发现无名称或ID的分组原始数据，已跳过: {group_raw_info}")
            
            self._groups_cache = formatted_groups
            self._save_cache() # 此方法内部已有日志
            logger.info(f"成功获取并处理了 {len(formatted_groups)} 个分组。缓存已更新。")
            return formatted_groups
        else:
            logger.error("从API获取分组数据失败。")
            if use_cache:
                logger.warning("尝试使用内存中的旧缓存数据。")
                return self._groups_cache.copy()
            logger.warning("未启用缓存或缓存为空，返回空的分组列表。")
            return {}

    def _get_group_id_by_identifier(self, group_identifier: str) -> Optional[str]:
        logger.debug(f"尝试通过标识符 '{group_identifier}' 获取分组ID...")
        if not self._groups_cache:
            logger.info("内部缓存为空，将尝试从API获取最新分组数据以查找分组ID...")
            self.get_all_groups(use_cache=False) # 强制刷新缓存

        for group_obj in self._groups_cache.values():
            if group_obj.group_id == group_identifier:
                logger.debug(f"通过分组ID '{group_identifier}' 匹配成功。")
                return group_obj.group_id
        if group_identifier in self._groups_cache:
            logger.debug(f"通过分组名称 '{group_identifier}' 匹配成功。")
            return self._groups_cache[group_identifier].group_id

        logger.warning(f"未能通过标识符 '{group_identifier}' 找到对应的分组ID。当前缓存中有 {len(self._groups_cache)} 个分组。")
        return None

    def _parse_code_with_market_suffix(self, code_with_market_suffix: str) -> Tuple[str, str]:
        logger.debug(f"尝试解析带市场后缀的代码: '{code_with_market_suffix}'")
        if '.' not in code_with_market_suffix:
            logger.error(f"股票代码格式无效: '{code_with_market_suffix}'。缺少 '.' 分隔符。")
            raise ValueError(f"股票代码格式无效: '{code_with_market_suffix}'。预期格式: CODE.MARKET_SUFFIX")

        code_part, market_suffix_part = code_with_market_suffix.rsplit('.', 1)
        api_market_type_code: Optional[str] = market_code(market_suffix_part.upper())

        if not api_market_type_code:
            logger.error(f"未知的市场后缀: '{market_suffix_part}' (来自代码 '{code_with_market_suffix}')")
            raise ValueError(f"未知的市场后缀: '{market_suffix_part}' (来自 '{code_with_market_suffix}')")
        
        logger.debug(f"代码 '{code_with_market_suffix}' 解析为: code='{code_part}', api_market_type='{api_market_type_code}'")
        return code_part, api_market_type_code


    def _modify_group_item_api_call(self,
                                    endpoint: str,
                                    group_id: str,
                                    item_code: str,
                                    api_item_type_code: str,
                                    action_name: str = "操作"
                                   ) -> Optional[Dict[str, Any]]:
        logger.info(f"准备 {action_name} 项目 '{item_code}' (类型: {api_item_type_code}) 到分组ID '{group_id}'，API端点: {endpoint}")

        # 自动确保版本号存在：如果当前版本号未知，则主动从API刷新一次分组（不使用缓存）
        if self._current_version is None:
            logger.info(f"当前版本号未知，自动调用 get_all_groups() 以获取版本号后再执行{action_name}操作…")
            self.get_all_groups(use_cache=False)
            if self._current_version is None:
                logger.error(f"{action_name}项目失败：仍未能获取有效的自选列表版本号（调用 get_all_groups() 后依旧为 None）。")
                return None
            else:
                logger.debug(f"已自动获取到版本号: {self._current_version}，继续后续 {action_name} 操作。")

        payload: Dict[str, str] = {
            "version": str(self._current_version),
            "from": "sjcg_gphone",
            "id": group_id,
            "content": f"{item_code},{api_item_type_code}",
            "num": "1"
        }
        logger.debug(f"{action_name}项目API请求载荷: {payload}")
        
        api_response: Optional[Dict[str, Any]] = None
        try:
            api_response = self.api_client.post_form_urlencoded(endpoint, data=payload)
        except httpx.HTTPStatusError as e:
            logger.error(f"{action_name}项目API HTTP错误 (已由APIClient记录): {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"{action_name}项目API请求错误 (已由APIClient记录): {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"{action_name}项目API响应JSON解析错误 (已由APIClient记录): {e}")
            return None
        except Exception as e:
            logger.exception(f"{action_name}项目API调用时发生未预料的错误。")
            return None

        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = api_response.get("data")
            self._update_version_from_response_data(data)
            logger.info(f"项目 '{item_code}' {action_name}到分组 '{group_id}' 成功。新版本: {self._current_version}")
            return data
        elif api_response and isinstance(api_response, dict):
            status_msg: str = api_response.get("status_msg", "未知业务错误")
            status_code: int = api_response.get("status_code", -1)
            logger.error(f"{action_name}项目API业务逻辑错误: {status_msg} (代码: {status_code})")
        elif api_response is not None:
            logger.error(f"{action_name}项目API返回了非预期的格式: {type(api_response)}")
        return None


    def add_item_to_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        logger.info(f"尝试添加项目 '{code_with_market_suffix}' 到分组 '{group_identifier}'...")
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error(f"添加项目失败: 未能找到分组 '{group_identifier}'。")
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as e: # _parse_code_with_market_suffix 内部已记录错误
            logger.error(f"添加项目失败: 解析代码 '{code_with_market_suffix}' 时出错 - {e}")
            return None

        api_result = self._modify_group_item_api_call(
            self._ADD_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="添加"
        )

        if api_result:
            logger.info(f"项目 '{code_with_market_suffix}' 添加API调用成功，正在刷新分组缓存...")
            self.get_all_groups(use_cache=False)
        else:
            logger.error(f"添加项目 '{code_with_market_suffix}' 到分组 '{group_identifier}' 最终失败。")
        return api_result

    def delete_item_from_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        logger.info(f"尝试删除项目 '{code_with_market_suffix}' 从分组 '{group_identifier}'...")
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            logger.error(f"删除项目失败: 未能找到分组 '{group_identifier}'。")
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as e:
            logger.error(f"删除项目失败: 解析代码 '{code_with_market_suffix}' 时出错 - {e}")
            return None

        api_result = self._modify_group_item_api_call(
            self._DELETE_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="删除"
        )

        if api_result:
            logger.info(f"项目 '{code_with_market_suffix}' 删除API调用成功，正在刷新分组缓存...")
            self.get_all_groups(use_cache=False)
        else:
            logger.error(f"删除项目 '{code_with_market_suffix}' 从分组 '{group_identifier}' 最终失败。")
        return api_result

    def close(self) -> None:
        logger.info("准备关闭 THSUserFavorite 服务...")
        self._save_cache()
        if not self._is_external_api_client:
            self.api_client.close() # api_client.close() 内部已有日志
        else:
            logger.debug("THSUserFavorite 使用的是外部API客户端，不在此处关闭。")
        logger.info("THSUserFavorite 服务已关闭。")


    def __enter__(self: T_UserFavorite) -> T_UserFavorite:
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        self.close()


if __name__ == "__main__":
    import sys
    logger.remove() # 移除默认处理器
    logger.add(sys.stderr, level="DEBUG", # 控制台日志级别可以设为 DEBUG 以便测试
               format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    logger.add("ths_favorite_app.log", rotation="10 MB", level="INFO", encoding="utf-8") # 文件日志级别可以设为 INFO

    logger.info("开始 THSUserFavorite 主程序测试...")

    os.environ["AUTO_LOAD_BROWSER_COOKIES"] = "true" # 测试自动加载
    test_cookies = None # 如果 AUTO_LOAD_BROWSER_COOKIES 为 true, 会尝试加载

    with THSUserFavorite(cookies=test_cookies) as ths_service:
        logger.info("\n--- 步骤1: 获取所有分组 (可能会从API获取或使用缓存) ---")
        all_current_groups = ths_service.get_all_groups(use_cache=True)

        if not all_current_groups:
            logger.warning("未能获取到任何分组信息。测试可能无法继续。")
        else:
            logger.info(f"成功获取到 {len(all_current_groups)} 个分组:")
            for name, group_obj in all_current_groups.items():
                logger.info(f"  分组名: {group_obj.name} (ID: {group_obj.group_id}), 项目数: {len(group_obj.items)}")
                if group_obj.items:
                    logger.debug(f"    示例项目: {group_obj.items[0]}")

            test_group_name_or_id = ""
            if all_current_groups:
                try:
                    first_group_name = list(all_current_groups.keys())[0]
                    test_group_name_or_id = first_group_name
                    logger.info(f"\n将使用分组 '{test_group_name_or_id}' 进行添加/删除测试。")

                    stock_to_add_delete = "000001.SZ" # 平安银行

                    logger.info(f"\n--- 步骤2: 尝试向分组 '{test_group_name_or_id}' 添加股票 '{stock_to_add_delete}' ---")
                    add_result = ths_service.add_item_to_group(test_group_name_or_id, stock_to_add_delete)
                    if add_result:
                        logger.info(f"添加API调用成功，响应数据: {add_result}")
                        # 验证是否真的添加 (需要重新获取或检查缓存)
                        temp_groups_after_add = ths_service._groups_cache # 访问内部缓存
                        added_item_found = any(
                            item.code == stock_to_add_delete.split('.')[0] and item.market == stock_to_add_delete.split('.')[1].upper()
                            for item in temp_groups_after_add.get(test_group_name_or_id, THSFavoriteGroup("","",[])).items
                        )
                        if added_item_found:
                            logger.info(f"验证成功：'{stock_to_add_delete}' 已存在于分组 '{test_group_name_or_id}' 的缓存中。")
                        else:
                            logger.warning(f"验证警告：'{stock_to_add_delete}' 未在分组 '{test_group_name_or_id}' 的缓存中找到。")
                    else:
                        logger.error(f"添加股票 '{stock_to_add_delete}' 失败。")


                    logger.info(f"\n--- 步骤3: 尝试从分组 '{test_group_name_or_id}' 删除股票 '{stock_to_add_delete}' ---")
                    delete_result = ths_service.delete_item_from_group(test_group_name_or_id, stock_to_add_delete)
                    if delete_result:
                        logger.info(f"删除API调用成功，响应数据: {delete_result}")
                    else:
                        logger.error(f"删除股票 '{stock_to_add_delete}' 失败。")

                except IndexError:
                     logger.error("分组列表为空，无法选择测试分组。")


                logger.info("\n--- 步骤4: 再次获取所有分组查看最终状态 (强制刷新) ---")
                final_groups = ths_service.get_all_groups(use_cache=False)
                if final_groups:
                    for name, group_obj in final_groups.items():
                        logger.info(f"  最终分组: {group_obj.name} (ID: {group_obj.group_id}), 项目数: {len(group_obj.items)}")
                else:
                    logger.warning("最终未能获取到分组信息。")
            else:
                logger.warning("没有可用的分组进行添加/删除测试。")

    logger.info("\nTHSUserFavorite 主程序测试结束。")
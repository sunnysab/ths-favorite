from dataclasses import dataclass
import httpx
import json
import os
from constant import market_abbr, market_code
from cookie import load_browser_cookie
from typing import List, Optional, Dict, Any, Set, Union, Tuple, TypeVar, Type

# 全局默认请求头
_DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": "Hexin_Gphone/11.28.03 (Royal Flush) hxtheme/0 innerversion/G037.09.028.1.32 followPhoneSystemTheme/0 userid/500780707 getHXAPPAccessibilityMode/0 hxNewFont/1 isVip/0 getHXAPPFontSetting/normal getHXAPPAdaptOldSetting/0 okhttp/3.14.9",
    # "Host": "ugc.10jqka.com.cn", # Host 通常由 httpx 根据 URL 自动设置
}


@dataclass(frozen=True) # frozen=True 使其实例不可变且可哈希
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
        """返回对象的字符串表示形式，方便调试。"""
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
        """
        初始化自选股分组。

        Args:
            name (str): 分组名称。
            group_id (str): 分组ID。
            items (List[THSFavorite]): 分组内的项目列表。
        """
        self.name = name
        self.group_id = group_id
        self.items = items

    def __repr__(self) -> str:
        """返回对象的字符串表示形式，方便调试。"""
        return f"THSFavoriteGroup(name='{self.name}', group_id='{self.group_id}', items_count={len(self.items)})"

    def diff(self, other: 'THSFavoriteGroup') -> Tuple[List[THSFavorite], List[THSFavorite]]:
        """
        比较当前分组与另一个分组 (`other`) 的项目差异。

        Args:
            other (THSFavoriteGroup): 用于比较的另一个分组对象。

        Returns:
            Tuple[List[THSFavorite], List[THSFavorite]]: 一个元组，包含两个列表：
                - 第一个列表 (`added_items`): 在 `other` 分组中存在，但在当前分组中不存在的项目。
                - 第二个列表 (`removed_items`): 在当前分组中存在，但在 `other` 分组中不存在的项目。

        Raises:
            TypeError: 如果 `other` 参数不是 `THSFavoriteGroup` 类型。
        """
        if not isinstance(other, THSFavoriteGroup):
            raise TypeError("比较对象 'other' 必须是 THSFavoriteGroup 类型。")

        # THSFavorite 设为 frozen=True 后，其实例可哈希，可以直接放入 set
        self_items_set: Set[THSFavorite] = set(self.items)
        other_items_set: Set[THSFavorite] = set(other.items)

        added_items: List[THSFavorite] = list(other_items_set - self_items_set)
        removed_items: List[THSFavorite] = list(self_items_set - other_items_set)

        return added_items, removed_items


T = TypeVar('T', bound='THSHttpApiClient') # 类型变量，用于 __enter__

class THSHttpApiClient:
    """
    一个通用的 HTTP API 客户端，封装了 httpx 请求的发送、
    Cookie 管理、基本头部设置和错误处理。
    """
    _DEFAULT_RETRY_COUNT: int = 3 # 示例：可配置的默认重试次数

    def __init__(self,
                 base_url: str,
                 cookies: Union[str, Dict[str, str], None] = None,
                 headers: Optional[Dict[str, str]] = None,
                 client: Optional[httpx.Client] = None,
                 timeout: float = 10.0, # 默认超时时间 (秒)
                 http2: bool = False): # 默认不启用 HTTP/2
        """
        初始化 API 客户端。

        Args:
            base_url (str): API 的基础 URL。所有请求的端点将与此拼接。
            cookies (Union[str, Dict[str, str], None], optional): 初始 cookies。
                如果为 None，将尝试从浏览器加载 (依赖 `load_cookies_from_browser`)。
            headers (Optional[Dict[str, str]], optional): 所有请求默认携带的头部。
                如果为 None，则使用模块级别的 `_DEFAULT_HEADERS`。
            client (Optional[httpx.Client], optional): 外部传入的 httpx.Client 实例。
                如果为 None，则内部会创建一个配置了 http2 和 timeout 的新 Client。
            timeout (float, optional): 请求的默认超时时间（秒）。
            http2 (bool, optional): 是否为内部创建的 Client 启用 HTTP/2。
        """
        self.base_url: str = base_url.rstrip('/')
        self._internal_cookies: Dict[str, str] = {} # 用于存储和管理本实例的cookies

        if client:
            self._client: httpx.Client = client
            self._is_external_client: bool = True
            # 如果使用外部客户端，假设其 cookies 和 headers 已由外部管理
            # 但如果传入了 cookies 参数，我们仍应尝试设置它们
            if cookies:
                self.set_cookies(cookies) # 这会更新 self._internal_cookies 并尝试更新 client.cookies
        else:
            self._client = httpx.Client(http2=http2, timeout=timeout)
            self._is_external_client = False
            # 对于内部客户端，明确设置其 cookies
            if cookies:
                self.set_cookies(cookies) # 更新 self._internal_cookies 和 self._client.cookies
            elif os.environ.get("AUTO_LOAD_BROWSER_COOKIES", "true").lower() == "true": # 通过环境变量控制是否自动加载
                # 仅在未提供 cookies 时尝试从浏览器加载，并提供配置开关
                print("未提供cookies，尝试从浏览器加载...") # 提示用户
                self.load_cookies_from_browser("firefox") # firefox 是示例，可能需要配置

        # 设置默认请求头
        self._default_headers: Dict[str, str] = headers.copy() if headers else _DEFAULT_HEADERS.copy()


    def _parse_cookies_str(self, cookies_str: str) -> Dict[str, str]:
        """
        辅助方法：将 "key1=value1; key2=value2" 格式的 cookie 字符串解析为字典。
        """
        cookie_dict: Dict[str, str] = {}
        if not cookies_str or not isinstance(cookies_str, str):
            return cookie_dict
        pairs: List[str] = cookies_str.split(';')
        for pair_str in pairs:
            pair_str = pair_str.strip()
            if '=' in pair_str:
                name, value = pair_str.split('=', 1)
                cookie_dict[name.strip()] = value.strip()
        return cookie_dict

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        """
        设置或更新客户端的 cookies。
        这将更新内部维护的 cookies 字典，并同步到 httpx.Client 实例。

        Args:
            cookies_input (Union[str, Dict[str, str]]):
                cookies 数据。可以是字典形式 `{"key": "value"}`，
                或者是单个字符串 "key1=value1; key2=value2"。

        Raises:
            TypeError: 如果 cookies_input 不是字符串或字典类型。
        """
        if isinstance(cookies_input, str):
            self._internal_cookies = self._parse_cookies_str(cookies_input)
        elif isinstance(cookies_input, dict):
            self._internal_cookies = cookies_input.copy() # 使用副本以避免外部修改
        else:
            raise TypeError("cookies_input 参数必须是字符串或字典类型。")

        # 同步到 httpx.Client 实例的 cookies
        if hasattr(self, '_client'): #确保 _client 已初始化
            self._client.cookies.clear()
            self._client.cookies.update(self._internal_cookies)

    def get_cookies(self) -> Dict[str, str]:
        """获取当前客户端内部管理的 cookies 的副本。"""
        return self._internal_cookies.copy()

    def load_cookies_from_browser(self, browser_name: str) -> None:
        """
        尝试从指定的浏览器中加载 cookies 并设置它们。
        依赖外部 `load_browser_cookie` 函数。

        Args:
            browser_name (str): 浏览器名称 (例如 "firefox", "chrome")。
                               其具体值取决于 `load_browser_cookie` 函数的支持。
        """
        try:
            # 假设 load_browser_cookie 返回类似 http.cookiejar.CookieJar 或兼容对象列表
            # 或者直接是字典
            raw_cookies = load_browser_cookie(browser_name) # 添加域名过滤
            cookies_dict = {cookie.name: cookie.value
                            for cookie in raw_cookies
                            if cookie.value is not None and cookie.name is not None}
            self.set_cookies(cookies_dict)
            print(f"已成功从 {browser_name} 加载并设置 cookies。")
        except Exception as e:
            print(f"从浏览器 {browser_name} 加载 cookies 时发生错误: {e}")

    def _prepare_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        准备最终用于请求的头部信息。
        合并默认头部和请求时额外指定的头部。
        """
        final_headers: Dict[str, str] = self._default_headers.copy()
        if additional_headers:
            final_headers.update(additional_headers)
        return final_headers

    def request(self,
                method: str,
                endpoint: str,
                params: Optional[Dict[str, Any]] = None,
                data: Optional[Dict[str, Any]] = None,
                json_payload: Optional[Any] = None,
                headers: Optional[Dict[str, str]] = None
               ) -> Dict[str, Any]:
        """
        发送 HTTP 请求并返回解析后的 JSON 数据。
        如果发生网络错误、HTTP 错误状态码或 JSON 解码错误，将抛出相应异常。

        Args:
            method (str): HTTP 方法 (例如 "GET", "POST")。
            endpoint (str): API 端点路径 (将与 base_url 拼接)。
            params (Optional[Dict[str, Any]]): URL 查询参数。
            data (Optional[Dict[str, Any]]): 表单数据 (用于 'application/x-www-form-urlencoded')。
            json_payload (Optional[Any]): JSON 数据 (用于 'application/json')。
            headers (Optional[Dict[str, str]]): 额外或覆盖的请求头部。

        Returns:
            Dict[str, Any]: 解析后的 JSON 响应。

        Raises:
            httpx.HTTPStatusError: 对于 4xx 或 5xx HTTP 状态码。
            httpx.RequestError: 对于网络问题 (例如连接错误, 超时)。
            json.JSONDecodeError: 如果响应内容不是有效的 JSON (或 httpx.JSONDecodeError)。
        """
        full_url: str = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers: Dict[str, str] = self._prepare_headers(headers)
        
        # httpx.Client 在初始化时已配置 cookies，所以这里通常不需要再传 cookies 参数
        # self._client.request 会自动使用其内部的 cookie jar
        response: httpx.Response = self._client.request(
            method,
            full_url,
            params=params,
            data=data,
            json=json_payload,
            headers=request_headers
        )
        
        response.raise_for_status() # 对 HTTP 4xx/5xx 错误抛出 httpx.HTTPStatusError

        # 如果响应成功但内容为空，response.json() 会抛出 json.JSONDecodeError
        # 如果业务上允许空JSON响应并希望将其视为空字典，可以在此处捕获处理
        # 例如:
        # try:
        #     return response.json()
        # except json.JSONDecodeError:
        #     if not response.text.strip():
        #         return {} # 空响应视为空字典
        #     raise # 非空但无效的JSON，重新抛出异常
        return response.json() # 直接尝试解析，失败则抛出异常

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        """发送 GET 请求。"""
        return self.request("GET", endpoint, params=params, **kwargs)

    def post_form_urlencoded(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        """发送 POST 请求，内容类型为 application/x-www-form-urlencoded。"""
        custom_headers: Dict[str, str] = kwargs.pop('headers', {})
        # 确保 Content-Type 被正确设置
        if 'Content-Type' not in custom_headers and 'content-type' not in custom_headers:
             custom_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8' # 明确编码
        return self.request("POST", endpoint, data=data, headers=custom_headers, **kwargs)

    def post_json(self, endpoint: str, json_payload: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        """发送 POST 请求，内容类型为 application/json。"""
        return self.request("POST", endpoint, json_payload=json_payload, **kwargs)

    def close(self) -> None:
        """关闭由该类实例内部创建的 httpx.Client。"""
        if not self._is_external_client and hasattr(self._client, "is_closed") and not self._client.is_closed:
            self._client.close()
            print("内部 THSHttpApiClient 已关闭。")

    def __enter__(self: T) -> T:
        """使得类实例可以用在 'with' 语句中。"""
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None: # Python 3.7+ 用 TracebackType
        """在 'with' 语句块结束时自动调用 close 方法。允许异常传播。"""
        self.close()
        # 返回 None (或不返回) 表示如果发生异常，则传播异常


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
        """
        初始化同花顺自选股服务。

        Args:
            cookies (Union[str, Dict[str, str], None], optional):
                用于请求的 cookies。如果提供了 `api_client`，此参数通常会被忽略，
                除非 `api_client` 未配置 cookies 且此参数被用于配置它。
            api_client (Optional[THSHttpApiClient], optional):
                外部传入的 `THSHttpApiClient` 实例。如果为 None，则内部会创建一个新的实例。
        """
        if api_client:
            self.api_client: THSHttpApiClient = api_client
            self._is_external_api_client: bool = True
        else:
            self.api_client = THSHttpApiClient(
                base_url=self._API_BASE_URL,
                cookies=cookies, # THSHttpApiClient 会处理 cookies 为 None 的情况
                headers=_DEFAULT_HEADERS # 使用模块级定义的默认头部
            )
            self._is_external_api_client = False

        self._current_version: Optional[Union[str, int]] = None
        self._groups_cache: Dict[str, THSFavoriteGroup] = {} # 键为分组名称
        self._load_cache()

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        """
        设置或更新 API 客户端的 cookies。
        实际调用 `self.api_client.set_cookies`。
        """
        self.api_client.set_cookies(cookies_input)

    def _update_version_from_response_data(self, response_data: Optional[Dict[str, Any]]) -> None:
        """从API响应数据中提取并更新当前的自选列表版本号。"""
        if response_data and isinstance(response_data, dict) and "version" in response_data:
            new_version: Union[str, int] = response_data["version"]
            # print(f"版本号从 {self._current_version} 更新为 {new_version}") # 调试用
            self._current_version = new_version

    def get_raw_group_data(self) -> Optional[Dict[str, Any]]:
        """
        从同花顺API获取原始的分组数据。

        Returns:
            Optional[Dict[str, Any]]: 如果请求成功且API业务状态码为0，则返回API响应中的 'data' 字段内容。
                                     否则，打印错误信息并返回 None。
        """
        params: Dict[str, str] = {
            "from": "sjcg_gphone",
            "types": "0,1"  # '0,1' 代表普通分组和概念板块等
        }
        api_response: Optional[Dict[str, Any]] = None
        try:
            api_response = self.api_client.get(self._QUERY_ENDPOINT, params=params)
        except httpx.HTTPStatusError as e:
            print(f"获取分组API HTTP错误: 状态码 {e.response.status_code}, 响应: {e.response.text[:200]}...")
            return None
        except httpx.RequestError as e:
            print(f"获取分组API请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"获取分组API响应JSON解析错误: {e}. 响应文本可能不是有效JSON。")
            return None
        except Exception as e: # 其他未知错误
            print(f"获取分组API时发生未知错误: {e}")
            return None


        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = api_response.get("data")
            self._update_version_from_response_data(data) # 更新版本号
            return data
        elif api_response and isinstance(api_response, dict): # API 返回了内容，但业务状态码非0
            status_msg: str = api_response.get("status_msg", "未知错误")
            status_code: int = api_response.get("status_code", -1)
            print(f"获取分组API业务逻辑错误: {status_msg} (代码: {status_code})")
        elif api_response is not None : # 返回了但不是预期的字典格式
            print(f"获取分组API返回了非预期的格式: {type(api_response)}")
        # 如果 api_response 为 None，说明在 try-except 中已处理并打印错误
        return None

    def _load_cache(self) -> None:
        """从本地 JSON 文件加载分组缓存。"""
        if not os.path.exists(self._CACHE_FILE):
            print(f"缓存文件 '{self._CACHE_FILE}' 不存在，跳过加载。")
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

                    if group_name and group_id: # 确保关键信息存在
                        group = THSFavoriteGroup(
                            name=group_name,
                            group_id=group_id,
                            items=items
                        )
                        temp_cache[group.name] = group
                    else:
                        print(f"警告: 缓存中发现不完整的分组数据: {group_data}")
                self._groups_cache = temp_cache
                print(f"已从 '{self._CACHE_FILE}' 加载 {len(self._groups_cache)} 个分组到缓存。")
        except json.JSONDecodeError:
            print(f"错误: 缓存文件 '{self._CACHE_FILE}' 内容不是有效的JSON格式。")
        except Exception as e:
            print(f"从文件加载缓存失败: {e}")

    def _save_cache(self) -> None:
        """将当前的分组缓存保存到本地 JSON 文件。"""
        if not self._groups_cache: # 如果缓存为空，可能不需要保存空文件或覆盖有用文件
            # print("缓存为空，跳过保存。") # 取决于业务需求
            # return
            pass # 允许保存空缓存（例如，用户删除了所有分组）

        try:
            cache_data_to_save: List[Dict[str, Any]] = []
            for group_name, group_obj in self._groups_cache.items():
                group_data: Dict[str, Any] = {
                    'name': group_obj.name,
                    'group_id': group_obj.group_id,
                    'items': [{'code': item.code, 'market': item.market} for item in group_obj.items]
                }
                cache_data_to_save.append(group_data)

            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data_to_save, f, ensure_ascii=False, indent=2)
            # print(f"已将 {len(cache_data_to_save)} 个分组保存到缓存文件 '{self._CACHE_FILE}'。")
        except Exception as e:
            print(f"保存缓存到文件失败: {e}")

    def parse_group_list(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        解析从API获取的原始数据中的 'group_list'。
        此方法是 `THSUserFavorite` 的内部辅助方法，用于将API原始数据转换为更结构化的中间形式。
        返回的列表中的每个字典代表一个分组的原始解析信息，待后续转换为 THSFavoriteGroup 对象。

        Args:
            raw_data (Optional[Dict[str, Any]]): `get_raw_group_data` 方法返回的原始 'data' 字段。

        Returns:
            List[Dict[str, Any]]: 解析后的分组原始信息列表。每个字典包含如 'id', 'name', 'item_details' 等键。
                                 如果输入数据无效或不含 'group_list'，则返回空列表。
        """
        parsed_groups_raw_info: List[Dict[str, Any]] = []
        if not raw_data or not isinstance(raw_data, dict) or "group_list" not in raw_data:
            return parsed_groups_raw_info

        api_group_list: List[Dict[str, Any]] = raw_data.get("group_list", [])

        for group_dict_from_api in api_group_list:
            if not isinstance(group_dict_from_api, dict):
                print(f"警告: API返回的group_list中包含非字典元素: {group_dict_from_api}")
                continue

            # 准备一个字典来存放这个分组的解析后信息
            current_group_parsed_info: Dict[str, Any] = {
                "id": group_dict_from_api.get("id"),
                "name": group_dict_from_api.get("name"),
                "api_type_code": group_dict_from_api.get("type"), # API返回的类型 (0或1等)
                "num_items_api": group_dict_from_api.get("num"),  # API报告的项目数量
                "attrs": group_dict_from_api.get("attrs", {}),    # 附加属性
                "item_details": []                                # 存储解析后的项目详情
            }

            content_str: Optional[str] = group_dict_from_api.get("content")
            if isinstance(content_str, str) and content_str:
                # content 格式示例: "002344|002563|...|600726|,33|33|...|33|"
                # 第一部分是项目代码，第二部分是对应的类型代码
                parts: List[str] = content_str.split(',', 1)
                item_codes_segment: str = parts[0]
                # API返回的类型代码段，例如 "33|17|..."
                api_item_type_codes_segment: str = parts[1] if len(parts) > 1 else ""

                item_codes_list: List[str] = [code for code in item_codes_segment.split('|') if code]
                api_item_type_codes_list: List[str] = [tc for tc in api_item_type_codes_segment.split('|') if tc]

                for i, item_code_str in enumerate(item_codes_list):
                    # API返回的该项目的类型代码 (例如 "33", "17")
                    api_item_type_code: Optional[str] = api_item_type_codes_list[i] if i < len(api_item_type_codes_list) else None
                    current_group_parsed_info["item_details"].append({
                        "code": item_code_str,
                        "api_type": api_item_type_code # 这是从API直接获取的类型代码
                    })

            parsed_groups_raw_info.append(current_group_parsed_info)
        return parsed_groups_raw_info

    def get_all_groups(self, use_cache: bool = False) -> Dict[str, THSFavoriteGroup]:
        """
        获取所有自选股分组信息。

        首先尝试从API获取最新数据。如果获取失败且 `use_cache` 为 True，
        则返回当前内存中的缓存数据。获取成功后会更新内存缓存并保存到文件。

        Args:
            use_cache (bool): 如果API请求失败，是否尝试使用内存中的旧缓存数据。默认为 False。

        Returns:
            Dict[str, THSFavoriteGroup]: 一个字典，键是分组名称，值是 `THSFavoriteGroup` 对象。
                                         如果API和缓存都无法获取数据，则返回空字典。
        """
        formatted_groups: Dict[str, THSFavoriteGroup] = {}
        raw_data_from_api = self.get_raw_group_data()

        if raw_data_from_api:
            # API调用成功，解析数据
            parsed_group_list_raw_info = self.parse_group_list(raw_data_from_api)

            for group_raw_info in parsed_group_list_raw_info:
                group_name: Optional[str] = group_raw_info.get("name")
                group_id: Optional[str] = group_raw_info.get("id")

                if group_name and group_id: # 确保名称和ID存在
                    favorite_items_list: List[THSFavorite] = []
                    item_details_from_parse: List[Dict[str, Optional[str]]] = group_raw_info.get("item_details", [])

                    for detail in item_details_from_parse:
                        item_code_str: Optional[str] = detail.get("code")
                        # 'api_type' 是从API获取的数字类型代码，例如 "33"
                        api_item_type_code: Optional[str] = detail.get("api_type")

                        # 使用 market_abbr 将API类型代码转换为市场缩写 (如 "SZ")
                        # 假设 market_abbr 能处理 Optional[str] 并返回 Optional[str]
                        market_short_name: Optional[str] = market_abbr(api_item_type_code) if api_item_type_code else None

                        if item_code_str:
                            favorite_items_list.append(THSFavorite(code=item_code_str, market=market_short_name))

                    ths_favorite_group = THSFavoriteGroup(name=group_name, group_id=group_id, items=favorite_items_list)
                    formatted_groups[group_name] = ths_favorite_group
                else:
                    print(f"警告: 解析时发现无名称或ID的分组原始数据: {group_raw_info}")
            
            # 更新内存缓存并保存到文件
            self._groups_cache = formatted_groups
            self._save_cache()
            return formatted_groups
        else:
            # API调用失败
            print("从API获取分组数据失败。")
            if use_cache:
                print("尝试使用内存中的缓存数据。")
                return self._groups_cache.copy() # 返回缓存副本
            return {} # 不使用缓存或缓存也为空

    def _get_group_id_by_identifier(self, group_identifier: str) -> Optional[str]:
        """
        通过分组标识符 (名称或ID) 获取分组的ID。
        会优先检查内存缓存，如果缓存为空，则尝试从API获取最新数据来填充缓存。

        Args:
            group_identifier (str): 分组的名称或ID。

        Returns:
            Optional[str]: 如果找到分组，则返回其ID；否则返回 None。
        """
        if not self._groups_cache: # 如果内存缓存为空
            print("内存缓存为空，尝试从API获取最新分组数据以查找分组ID...")
            self.get_all_groups(use_cache=False) # 获取最新数据并填充缓存，不使用旧缓存

        # 检查缓存中是否有此标识符（作为名称或ID）
        # 优先匹配ID
        for group_obj in self._groups_cache.values():
            if group_obj.group_id == group_identifier:
                return group_obj.group_id
        # 然后匹配名称
        if group_identifier in self._groups_cache:
            return self._groups_cache[group_identifier].group_id

        print(f"未能通过标识符 '{group_identifier}' 找到对应的分组ID。")
        return None

    def _parse_code_with_market_suffix(self, code_with_market_suffix: str) -> Tuple[str, str]:
        """
        解析带市场后缀的股票代码 (例如 "000001.SZ")。

        Args:
            code_with_market_suffix (str): 带市场后缀的股票代码。

        Returns:
            Tuple[str, str]: 一个元组，包含 (纯代码, API市场类型代码)。
                             例如 ("000001", "33")。

        Raises:
            ValueError: 如果代码格式无效或市场类型未知。
        """
        if '.' not in code_with_market_suffix:
            raise ValueError(f"股票代码格式无效: '{code_with_market_suffix}'。预期格式: CODE.MARKET_SUFFIX (例如 '000001.SZ')")

        code_part, market_suffix_part = code_with_market_suffix.rsplit('.', 1) # 使用 rsplit 更稳妥
        
        # 使用 market_code 将市场后缀 (如 "SZ") 转换为API所需的类型代码 (如 "33")
        # 假设 market_code(market_suffix: str) -> Optional[str]
        api_market_type_code: Optional[str] = market_code(market_suffix_part.upper())

        if not api_market_type_code:
            raise ValueError(f"未知的市场后缀: '{market_suffix_part}' (来自 '{code_with_market_suffix}')")

        return code_part, api_market_type_code

    def _modify_group_item_api_call(self,
                                    endpoint: str,
                                    group_id: str,
                                    item_code: str, # 纯代码，例如 "000001"
                                    api_item_type_code: str, # API 市场类型代码, 例如 "33"
                                    action_name: str = "操作"
                                   ) -> Optional[Dict[str, Any]]:
        """
        调用API以修改分组中的项目 (添加或删除)。

        Args:
            endpoint (str): API的端点路径 (添加或删除)。
            group_id (str): 目标分组的ID。
            item_code (str): 要操作的项目的纯代码。
            api_item_type_code (str): 项目的API市场类型代码。
            action_name (str): 操作的名称 (例如 "添加", "删除")，用于日志输出。

        Returns:
            Optional[Dict[str, Any]]: 如果API调用成功且业务状态码为0，则返回API响应中的 'data' 部分。
                                     否则返回 None。
        """
        if self._current_version is None:
            print(f"{action_name}项目失败：未能确定有效的自选列表版本号。请先成功调用 get_all_groups()。")
            # 可以选择尝试获取一次版本号
            # print("尝试获取最新版本号...")
            # self.get_all_groups(use_cache=False)
            # if self._current_version is None:
            #     print("仍然无法获取版本号，操作终止。")
            #     return None
            return None


        payload: Dict[str, str] = {
            "version": str(self._current_version),
            "from": "sjcg_gphone",
            "id": group_id,
            "content": f"{item_code},{api_item_type_code}", # API 需要 纯代码,API类型代码
            "num": "1" # 每次操作一个项目
        }
        
        api_response: Optional[Dict[str, Any]] = None
        try:
            api_response = self.api_client.post_form_urlencoded(endpoint, data=payload)
        except httpx.HTTPStatusError as e:
            print(f"{action_name}项目API HTTP错误: 状态码 {e.response.status_code}, 响应: {e.response.text[:200]}...")
            return None
        except httpx.RequestError as e:
            print(f"{action_name}项目API请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"{action_name}项目API响应JSON解析错误: {e}")
            return None
        except Exception as e:
            print(f"{action_name}项目API时发生未知错误: {e}")
            return None

        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data: Optional[Dict[str, Any]] = api_response.get("data")
            self._update_version_from_response_data(data) # 更新版本号
            print(f"项目 '{item_code}' ({action_name}到分组 '{group_id}') 成功。新版本: {self._current_version}")
            return data
        elif api_response and isinstance(api_response, dict):
            status_msg: str = api_response.get("status_msg", "未知错误")
            status_code: int = api_response.get("status_code", -1)
            print(f"{action_name}项目API业务逻辑错误: {status_msg} (代码: {status_code})")
        elif api_response is not None:
            print(f"{action_name}项目API返回了非预期的格式: {type(api_response)}")
        return None

    def add_item_to_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        """
        向指定分组添加一个自选项目。

        Args:
            group_identifier (str): 目标分组的名称或ID。
            code_with_market_suffix (str): 要添加的项目的代码，带市场后缀 (例如 "000001.SZ")。

        Returns:
            Optional[Dict[str, Any]]: 如果操作成功，返回API响应的 'data' 部分；否则返回 None。
                                     成功后会自动刷新缓存。
        """
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            print(f"添加项目失败: 未能找到分组 '{group_identifier}'。")
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as e:
            print(f"添加项目失败: 解析代码 '{code_with_market_suffix}' 时出错 - {e}")
            return None

        api_result = self._modify_group_item_api_call(
            self._ADD_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="添加"
        )

        if api_result:
            # 操作成功，刷新缓存以反映更改
            print(f"项目 '{code_with_market_suffix}' 添加成功，正在刷新分组缓存...")
            self.get_all_groups(use_cache=False) # 强制从API获取最新数据
        return api_result

    def delete_item_from_group(self, group_identifier: str, code_with_market_suffix: str) -> Optional[Dict[str, Any]]:
        """
        从指定分组删除一个自选项目。

        Args:
            group_identifier (str): 目标分组的名称或ID。
            code_with_market_suffix (str): 要删除的项目的代码，带市场后缀 (例如 "000001.SZ")。

        Returns:
            Optional[Dict[str, Any]]: 如果操作成功，返回API响应的 'data' 部分；否则返回 None。
                                     成功后会自动刷新缓存。
        """
        target_group_id: Optional[str] = self._get_group_id_by_identifier(group_identifier)
        if not target_group_id:
            print(f"删除项目失败: 未能找到分组 '{group_identifier}'。")
            return None

        try:
            item_pure_code, api_item_type = self._parse_code_with_market_suffix(code_with_market_suffix)
        except ValueError as e:
            print(f"删除项目失败: 解析代码 '{code_with_market_suffix}' 时出错 - {e}")
            return None

        api_result = self._modify_group_item_api_call(
            self._DELETE_ITEM_ENDPOINT,
            target_group_id,
            item_pure_code,
            api_item_type,
            action_name="删除"
        )

        if api_result:
            # 操作成功，刷新缓存
            print(f"项目 '{code_with_market_suffix}' 删除成功，正在刷新分组缓存...")
            self.get_all_groups(use_cache=False)
        return api_result

    def close(self) -> None:
        """
        关闭由该类实例内部创建的 `THSHttpApiClient` (如果存在)。
        并确保在退出前保存缓存。
        """
        print("正在关闭 THSUserFavorite 服务...")
        self._save_cache() # 确保退出前保存最新的缓存状态
        if not self._is_external_api_client: # 只关闭内部创建的 HTTP client
            self.api_client.close()
        print("THSUserFavorite 服务已关闭。")


    def __enter__(self: 'THSUserFavorite') -> 'THSUserFavorite': # TypeVar for self type
        """使得类实例可以用在 'with' 语句中。"""
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        """在 'with' 语句块结束时自动调用 close 方法。允许异常传播。"""
        self.close()


if __name__ == "__main__":
   
    with THSUserFavorite() as ths_service:
        print("\n--- 步骤1: 获取所有分组 (可能会从API获取或使用缓存) ---")
        all_current_groups = ths_service.get_all_groups(use_cache=True) # 首次尝试API,失败则用缓存

        if not all_current_groups:
            print("未能获取到任何分组信息。测试可能无法继续。")
        else:
            print(f"成功获取到 {len(all_current_groups)} 个分组:")
            for name, group_obj in all_current_groups.items():
                print(f"  分组名: {group_obj.name} (ID: {group_obj.group_id}), 项目数: {len(group_obj.items)}")
                if group_obj.items:
                    print(f"    示例项目: {group_obj.items[0]}")

            # 选择一个分组进行测试 (请根据实际存在的分组名修改)
            # test_group_name_or_id = "我的分组1" # 或者使用分组ID "0_xx"
            # 如果分组列表不为空，尝试选择第一个分组
            test_group_name_or_id = ""
            if all_current_groups:
                first_group_name = list(all_current_groups.keys())[0]
                test_group_name_or_id = first_group_name
                print(f"\n将使用分组 '{test_group_name_or_id}' 进行添加/删除测试。")

                # --- 步骤2: 向分组添加股票 (假设 000001.SZ 是平安银行) ---
                stock_to_add = "000001.SZ"
                print(f"\n--- 步骤2: 尝试向分组 '{test_group_name_or_id}' 添加股票 '{stock_to_add}' ---")
                add_result = ths_service.add_item_to_group(test_group_name_or_id, stock_to_add)
                if add_result:
                    print(f"添加API调用成功，响应数据: {add_result}")
                    updated_groups_after_add = ths_service._groups_cache # 直接访问内部缓存查看是否更新
                    if stock_to_add.split('.')[0] in [item.code for item in updated_groups_after_add.get(test_group_name_or_id, THSFavoriteGroup("","",[])).items]:
                         print(f"验证成功：'{stock_to_add}' 已存在于分组 '{test_group_name_or_id}' 的缓存中。")
                    else:
                         print(f"验证警告：'{stock_to_add}' 未在分组 '{test_group_name_or_id}' 的缓存中找到 (可能由于API未实际添加或缓存逻辑)。")

                else:
                    print(f"添加股票 '{stock_to_add}' 失败。")

                # --- 步骤3: 从分组删除股票 ---
                stock_to_delete = "000001.SZ" # 假设我们刚添加了这个
                print(f"\n--- 步骤3: 尝试从分组 '{test_group_name_or_id}' 删除股票 '{stock_to_delete}' ---")
                delete_result = ths_service.delete_item_from_group(test_group_name_or_id, stock_to_delete)
                if delete_result:
                    print(f"删除API调用成功，响应数据: {delete_result}")
                else:
                    print(f"删除股票 '{stock_to_delete}' 失败。")

                print("\n--- 步骤4: 再次获取所有分组查看最终状态 ---")
                final_groups = ths_service.get_all_groups(use_cache=False) # 强制刷新
                for name, group_obj in final_groups.items():
                    print(f"  最终分组: {group_obj.name}, 项目数: {len(group_obj.items)}")
            else:
                print("没有可用的分组进行添加/删除测试。")


    print("\n测试结束。")
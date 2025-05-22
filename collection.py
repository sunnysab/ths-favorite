from dataclasses import dataclass
import httpx
import json
import os
from constant import *
from cookie import *
from typing import List, Optional, Dict, Any, Union, Tuple


_DEFAULT_HEADERS = {
    "User-Agent": "Hexin_Gphone/11.28.03 (Royal Flush) hxtheme/0 innerversion/G037.09.028.1.32 followPhoneSystemTheme/0 userid/500780707 getHXAPPAccessibilityMode/0 hxNewFont/1 isVip/0 getHXAPPFontSetting/normal getHXAPPAdaptOldSetting/0 okhttp/3.14.9",
}


@dataclass
class THSFavorite:
    """
    同花顺自选股的单个项目类，包含代码、名称和类型。
    """
    code: str
    market: Optional[str] = None

    def __repr__(self):
        return f"Favorite({self.code}.{self.market})"


class THSFavoriteGroup:
    """
    同花顺自选股的分组类，包含分组名称、ID 和项目列表。
    """
    group_id: str
    name: str
    items: List[THSFavorite]

    def __init__(self, name: str, group_id: str, items: List[THSFavorite]):
        self.name = name
        self.group_id = group_id
        self.items = items

    def __repr__(self):
        return f"THSFavoriteGroup(name={self.name}, group_id={self.group_id}, items={self.items})"
    
    def diff(self, other: 'THSFavoriteGroup') -> Tuple[List[THSFavorite], List[THSFavorite]]:
        """
        比较两个分组，返回新增和删除的项目列表。
        """
        if not isinstance(other, THSFavoriteGroup):
            raise TypeError("other 必须是 THSFavoriteGroup 类型。")
        
        self_set = set(self.items)
        other_set = set(other.items)

        added_items = list(other_set - self_set)
        removed_items = list(self_set - other_set)

        return added_items, removed_items


class THSHttpApiClient:
    """
    一个通用的 HTTP API 客户端，封装了 httpx 请求的发送、
    Cookie 管理、基本头部设置和错误处理。
    """
    def __init__(self,
                 base_url: str,
                 cookies: Union[str, Dict[str, str], None] = None,
                 headers: Optional[Dict[str, str]] = None,
                 client: Optional[httpx.Client] = None):
        """
        初始化 API 客户端。

        Args:
            base_url (str): API 的基础 URL。所有请求的端点将与此拼接。
            cookies (Union[str, Dict[str, str], None], optional): 初始 cookies。
            headers (Optional[Dict[str, str]], optional): 所有请求默认携带的头部。
            client (Optional[httpx.Client], optional): 外部传入的 httpx.Client 实例。
                                                       如果为 None，则内部会创建一个新 Client。
        """
        self.base_url = base_url.rstrip('/')
        self._cookies: Dict[str, str] = {}
        if cookies:
            self.set_cookies(cookies)
        else:
            self.load_cookies_from_browser("firefox")

        self._default_headers = headers if headers else _DEFAULT_HEADERS

        if client:
            self._client = client
            self._is_external_client = True
        else:
            self._client = httpx.Client()
            self._is_external_client = False

        self._client.cookies.update(self._cookies)

    def _parse_cookies_str(self, cookies_str: str) -> Dict[str, str]:
        cookie_dict = {}
        if not cookies_str or not isinstance(cookies_str, str):
            return cookie_dict
        pairs = cookies_str.split(';')
        for pair in pairs:
            pair = pair.strip()
            if '=' in pair:
                name, value = pair.split('=', 1)
                cookie_dict[name.strip()] = value.strip()
        return cookie_dict

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]):
        if isinstance(cookies_input, str):
            self._cookies = self._parse_cookies_str(cookies_input)
        elif isinstance(cookies_input, dict):
            self._cookies = cookies_input.copy()
        else:
            raise TypeError("cookies_input 必须是字符串或字典类型。")

    def get_cookies(self) -> Dict[str, str]:
        return self._cookies.copy()
    
    def load_cookies_from_browser(self, browser: str):
        """
        从指定的浏览器中加载 cookies。
        """
        cookies = load_browser_cookie(browser)
        if cookies:
            cookies_dict = {cookie.name: cookie.value for cookie in cookies if cookie.value is not None}
            self.set_cookies(cookies_dict)

    def _prepare_request_args(self,
                              headers: Optional[Dict[str, str]] = None
                             ) -> Dict[str, str]:
        """准备最终的请求头部和 cookies。"""
        final_headers = self._default_headers.copy()
        if headers:
            final_headers.update(headers)

        return final_headers

    def request(self,
                method: str,
                endpoint: str,
                params: Optional[Dict[str, Any]] = None,
                data: Optional[Dict[str, Any]] = None, # For x-www-form-urlencoded
                json_payload: Optional[Any] = None,    # For application/json
                headers: Optional[Dict[str, str]] = None
               ) -> Dict[str, Any]: # Changed return type
        """
        Send HTTP request and return parsed JSON data.
        Raises exceptions on HTTP errors, network errors, or JSON decoding errors.

        Args:
            method (str): HTTP method (GET, POST, etc.).
            endpoint (str): API endpoint path (will be joined with base_url).
            params (Optional[Dict[str, Any]]): URL query parameters.
            data (Optional[Dict[str, Any]]): Form data (for 'application/x-www-form-urlencoded').
            json_payload (Optional[Any]): JSON data (for 'application/json').
            headers (Optional[Dict[str, str]]): Headers to override or add.

        Returns:
            Dict[str, Any]: Parsed JSON response. Returns an empty dict if the response body is empty but successful.

        Raises:
            httpx.HTTPStatusError: For 4xx or 5xx HTTP status codes.
            httpx.RequestError: For network issues (connection, timeout, etc.).
            ApiResponseJsonDecodeError: If the response content is not valid JSON.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        final_headers = self._prepare_request_args(headers)
        response: httpx.Response

        response = self._client.request(
                method,
                url,
                params=params,
                data=data,
                json=json_payload,
                headers=final_headers
            )
        response.raise_for_status() # Raises httpx.HTTPStatusError for 4xx/5xx
        return response.json()

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]: # Changed return type
        return self.request("GET", endpoint, params=params, **kwargs)

    def post_form_urlencoded(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]: # Changed return type
        # Ensure Content-Type is correctly set, or rely on httpx to handle it
        custom_headers = kwargs.pop('headers', {})
        if 'Content-Type' not in custom_headers and 'content-type' not in custom_headers :
             custom_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        return self.request("POST", endpoint, data=data, headers=custom_headers, **kwargs)

    def post_json(self, endpoint: str, json_payload: Optional[Any] = None, **kwargs) -> Dict[str, Any]: # Changed return type
        return self.request("POST", endpoint, json_payload=json_payload, **kwargs)

    def close(self):
        if not self._is_external_client and hasattr(self._client, "is_closed") and not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return None  # 允许异常传播



class THSUserGroups:
    _API_BASE_URL = "https://ugc.10jqka.com.cn"
    _QUERY_ENDPOINT = "/optdata/selfgroup/open/api/group/v1/query"
    _ADD_ITEM_ENDPOINT = "/optdata/selfgroup/open/api/content/v1/add"
    _DELETE_ITEM_ENDPOINT = "/optdata/selfgroup/open/api/content/v1/delete"
    _CACHE_FILE = "favorite.json"

    def __init__(self,
                 cookies: Union[str, Dict[str, str], None] = None,
                 api_client: Optional[THSHttpApiClient] = None):
        """
        初始化同花顺自选股分组服务类。

        Args:
            cookies (Union[str, Dict[str, str], None], optional):
                用于请求的 cookies。如果提供了 api_client，此参数将被忽略。
            api_client (Optional[THSHttpApiClient], optional):
                外部传入的 THSHttpApiClient 实例。如果为 None，则内部会创建一个新的实例。
        """
        if api_client:
            self.api_client = api_client
            self._is_external_api_client = True
        else:
            # 通用头部，Host 会由 httpx 根据 URL 自动设置，User-Agent 很重要
            
            self.api_client = THSHttpApiClient(
                base_url=self._API_BASE_URL,
                cookies=cookies,
                headers=_DEFAULT_HEADERS
            )
            self._is_external_api_client = False
        
        self._current_version: Optional[Union[str, int]] = None
        self._groups_cache: Dict[str, THSFavoriteGroup] = {}
        self._load_cache()

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]):
        """设置或更新 API 客户端的 cookies。"""
        self.api_client.set_cookies(cookies_input)

    def _update_version_from_response_data(self, response_data: Optional[Dict[str, Any]]) -> None:
        if response_data and "version" in response_data:
            new_version = response_data["version"]
            self._current_version = new_version

    def get_raw_group_data(self) -> Optional[Dict[str, Any]]:
        params = {
            "from": "sjcg_gphone",
            "types": "0,1"
        }
        # 不需要传递 headers 或 cookies 给 get 方法，因为它们已在 THSHttpApiClient 中配置
        try:
            api_response = self.api_client.get(self._QUERY_ENDPOINT, params=params)
        except RuntimeError as e:
            print(f"获取分组API请求错误: {e}")
            return None

        # The THS API returns a business-level status code within the JSON response.
        # A 200 HTTP status from self.api_client.get() doesn't guarantee business success.
        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data = api_response.get("data")
            self._update_version_from_response_data(data)
            return data
        elif api_response and isinstance(api_response, dict): # API 返回了内容，但业务状态码非0
            print(f"获取分组API业务错误: {api_response.get('status_msg')} (代码: {api_response.get('status_code')})")
        elif not isinstance(api_response, dict):
            print(f"获取分组API返回了非预期的格式: {type(api_response)}")
        return None

    def _load_cache(self) -> None:
        """从文件加载缓存"""
        try:
            if os.path.exists(self._CACHE_FILE):
                with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    for group_data in cache_data:
                        items = [THSFavorite(**item) for item in group_data['items']]
                        group = THSFavoriteGroup(
                            name=group_data['name'],
                            group_id=group_data['group_id'],
                            items=items
                        )
                        self._groups_cache[group.name] = group
        except Exception as e:
            print(f"加载缓存失败: {e}")

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            cache_data = []
            for group in self._groups_cache.values():
                group_data = {
                    'name': group.name,
                    'group_id': group.group_id,
                    'items': [{'code': item.code, 'market': item.market} for item in group.items]
                }
                cache_data.append(group_data)
            
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def get_all_groups(self) -> Dict[str, THSFavoriteGroup]:
        """
        获取所有分组信息，并将其格式化为字典。
        键是分组名称，值是 THSFavoriteGroup 对象。
        同时更新缓存。
        """
        formatted_groups: Dict[str, THSFavoriteGroup] = {}
        raw_data = self.get_raw_group_data()
        
        if raw_data:
            # parse_group_list returns List[Dict[str, Any]]
            # Each dict contains 'id', 'name' and 'item_details'
            # 'item_details' is a list of {'code': str, 'type': Optional[str]}
            parsed_group_list = self.parse_group_list(raw_data)
            
            for group_data in parsed_group_list:
                group_name = group_data.get("name")
                group_id = group_data.get("id") # Get group_id
                
                if group_name and isinstance(group_name, str) and group_id is not None:
                    favorite_items: List[THSFavorite] = []
                    item_details = group_data.get("item_details", [])
                    
                    for detail in item_details:
                        item_code = detail.get("code")  # Expected to be str
                        item_market = detail.get("type")  # Corresponds to THSFavorite.market
                        
                        item_market = market_abbr(item_market)
                        if item_code is not None: 
                            favorite_items.append(THSFavorite(code=str(item_code), market=item_market))
                            
                    # Create THSFavoriteGroup instance
                    ths_favorite_group = THSFavoriteGroup(name=group_name, group_id=str(group_id), items=favorite_items)
                    formatted_groups[group_name] = ths_favorite_group

        # 更新缓存
        self._groups_cache = formatted_groups
        self._save_cache()
        return formatted_groups

    def _get_group_id(self, group_identifier: str) -> Optional[str]:
        """
        通过分组标识(名称或ID)获取分组ID
        """
        # 如果缓存为空，先获取所有分组
        if not self._groups_cache:
            self.get_all_groups()
            
        # 先检查是否直接是组ID
        for group in self._groups_cache.values():
            if group.group_id == group_identifier:
                return group.group_id
                
        # 再检查是否是组名称
        if group_identifier in self._groups_cache:
            return self._groups_cache[group_identifier].group_id
                
        return None

    def _parse_stock_code(self, code_with_market: str) -> Tuple[str, str]:
        """
        解析带市场后缀的股票代码，返回(代码, 市场类型代码)
        
        Args:
            code_with_market: 股票代码(带市场后缀，如: 000001.SZ)
            
        Returns:
            Tuple[str, str]: (代码, 市场类型代码)
            
        Raises:
            ValueError: 如果代码格式无效
        """
        if '.' not in code_with_market:
            raise ValueError(f"股票代码格式无效: {code_with_market}。预期格式: CODE.MARKET")
        
        code, market = code_with_market.split('.')
        market_type_code = market_code(market.upper())
        if not market_type_code:
            raise ValueError(f"未知的市场类型: {market}")
        
        return code, market_type_code

    def add_item_to_group(self, group_identifier: str, code_with_market: str) -> Optional[Dict[str, Any]]:
        """
        向分组添加股票
        
        Args:
            group_identifier: 分组名称或分组ID
            code_with_market: 股票代码(带市场后缀，如: 000001.SZ)
            
        Returns:
            Optional[Dict[str, Any]]: API返回的数据，失败时返回None
        """
        try:
            # 获取组ID
            group_id = self._get_group_id(group_identifier)
            if not group_id:
                print(f"未找到分组: {group_identifier}")
                return None
                
            # 解析股票代码
            item_code, item_type_code = self._parse_stock_code(code_with_market)
            
            # 执行添加操作
            result = self._modify_group_item(
                self._ADD_ITEM_ENDPOINT,
                group_id,
                item_code,
                item_type_code,
                self._current_version,
                "添加"
            )
            
            # 成功后更新缓存
            if result:
                self.get_all_groups()  # 重新获取分组数据并更新缓存
            
            return result
        except ValueError as e:
            print(f"添加项目失败: {e}")
            return None

    def delete_item_from_group(self, group_identifier: str, code_with_market: str) -> Optional[Dict[str, Any]]:
        """
        从分组删除股票
        
        Args:
            group_identifier: 分组名称或分组ID
            code_with_market: 股票代码(带市场后缀，如: 000001.SZ)
            
        Returns:
            Optional[Dict[str, Any]]: API返回的数据，失败时返回None
        """
        try:
            # 获取组ID
            group_id = self._get_group_id(group_identifier)
            if not group_id:
                print(f"未找到分组: {group_identifier}")
                return None
                
            # 解析股票代码
            item_code, item_type_code = self._parse_stock_code(code_with_market)
            
            # 执行删除操作
            result = self._modify_group_item(
                self._DELETE_ITEM_ENDPOINT,
                group_id,
                item_code,
                item_type_code,
                self._current_version,
                "删除"
            )
            
            # 成功后更新缓存
            if result:
                self.get_all_groups()  # 重新获取分组数据并更新缓存
            
            return result
        except ValueError as e:
            print(f"删除项目失败: {e}")
            return None

    def _modify_group_item(self,
                          endpoint: str,
                          group_id: str,
                          item_code: str,
                          item_type_code: Union[str, int],
                          current_version: Optional[Union[str, int]] = None,
                          action_name: str = "操作"
                         ) -> Optional[Dict[str, Any]]:
        """原有的修改分组项目的方法，保持不变"""
        version_to_use = str(current_version) if current_version is not None else \
                        (str(self._current_version) if self._current_version is not None else None)

        if version_to_use is None:
            print(f"{action_name}项目失败：未能确定有效的版本号。请先调用 get_all_groups() 或提供 current_version。")
            return None

        payload = {
            "version": version_to_use,
            "from": "sjcg_gphone",
            "id": group_id,
            "content": f"{item_code},{item_type_code}",
            "num": "1"
        }
        
        try:
            api_response = self.api_client.post_form_urlencoded(endpoint, data=payload)
        except RuntimeError as e:
            print(f"{action_name}项目API请求错误: {e}")
            return None

        if api_response and isinstance(api_response, dict) and api_response.get("status_code") == 0:
            data = api_response.get("data")
            self._update_version_from_response_data(data)
            print(f"项目 {item_code} {action_name}到分组 {group_id} 成功。新版本: {self._current_version}")
            return data
        elif api_response and isinstance(api_response, dict):
            print(f"{action_name}项目API业务错误: {api_response.get('status_msg')} (代码: {api_response.get('status_code')})")
        elif not isinstance(api_response, dict):
            print(f"{action_name}项目API返回了非预期的格式: {type(api_response)}")
        return None

    def close(self):
        """关闭由该类实例内部创建的 THSHttpApiClient (如果存在)。"""
        if not self._is_external_api_client: # 只关闭内部创建的 client
            self.api_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_cache()  # 退出时保存缓存
        self.close()
        return None  # 允许异常传播

    def parse_group_list(self, raw_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed_groups: List[Dict[str, Any]] = []
        if not raw_data or not isinstance(raw_data, dict) or "group_list" not in raw_data:
            return parsed_groups

        for group_dict in raw_data.get("group_list", []):
            if not isinstance(group_dict, dict):
                continue

            group_info: Dict[str, Any] = {
                "id": group_dict.get("id"),
                "name": group_dict.get("name"),
                "type": group_dict.get("type"),
                "num_items": group_dict.get("num"),
                "items": [],
                "item_details": []
            }

            attrs = group_dict.get("attrs", {})
            if isinstance(attrs, dict):
                if "question" in attrs:
                    group_info["question"] = attrs["question"]
                if "color" in attrs:
                    group_info["color"] = attrs["color"]
            
            content_str = group_dict.get("content", "")
            if isinstance(content_str, str) and content_str:
                parts = content_str.split(',', 1)
                item_codes_str = parts[0]
                item_types_str = parts[1] if len(parts) > 1 else ""

                item_codes_list = [code for code in item_codes_str.split('|') if code]
                item_types_list = [type_code for type_code in item_types_str.split('|') if type_code]
                
                group_info["items"] = item_codes_list

                for i, code in enumerate(item_codes_list):
                    item_type = item_types_list[i] if i < len(item_types_list) else None
                    group_info["item_details"].append({"code": code, "type": item_type})
            
            parsed_groups.append(group_info)
        return parsed_groups
    

if __name__ == "__main__":
    # 测试代码
    with THSUserGroups() as ths_user_groups:
        # 先获取所有分组，以初始化版本号和缓存
        all_groups = ths_user_groups.get_all_groups()
        print(all_groups)
        
        # 添加股票到分组 - 可以使用分组名或分组ID
        ths_user_groups.add_item_to_group("航空", "000001.SZ")
        
        # 从分组删除股票
        # ths_user_groups.delete_item_from_group("航空", "000001.SZ")
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type, TypeVar, Union

from loguru import logger
from requests import Response, Session
from requests.exceptions import HTTPError, RequestException

from config import DEFAULT_HEADERS, DEFAULT_HTTP_TIMEOUT
from cookie import parse_cookie_string

T_HttpApiClient = TypeVar("T_HttpApiClient", bound="THSHttpApiClient")


class THSHttpApiClient:
    """负责底层 HTTP 请求、Cookie 管理与通用错误处理的客户端。"""

    def __init__(
        self,
        base_url: str,
        cookies: Union[str, Dict[str, str], None] = None,
        headers: Optional[Dict[str, str]] = None,
        client: Optional[Session] = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        self.base_url: str = base_url.rstrip("/")
        logger.debug("THSHttpApiClient 初始化: base_url='%s', timeout=%ss", self.base_url, timeout)

        self._timeout: float = timeout

        if client:
            self._client = client
            self._is_external_client = True
            logger.info("使用外部传入的 requests.Session 实例。")
        else:
            self._client = Session()
            self._is_external_client = False
            logger.info("创建内部 requests.Session 实例。")

        if cookies:
            self.set_cookies(cookies)

        self._default_headers: Dict[str, str] = headers.copy() if headers else DEFAULT_HEADERS.copy()
        logger.debug("默认请求头已设置: %s", self._default_headers)

    def set_cookies(self, cookies_input: Union[str, Dict[str, str]]) -> None:
        if isinstance(cookies_input, str):
            parsed = parse_cookie_string(cookies_input)
        elif isinstance(cookies_input, dict):
            parsed = {str(k): str(v) for k, v in cookies_input.items()}
        else:
            logger.error(
                "设置cookies失败: cookies_input 类型错误，应为字符串或字典，得到 %s。",
                type(cookies_input),
            )
            raise TypeError("cookies_input 参数必须是字符串或字典类型。")

        self._client.cookies.clear()
        self._client.cookies.update(parsed)
        logger.info("客户端 cookies 已更新，共 %d 个。", len(parsed))

    def get_cookies(self) -> Dict[str, str]:
        cookies = self._client.cookies.get_dict()
        logger.debug("获取当前 cookies 副本，共 %d 个。", len(cookies))
        return cookies

    def _prepare_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        final_headers: Dict[str, str] = self._default_headers.copy()
        if additional_headers:
            final_headers.update(additional_headers)
        logger.debug("准备请求头: %s", final_headers)
        return final_headers

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        full_url: str = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._prepare_headers(headers)

        logger.info("发送 %s 请求到 %s", method, full_url)
        logger.debug("请求参数: %s, 表单数据: %s, JSON载荷: %s", params, data, json_payload is not None)

        response: Optional[Response] = None
        try:
            response = self._client.request(
                method=method,
                url=full_url,
                params=params,
                data=data,
                json=json_payload,
                headers=request_headers,
                timeout=self._timeout,
            )
            logger.debug("收到响应: 状态码 %s, URL: %s", response.status_code, response.url)
            response.raise_for_status()

            if not response.text:
                logger.info("请求 %s 成功，但响应体为空。返回空字典。", full_url)
                return {}

            json_response = response.json()
            logger.debug("成功解析响应为JSON: %s", str(json_response)[:200])
            return json_response
        except HTTPError as exc:
            status_code = exc.response.status_code if exc.response else "未知"
            resp_preview = exc.response.text[:200] if exc.response and exc.response.text else ""
            logger.error("HTTP错误 (%s %s): 状态码 %s, 响应: %s...", method, full_url, status_code, resp_preview)
            raise
        except RequestException as exc:
            logger.error("请求错误 (%s %s): %s", method, full_url, exc)
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            resp_text_preview = ""
            if response is not None and response.text:
                resp_text_preview = response.text[:200]
            logger.error("JSON解码错误 (%s %s): %s. 响应文本: %s...", method, full_url, exc, resp_text_preview)
            raise

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        return self.request("GET", endpoint, params=params, **kwargs)

    def post_form_urlencoded(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        custom_headers: Dict[str, str] = kwargs.pop("headers", {})
        if "Content-Type" not in custom_headers and "content-type" not in custom_headers:
            custom_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        return self.request("POST", endpoint, data=data, headers=custom_headers, **kwargs)

    def post_form_json(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        custom_headers: Dict[str, str] = kwargs.pop("headers", {})
        if "Content-Type" not in custom_headers and "content-type" not in custom_headers:
            custom_headers["Content-Type"] = "application/json; charset=utf-8"
        return self.request("POST", endpoint, json_payload=data, headers=custom_headers, **kwargs)

    def post_json(self, endpoint: str, json_payload: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        return self.request("POST", endpoint, json_payload=json_payload, **kwargs)

    def close(self) -> None:
        if not self._is_external_client:
            self._client.close()
            logger.info("内部 THSHttpApiClient 的 requests.Session 已关闭。")
        else:
            logger.debug("THSHttpApiClient 使用的是外部 Session，不在此处关闭。")

    def __enter__(self: T_HttpApiClient) -> T_HttpApiClient:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()

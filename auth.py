"""High-level helper for obtaining THS session cookies.

Steps implemented here:
1. Fetch the RSA public key from the auth endpoint.
2. Perform the unified login request to obtain ``userid`` and ``sessionid``.
3. Call ``mainverify`` to retrieve the ``signvalid`` field.
4. Exchange the trio for cookies via ``docookie2.php``.

Dependencies: ``requests`` and ``cryptography``. Install with
``pip install requests cryptography`` if they are not already available.
"""

import base64
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Union

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import COOKIE_CACHE_FILE, COOKIE_CACHE_TTL_SECONDS
from cookie import load_browser_cookie, parse_cookie_header, parse_cookie_string
from exceptions import THSAPIError, THSNetworkError
from storage import (
    load_cookie_cache_data,
    read_cached_cookies,
    write_cookie_cache,
)
from utils import parse_ths_xml_response

AUTH_BASE = "https://auth.10jqka.com.cn"
UPASS_BASE = "https://upass.10jqka.com.cn"
DOC_COOKIE_PATH = "/docookie2.php"
USER_AGENT = "同花顺/7.0.10 CFNetwork/1333.0.4 Darwin/21.5.0"
IMEI_ENCODED = "ZjI6MDY6NGE6NzI6MjQ6NTA="
QSID = "8003"
PRODUCT = "S01"
SECURITIES = r"%E5%90%8C%E8%8A%B1%E9%A1%BA%E8%BF%9C%E8%88%AA%E7%89%88"
RSA_VERSION_FALLBACK = "default_5"
TA_APP_ID = "2022021114090152"
REQUEST_TIMEOUT = 10.0


@dataclass(frozen=True)
class SessionResult:
    userid: str
    sessionid: str
    signvalid: str
    cookies: Dict[str, str]


@dataclass(frozen=True)
class LoginBundle:
    userid: str
    sessionid: str
    account: str
    rsa_version: str


@dataclass(frozen=True)
class RsaInfo:
    pubkey: str
    rsa_version: str


class SessionClient:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        auth_base: str = AUTH_BASE,
        upass_base: str = UPASS_BASE,
        timeout: float = REQUEST_TIMEOUT,
        http: Optional[requests.Session] = None,
    ) -> None:
        if not username or not password:
            raise ValueError("username/password are required; anonymous login is not supported")

        self._username = username
        self._password = password
        self._auth_base = auth_base.rstrip("/")
        self._upass_base = upass_base.rstrip("/")
        self._timeout = timeout
        self._http = http or requests.Session()
        self._http.headers.setdefault("User-Agent", USER_AGENT)

    def create_session(self) -> SessionResult:
        rsa_info = self._fetch_rsa_info()
        login_bundle = self._login(rsa_info)
        signvalid = self._fetch_signvalid(login_bundle)
        cookies = self._fetch_cookies(login_bundle.userid, login_bundle.sessionid, signvalid)
        return SessionResult(
            userid=login_bundle.userid,
            sessionid=login_bundle.sessionid,
            signvalid=signvalid,
            cookies=cookies,
        )

    def _fetch_rsa_info(self) -> RsaInfo:
        params = {"reqtype": "do_rsa", "type": "get_pubkey"}
        root = self._call_xml(f"{self._auth_base}/verify2", params, "RSA key fetch")
        item = root.find("item")
        if item is None:
            raise RuntimeError("RSA key fetch failed: <item> node missing")
        pubkey = item.attrib.get("pubkey")
        if not pubkey:
            raise RuntimeError("RSA key fetch failed: missing pubkey attribute")
        rsa_version = item.attrib.get("rsa_version", RSA_VERSION_FALLBACK)
        return RsaInfo(pubkey=pubkey, rsa_version=rsa_version)

    def _login(self, rsa_info: RsaInfo) -> LoginBundle:
        encrypted_account = self._encrypt_with_rsa(rsa_info.pubkey, self._username)
        encrypted_password = self._encrypt_with_rsa(rsa_info.pubkey, self._password)
        params = {
            "account": encrypted_account,
            "msg": "1",
            "passwd": encrypted_password,
            "reqtype": "unified_login",
            "rsa_version": rsa_info.rsa_version or RSA_VERSION_FALLBACK,
            "ta_appid": TA_APP_ID,
        }
        root = self._call_xml(f"{self._auth_base}/verify2", params, "Login")
        item = root.find("item")
        if item is None:
            raise RuntimeError("Login response missing <item> node")
        userid = item.attrib.get("userid")
        sessionid = item.attrib.get("sessionid")
        account = item.attrib.get("account")
        if not all([userid, sessionid, account]):
            raise RuntimeError("Login response missing required attributes (userid/sessionid/account)")
        rsa_version = item.attrib.get("rsa_version") or rsa_info.rsa_version or RSA_VERSION_FALLBACK
        return LoginBundle(
            userid=userid,
            sessionid=sessionid,
            account=account,
            rsa_version=rsa_version,
        )

    def _fetch_signvalid(self, login_bundle: LoginBundle) -> str:
        params = {
            "reqtype": "mainverify",
            "userid": login_bundle.userid,
            "sessionid": login_bundle.sessionid,
            "qsid": QSID,
            "product": PRODUCT,
            "version": "11.4.1.3",
            "imei": IMEI_ENCODED,
            "sdsn": "",
            "rsa_version": login_bundle.rsa_version or RSA_VERSION_FALLBACK,
            "nohqlist": "0",
            "securities": SECURITIES,
        }
        root = self._call_xml(f"{self._auth_base}/verify2", params, "Mainverify")
        item = root.find("item")
        if item is None:
            raise RuntimeError("Mainverify response missing <item> node")
        passport_blob = item.attrib.get("passport")
        if not passport_blob:
            raise RuntimeError("Mainverify response missing passport data")
        passport_map = self._parse_passport(passport_blob)
        signvalid = passport_map.get("signvalid")
        if not signvalid:
            raise RuntimeError("signvalid not present inside passport payload")
        return signvalid

    def _fetch_cookies(self, userid: str, sessionid: str, signvalid: str) -> Dict[str, str]:
        params = {"userid": userid, "sessionid": sessionid, "signvalid": signvalid}
        resp = self._http.get(
            f"{self._upass_base}{DOC_COOKIE_PATH}", params=params, timeout=self._timeout
        )
        resp.raise_for_status()
        cookies = resp.cookies.get_dict()
        if not cookies:
            cookie_header = resp.headers.get("Set-Cookie", "")
            if cookie_header:
                cookies = parse_cookie_header(cookie_header)
        if not cookies:
            raise RuntimeError("docookie2.php returned no cookies")
        return cookies

    def _call_xml(self, url: str, params: Dict[str, str], action: str) -> ET.Element:
        try:
            resp = self._http.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise THSNetworkError(action, str(exc)) from exc
        return parse_ths_xml_response(resp.text, action)

    @staticmethod
    def _encrypt_with_rsa(pubkey_pem: str, value: str) -> str:
        public_key = serialization.load_pem_public_key(pubkey_pem.encode("ascii"))
        encrypted = public_key.encrypt(value.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("ascii")

    @staticmethod
    def _parse_passport(passport_blob: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for chunk in passport_blob.split('|'):
            if not chunk or '=' not in chunk:
                continue
            key, value = chunk.split('=', 1)
            out[key.strip()] = value.strip()
        return out


class SessionManager:
    """Provide unified cookie resolution across login strategies."""

    def __init__(
        self,
        *,
        cookies: Optional[Union[Dict[str, str], str]] = None,
        auth_method: str = "browser",
        browser_name: str = "firefox",
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie_cache_path: Optional[str] = None,
        cookie_cache_ttl_seconds: int = COOKIE_CACHE_TTL_SECONDS,
        login_factory: Optional[Callable[[str, str], SessionResult]] = None,
    ) -> None:
        self._explicit_cookies = self._normalize_cookies(cookies)
        self._auth_method = (auth_method or "browser").lower()
        self._browser_name = browser_name
        self._username = username
        self._password = password
        self._cookie_cache_path = cookie_cache_path or COOKIE_CACHE_FILE
        self._cookie_cache_ttl = cookie_cache_ttl_seconds
        self._login_factory = login_factory or create_session
        self._resolved_cache: Optional[Dict[str, str]] = None

    def resolve(self) -> Optional[Dict[str, str]]:
        if self._explicit_cookies is not None:
            return self._explicit_cookies.copy()
        if self._resolved_cache is None:
            self._resolved_cache = self._resolve_from_strategy()
        return self._resolved_cache.copy() if self._resolved_cache else None

    def _resolve_from_strategy(self) -> Optional[Dict[str, str]]:
        if self._auth_method in {"none", "skip"}:
            return None
        if self._auth_method == "browser":
            cache_key = self._browser_cache_key(self._browser_name)
            return self._fetch_with_cache(cache_key, lambda: self._load_from_browser(self._browser_name))
        if self._auth_method in {"credentials", "login"}:
            return self._resolve_credentials_flow()
        raise ValueError(f"未知的 auth_method: {self._auth_method}")

    def _resolve_credentials_flow(self) -> Optional[Dict[str, str]]:
        if self._username and self._password:
            cache_key = self._credentials_cache_key(self._username)
            return self._fetch_with_cache(
                cache_key,
                lambda: self._load_from_credentials(self._username, self._password),
            )

        cached_by_user: Optional[Dict[str, str]] = None
        if self._username:
            cache_key = self._credentials_cache_key(self._username)
            cached_by_user = read_cached_cookies(
                self._cookie_cache_path,
                cache_key,
                self._cookie_cache_ttl,
            )
            if cached_by_user:
                return cached_by_user

        latest = self._load_latest_credentials_cache()
        if latest:
            return latest

        raise THSAPIError(
            "认证",
            "auth_method=credentials 需要提供 username/password，或预先缓存的凭据。",
        )

    def _fetch_with_cache(
        self,
        cache_key: str,
        loader: Callable[[], Optional[Dict[str, str]]],
    ) -> Optional[Dict[str, str]]:
        cached = read_cached_cookies(self._cookie_cache_path, cache_key, self._cookie_cache_ttl)
        if cached:
            return cached
        fresh = loader()
        if fresh:
            write_cookie_cache(self._cookie_cache_path, cache_key, fresh)
        return fresh

    def _load_from_browser(self, browser_name: str) -> Optional[Dict[str, str]]:
        cookies_raw = load_browser_cookie(browser_name)
        cookie_dict: Dict[str, str] = {}
        for cookie in cookies_raw:
            name = getattr(cookie, "name", None)
            value = getattr(cookie, "value", None)
            if name and value is not None:
                cookie_dict[str(name)] = str(value)
        return cookie_dict or None

    def _load_from_credentials(self, username: str, password: str) -> Optional[Dict[str, str]]:
        session = self._login_factory(username, password)
        return session.cookies

    def _load_latest_credentials_cache(self) -> Optional[Dict[str, str]]:
        cache_data = load_cookie_cache_data(self._cookie_cache_path)
        if not cache_data:
            return None
        latest_payload: Optional[Dict[str, str]] = None
        latest_ts = float("-inf")
        now = time.time()
        for key, entry in cache_data.items():
            if not isinstance(key, str) or not key.startswith("credentials::"):
                continue
            timestamp = entry.get("timestamp")
            try:
                timestamp_value = float(timestamp)
            except (TypeError, ValueError):
                continue
            if now - timestamp_value > self._cookie_cache_ttl:
                continue
            if timestamp_value <= latest_ts:
                continue
            cookies_payload = entry.get("cookies")
            if isinstance(cookies_payload, dict) and cookies_payload:
                latest_payload = {str(k): str(v) for k, v in cookies_payload.items()}
                latest_ts = timestamp_value
        return latest_payload

    @staticmethod
    def _browser_cache_key(browser_name: str) -> str:
        normalized = (browser_name or "default").lower()
        return f"browser::{normalized}"

    @staticmethod
    def _credentials_cache_key(username: str) -> str:
        digest = hashlib.sha256(username.encode("utf-8")).hexdigest()
        return f"credentials::{digest}"

    @staticmethod
    def _normalize_cookies(cookies_input: Optional[Union[Dict[str, str], str]]) -> Optional[Dict[str, str]]:
        if cookies_input is None:
            return None
        if isinstance(cookies_input, dict):
            return {str(k): str(v) for k, v in cookies_input.items()}
        if isinstance(cookies_input, str):
            return parse_cookie_string(cookies_input)
        raise TypeError("cookies 必须是字典或字符串")


def create_session(username: str, password: str) -> SessionResult:
    """Convenience wrapper that returns ``SessionResult`` for the given credentials."""
    client = SessionClient(username=username, password=password)
    return client.create_session()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch THS session cookies")
    parser.add_argument("username", help="账号")
    parser.add_argument("password", help="密码")
    args = parser.parse_args()

    session_result = create_session(args.username, args.password)
    print(
        json.dumps(
            {
                "userid": session_result.userid,
                "sessionid": session_result.sessionid,
                "signvalid": session_result.signvalid,
                "cookies": session_result.cookies,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

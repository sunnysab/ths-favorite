"""High-level helper for obtaining THS session cookies.

Steps implemented here:
1. Fetch the RSA public key from the auth endpoint.
2. Perform the unified login request to obtain ``userid`` and ``sessionid``.
3. Call ``mainverify`` to retrieve the ``signvalid`` field.
4. Exchange the trio for cookies via ``docookie2.php``.

Dependencies: ``requests`` and ``cryptography``. Install with
``pip install requests cryptography`` if they are not already available.
"""
from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Optional

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

AUTH_BASE = "http://auth.10jqka.com.cn"
UPASS_BASE = "http://upass.10jqka.com.cn"
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
        pubkey = item.attrib["pubkey"]
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
        rsa_version = item.attrib.get("rsa_version") or rsa_info.rsa_version or RSA_VERSION_FALLBACK
        return LoginBundle(
            userid=item.attrib["userid"],
            sessionid=item.attrib["sessionid"],
            account=item.attrib["account"],
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
                cookies = self._parse_cookie_header(cookie_header)
        if not cookies:
            raise RuntimeError("docookie2.php returned no cookies")
        return cookies

    def _call_xml(self, url: str, params: Dict[str, str], action: str) -> ET.Element:
        resp = self._http.get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        self._ensure_success(root, action)
        return root

    @staticmethod
    def _ensure_success(root: ET.Element, action: str) -> None:
        ret_node = root.find("ret")
        if ret_node is None:
            raise RuntimeError(f"{action} failed: <ret> node missing")
        code = int(ret_node.attrib.get("code", "-1"))
        if code != 0:
            raise RuntimeError(f"{action} failed: {ret_node.attrib.get('msg', 'unknown error')}")

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

    @staticmethod
    def _parse_cookie_header(header: str) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        for part in header.split(','):
            segment = part.strip()
            if not segment:
                continue
            pair = segment.split(';', 1)[0]
            if '=' not in pair:
                continue
            name, value = pair.split('=', 1)
            cookies[name.strip()] = value.strip()
        return cookies


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

from __future__ import annotations

from http.cookiejar import Cookie, CookieJar
from typing import Dict, List

try:
    import browser_cookie3 as cookie_jar
except ImportError:  # pragma: no cover - 友好的错误提示更重要
    cookie_jar = None


def load_browser_cookie(browser: str) -> List[Cookie]:
    """Load cookies for *.10jqka.com.cn from a local browser profile.

    Args:
        browser: Browser name, e.g. ``"firefox"``, ``"chrome"`` or ``"edge"``.

    Returns:
        A list of :class:`http.cookiejar.Cookie` objects that belong to
        ``.10jqka.com.cn``.

    Raises:
        RuntimeError: If ``browser-cookie3`` is not installed.
        ValueError: If the browser is unsupported or the cookies cannot be
            located in the profile database.
    """

    if cookie_jar is None:
        raise RuntimeError(
            "检测到未安装 browser-cookie3，浏览器自动登录功能不可用。"
            "请运行 'pip install browser-cookie3' 或在 THSUserFavorite 中手动提供 cookies。"
        )

    load = None
    match browser.lower():
        case "chrome":
            load = cookie_jar.chrome
        case "firefox":
            load = cookie_jar.firefox
        case "edge":
            load = cookie_jar.edge
        case _:
            raise ValueError(f"Browser {browser} not supported")

    cookies: CookieJar = load(domain_name=".10jqka.com.cn")
    try:
        ths_session: List[Cookie] = cookies.__dict__["_cookies"][".10jqka.com.cn"]["/"]
    except ValueError as exc:
        raise ValueError("Cookie not found") from exc

    return ths_session


def parse_cookie_string(raw: str) -> Dict[str, str]:
    """Parse a ``Cookie`` header string into a dictionary."""

    cookies: Dict[str, str] = {}
    if not raw:
        return cookies
    for pair_str in raw.split(";"):
        pair_str = pair_str.strip()
        if not pair_str or "=" not in pair_str:
            continue
        name, value = pair_str.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def parse_cookie_header(header: str) -> Dict[str, str]:
    """Parse a ``Set-Cookie`` style header containing comma-separated cookies."""

    cookies: Dict[str, str] = {}
    if not header:
        return cookies
    for part in header.split(","):
        segment = part.strip()
        if not segment:
            continue
        pair = segment.split(";", 1)[0]
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies
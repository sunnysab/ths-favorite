from http.cookiejar import CookieJar, Cookie
from typing import List


def load_browser_cookie(browser: str) -> List[Cookie]:
    """
    从指定的浏览器中加载同花顺站点的 cookie
    """

    import browser_cookie3 as cookie_jar

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

    cookies: CookieJar = load(domain_name='.10jqka.com.cn')
    try:
        ths_session: List[Cookie] = cookies.__dict__['_cookies']['.10jqka.com.cn']['/']
    except ValueError as e:
        raise ValueError("Cookie not found") from e

    return ths_session.values()


if __name__ == "__main__":
    # 测试代码
    cookie = load_browser_cookie('firefox')
    print(cookie)
    # cookie = load_browser_cookie_or_none("chrome")
    # print(cookie)
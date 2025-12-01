from __future__ import annotations

from typing import Dict

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Hexin_Gphone/11.28.03 (Royal Flush) hxtheme/0 innerversion/G037.09.028.1.32 "
        "followPhoneSystemTheme/0 userid/000000000 getHXAPPAccessibilityMode/0 "
        "hxNewFont/1 isVip/0 getHXAPPFontSetting/normal getHXAPPAdaptOldSetting/0 okhttp/3.14.9"
    ),
}

API_BASE_URL: str = "https://ugc.10jqka.com.cn"

ENDPOINTS = {
    "query_groups": "/optdata/selfgroup/open/api/group/v1/query",
    "add_item": "/optdata/selfgroup/open/api/content/v1/add",
    "delete_item": "/optdata/selfgroup/open/api/content/v1/delete",
    "add_group": "/optdata/selfgroup/open/api/group/v1/add",
    "delete_group": "/optdata/selfgroup/open/api/group/v1/delete",
    "share_group": "/optdata/sharing_service/open/api/sharing/v1/create",
}

GROUP_CACHE_FILE: str = "ths_favorite_cache.json"
COOKIE_CACHE_FILE: str = "ths_cookie_cache.json"
COOKIE_CACHE_TTL_SECONDS: int = 24 * 60 * 60

DEFAULT_FROM_PARAM: str = "sjcg_gphone"
GROUP_QUERY_TYPES: str = "0,1"
DEFAULT_HTTP_TIMEOUT: float = 10.0

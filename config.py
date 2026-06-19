DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Hexin_Gphone/11.28.03 (Royal Flush) hxtheme/0 innerversion/G037.09.028.1.32 "
        "followPhoneSystemTheme/0 userid/000000000 getHXAPPAccessibilityMode/0 "
        "hxNewFont/1 isVip/0 getHXAPPFontSetting/normal getHXAPPAdaptOldSetting/0 okhttp/3.14.9"
    ),
}

API_BASE_URL: str = "https://ugc.10jqka.com.cn"
SELF_STOCK_V2_BASE_URL: str = "https://t.10jqka.com.cn"
SELF_STOCK_V2_LIST_PATH: str = "/newcircle/group/getSelfStockWithMarket/"
SELF_STOCK_V2_MODIFY_PATH: str = "/newcircle/group/modifySelfStock/"

# Self-stock v1 (batch) API — operates on "我的自选" via full-replace
SELF_STOCK_V1_BASE_URL: str = "https://ugc.10jqka.com.cn"
SELF_STOCK_V1_QUERY_PATH: str = "/optdata/selfstock/open/api/v1/query"
SELF_STOCK_V1_MODIFY_PATH: str = "/optdata/selfstock/open/api/v1/modify"

# multiStorage blockstock API — operates on all groups (我的自选 + custom)
MULTI_STORAGE_URL: str = "https://cs.10jqka.com.cn/multiStorage"
BLOCKSTOCK_APPNAME: str = "blockstock"
MULTI_STORAGE_DEFAULT_CLIENTTYPE: str = "hevo_pc"

# Dynamic plate API — queries stocks in 同花顺 concept/sector plates (1_ groups)
DYNAMIC_PLATE_BASE_URL: str = "https://apigate.10jqka.com.cn"
DYNAMIC_PLATE_SELECT_PATH: str = "/d/platform/dynamicplate/stocks/self/v2/select"

ENDPOINTS = {
    "query_groups": "/optdata/selfgroup/open/api/group/v1/query",
    "add_item": "/optdata/selfgroup/open/api/content/v1/add",
    "delete_item": "/optdata/selfgroup/open/api/content/v1/delete",
    "add_group": "/optdata/selfgroup/open/api/group/v1/add",
    "delete_group": "/optdata/selfgroup/open/api/group/v1/delete",
    "share_group": "/optdata/sharing_service/open/api/sharing/v1/create",
}

GROUP_CACHE_FILE: str = "ths_favorite_cache.json"
SELF_STOCK_CACHE_FILE: str = "ths_self_stock_cache.json"
COOKIE_CACHE_FILE: str = "ths_cookie_cache.json"
COOKIE_CACHE_TTL_SECONDS: int = 24 * 60 * 60
SELF_STOCK_GROUP_ID: str = "__selfstock__"
SELF_STOCK_DEFAULT_NAME: str = "我的自选"

DEFAULT_FROM_PARAM: str = "sjcg_gphone"
GROUP_QUERY_TYPES: str = "0,1"
DEFAULT_HTTP_TIMEOUT: float = 10.0
SELF_STOCK_HTTP_TIMEOUT: float = 10.0

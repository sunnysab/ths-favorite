# -*- coding: utf-8 -*-

__MARKET_CODE = {
    'SH': '17',    # 上海证券交易所
    'SHETF': '20', # 上海证券交易所ETF
    'ST': '22',    # 上海证券交易所ST
    'SZ': '33',    # 深圳证券交易所
    'SZETF': '36', # 深圳证券交易所ETF
    'ZS': '48',    # 指数
    'CYB': '38',   # 创业板
    'KC': '18',    # 科创板
    'BJ': '71',    # 北京证券交易所
    'HK': '55',    # 港股
    'US': '61',    # 美股
    'FT': '50',    # 期货
    'QH': '51',    # 期货主力
    'QZ': '53',    # 期指
    'OP': '79',    # 期权
    'JJ': '39',    # 基金
    'ZQ': '45',    # 债券
    'XSB': '67',   # 新三板
}


# 生成一个反向的、CODE -> MARKET 的字典
__MARKET_NAME = {v: k for k, v in __MARKET_CODE.items()}

def market_abbr(market_type: str) -> str:
    """
    将市场类型代码映射为对应的名称缩写
    """
    assert market_type
    return __MARKET_NAME.get(market_type, market_type)

def market_code(market_abbr: str) -> str:
    """
    将市场类型缩写映射为对应的代码
    """
    assert market_abbr
    return __MARKET_CODE.get(market_abbr.upper(), market_abbr)

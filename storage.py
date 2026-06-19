import json
import os
import time
from typing import Any

from loguru import logger

from models import StockGroup, StockItem


def load_cache(cache_file: str) -> tuple[dict[str, StockGroup], StockGroup | None]:
    """Load cached groups and self stock from disk.

    Returns (groups, self_stock).
    Both are empty/None when the cache file does not exist or is corrupt.
    """

    logger.info(f"尝试从文件 '{cache_file}' 加载缓存...")
    if not os.path.exists(cache_file):
        logger.info(f"缓存文件 '{cache_file}' 不存在，跳过加载。")
        return {}, None

    try:
        with open(cache_file, encoding='utf-8') as fp:
            root: dict[str, Any] = json.load(fp)
    except json.JSONDecodeError:
        logger.error(f"错误: 缓存文件 '{cache_file}' 内容不是有效的JSON格式。缓存未加载。")
        return {}, None
    except Exception:
        logger.exception('从文件加载缓存时发生未知错误。')
        return {}, None

    groups_data: list[dict[str, Any]] = root.get('groups', []) if isinstance(root, dict) else []
    groups: dict[str, StockGroup] = {}
    for group_data in groups_data:
        items: list[StockItem] = [
            StockItem(code=item_dict['code'], market=item_dict.get('market'))
            for item_dict in group_data.get('items', [])
            if item_dict.get('code')
        ]
        group_name: str | None = group_data.get('name')
        group_id: str | None = group_data.get('group_id')
        if not group_name or not group_id:
            logger.warning(f'缓存中发现不完整的分组数据，已跳过: {group_data}')
            continue
        groups[group_name] = StockGroup(name=group_name, group_id=group_id, items=items)

    self_stock_data: dict[str, Any] | None = root.get('self_stock') if isinstance(root, dict) else None
    self_stock: StockGroup | None = None
    if isinstance(self_stock_data, dict):
        self_stock_items: list[StockItem] = [
            StockItem(code=item_dict['code'], market=item_dict.get('market'))
            for item_dict in self_stock_data.get('items', [])
            if item_dict.get('code')
        ]
        group_name = self_stock_data.get('name')
        group_id = self_stock_data.get('group_id')
        if group_name and group_id:
            self_stock = StockGroup(name=group_name, group_id=group_id, items=self_stock_items)

    logger.info(
        f"已从 '{cache_file}' 加载 {len(groups)} 个分组"
        + (f"，自选股「{self_stock.name}」" if self_stock else "，无自选股缓存")
        + "。"
    )
    return groups, self_stock


def save_cache(
    cache_file: str,
    groups: dict[str, StockGroup],
    self_stock: StockGroup | None,
) -> None:
    """Persist groups and self stock into a single cache file."""

    serializable: dict[str, Any] = {}

    serializable['groups'] = [
        {
            'name': group_obj.name,
            'group_id': group_obj.group_id,
            'items': [
                {'code': item.code, 'market': item.market} for item in group_obj.items
            ],
        }
        for group_obj in groups.values()
    ]

    if self_stock is not None:
        serializable['self_stock'] = {
            'name': self_stock.name,
            'group_id': self_stock.group_id,
            'items': [
                {'code': item.code, 'market': item.market} for item in self_stock.items
            ],
        }

    logger.info(
        f"尝试将 {len(serializable['groups'])} 个分组"
        + (" 及自选股" if self_stock else "")
        + f" 保存到缓存文件 '{cache_file}'..."
    )
    try:
        with open(cache_file, 'w', encoding='utf-8') as fp:
            json.dump(serializable, fp, ensure_ascii=False, indent=2)
        logger.info(f"已成功保存缓存到 '{cache_file}'。")
    except Exception:
        logger.exception('保存缓存到文件时发生错误。')


def load_cookie_cache_data(cache_path: str) -> dict[str, Any]:
    """Read the entire cookie cache file into memory."""

    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, encoding='utf-8') as fp:
            cached_data = json.load(fp)
        if isinstance(cached_data, dict):
            return cached_data
    except json.JSONDecodeError:
        logger.warning(f"cookies 缓存文件 '{cache_path}' 内容无效，将忽略。")
    except Exception:
        logger.exception('读取 cookies 缓存文件失败。')
    return {}


def read_cached_cookies(cache_path: str, cache_key: str, ttl_seconds: int) -> dict[str, str] | None:
    """Return cached cookies when still valid.

    Args:
        cache_path: 缓存文件路径。
        cache_key: 浏览器或账号对应的 key。
        ttl_seconds: 超时时间。

    Returns:
        dict[str, str] | None: 可复用的 cookies。
    """

    cache_data = load_cookie_cache_data(cache_path)
    entry = cache_data.get(cache_key)
    if not entry:
        return None

    timestamp = entry.get('timestamp')
    try:
        timestamp_value = float(timestamp)
    except (TypeError, ValueError):
        return None

    if time.time() - timestamp_value > ttl_seconds:
        logger.info(f'cookies 缓存已过期: {cache_key}')
        return None

    cookies_payload = entry.get('cookies')
    if isinstance(cookies_payload, dict) and cookies_payload:
        return {str(k): str(v) for k, v in cookies_payload.items()}
    return None


def read_cached_auth_params(
    cache_path: str, cache_key: str, ttl_seconds: int
) -> dict[str, str] | None:
    """Return cached multiStorage auth params when still valid."""
    cache_data = load_cookie_cache_data(cache_path)
    entry = cache_data.get(cache_key)
    if not entry:
        return None
    timestamp = entry.get('timestamp')
    try:
        timestamp_value = float(timestamp)
    except (TypeError, ValueError):
        return None
    if time.time() - timestamp_value > ttl_seconds:
        return None
    auth = entry.get('auth_params')
    if isinstance(auth, dict) and auth:
        return {str(k): str(v) for k, v in auth.items()}
    return None


def write_cookie_cache(
    cache_path: str,
    cache_key: str,
    cookies_payload: dict[str, str],
    *,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Upsert cookies plus timestamp into the cache file."""

    cache_data = load_cookie_cache_data(cache_path)
    entry: dict[str, Any] = {
        'cookies': {str(k): str(v) for k, v in cookies_payload.items()},
        'timestamp': time.time(),
    }
    if extra_fields:
        entry.update(extra_fields)
    cache_data[cache_key] = entry

    dir_name = os.path.dirname(cache_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    try:
        with open(cache_path, 'w', encoding='utf-8') as fp:
            json.dump(cache_data, fp, ensure_ascii=False, indent=2)
        logger.info(f'已更新 cookies 缓存: {cache_path} -> {cache_key}')
    except Exception:
        logger.exception('写入 cookies 缓存文件失败。')

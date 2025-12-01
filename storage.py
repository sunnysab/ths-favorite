from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from models import THSFavorite, THSFavoriteGroup


def load_groups_cache(cache_file: str) -> Dict[str, THSFavoriteGroup]:
    """Load cached groups from disk into THSFavoriteGroup instances.

    Args:
        cache_file: JSON 文件路径。

    Returns:
        dict[str, THSFavoriteGroup]: 以分组名称为键的缓存字典。
    """

    logger.info(f"尝试从文件 '{cache_file}' 加载分组缓存...")
    if not os.path.exists(cache_file):
        logger.info(f"缓存文件 '{cache_file}' 不存在，跳过加载。")
        return {}

    try:
        with open(cache_file, "r", encoding="utf-8") as fp:
            cached_groups_data: List[Dict[str, Any]] = json.load(fp)
    except json.JSONDecodeError:
        logger.error(f"错误: 缓存文件 '{cache_file}' 内容不是有效的JSON格式。缓存未加载。")
        return {}
    except Exception:
        logger.exception("从文件加载缓存时发生未知错误。")
        return {}

    groups: Dict[str, THSFavoriteGroup] = {}
    for group_data in cached_groups_data:
        items: List[THSFavorite] = [
            THSFavorite(code=item_dict["code"], market=item_dict.get("market"))
            for item_dict in group_data.get("items", [])
            if item_dict.get("code")
        ]
        group_name: Optional[str] = group_data.get("name")
        group_id: Optional[str] = group_data.get("group_id")
        if not group_name or not group_id:
            logger.warning(f"缓存中发现不完整的分组数据，已跳过: {group_data}")
            continue
        groups[group_name] = THSFavoriteGroup(name=group_name, group_id=group_id, items=items)

    logger.info(f"已从 '{cache_file}' 加载 {len(groups)} 个分组到缓存。")
    return groups


def save_groups_cache(cache_file: str, groups: Dict[str, THSFavoriteGroup]) -> None:
    """Persist in-memory groups onto disk for faster warm start."""

    logger.info(f"尝试将 {len(groups)} 个分组保存到缓存文件 '{cache_file}'...")
    try:
        serializable: List[Dict[str, Any]] = []
        for group_obj in groups.values():
            serializable.append(
                {
                    "name": group_obj.name,
                    "group_id": group_obj.group_id,
                    "items": [
                        {"code": item.code, "market": item.market}
                        for item in group_obj.items
                    ],
                }
            )

        with open(cache_file, "w", encoding="utf-8") as fp:
            json.dump(serializable, fp, ensure_ascii=False, indent=2)
        logger.info(f"已成功将 {len(serializable)} 个分组保存到缓存文件 '{cache_file}'。")
    except Exception:
        logger.exception("保存缓存到文件时发生错误。")


def load_cookie_cache_data(cache_path: str) -> Dict[str, Any]:
    """Read the entire cookie cache file into memory."""

    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as fp:
            cached_data = json.load(fp)
        if isinstance(cached_data, dict):
            return cached_data
    except json.JSONDecodeError:
        logger.warning(f"cookies 缓存文件 '{cache_path}' 内容无效，将忽略。")
    except Exception:
        logger.exception("读取 cookies 缓存文件失败。")
    return {}


def read_cached_cookies(cache_path: str, cache_key: str, ttl_seconds: int) -> Optional[Dict[str, str]]:
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

    timestamp = entry.get("timestamp")
    try:
        timestamp_value = float(timestamp)
    except (TypeError, ValueError):
        return None

    if time.time() - timestamp_value > ttl_seconds:
        logger.info(f"cookies 缓存已过期: {cache_key}")
        return None

    cookies_payload = entry.get("cookies")
    if isinstance(cookies_payload, dict) and cookies_payload:
        return {str(k): str(v) for k, v in cookies_payload.items()}
    return None


def write_cookie_cache(cache_path: str, cache_key: str, cookies_payload: Dict[str, str]) -> None:
    """Upsert cookies plus timestamp into the cache file."""

    cache_data = load_cookie_cache_data(cache_path)
    cache_data[cache_key] = {
        "cookies": {str(k): str(v) for k, v in cookies_payload.items()},
        "timestamp": time.time(),
    }

    dir_name = os.path.dirname(cache_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    try:
        with open(cache_path, "w", encoding="utf-8") as fp:
            json.dump(cache_data, fp, ensure_ascii=False, indent=2)
        logger.info(f"已更新 cookies 缓存: {cache_path} -> {cache_key}")
    except Exception:
        logger.exception("写入 cookies 缓存文件失败。")

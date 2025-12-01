#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from datetime import datetime
from typing import Any, Optional

from loguru import logger
from tabulate import tabulate

from favorite import THSUserFavorite


def _format_price(value: Optional[Any]) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_epoch_timestamp(value: float) -> str:
    timestamp = value
    if timestamp > 1_000_000_000_000:  # milliseconds
        timestamp /= 1000.0
    try:
        dt_obj = datetime.fromtimestamp(timestamp)
    except (OSError, ValueError):
        return "-"
    return dt_obj.strftime("%Y-%m-%d %H:%M")


def _format_added_at(raw: Any) -> str:
    if raw in (None, ""):
        return "-"

    if isinstance(raw, float):
        if not raw.is_integer():
            return _format_epoch_timestamp(float(raw))
        raw = int(raw)

    if isinstance(raw, int):
        text = str(raw)
    else:
        text = str(raw).strip()

    if not text:
        return "-"

    if text.isdigit():
        if len(text) == 8:
            try:
                dt_obj = datetime.strptime(text, "%Y%m%d")
                return dt_obj.strftime("%Y-%m-%d")
            except ValueError:
                pass
        elif len(text) == 14:
            try:
                dt_obj = datetime.strptime(text, "%Y%m%d%H%M%S")
                return dt_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
        elif len(text) in (10, 13):
            try:
                epoch_value = float(text)
            except ValueError:
                epoch_value = None
            if epoch_value is not None:
                return _format_epoch_timestamp(epoch_value)

    return text


def list_groups(ths: THSUserFavorite):
    """列出所有分组及其股票数量"""
    groups = ths.get_all_groups()
    if not groups:
        print("未找到任何分组。")
        return

    rows = []
    for name, group in sorted(groups.items()):
        rows.append([name, group.group_id, len(group.items)])

    print(f"共有 {len(rows)} 个分组:")
    print(tabulate(rows, headers=["分组名称", "分组ID", "股票数量"], tablefmt="github"))


def list_stocks(ths: THSUserFavorite, group_name: str):
    """列出指定分组中的所有股票"""
    groups = ths.get_all_groups()

    if group_name not in groups:
        print(f"未找到名为 '{group_name}' 的分组")
        return

    group = groups[group_name]
    if not group.items:
        print(f"分组 '{group_name}' (ID: {group.group_id}) 暂无股票。")
        return

    rows = []
    for item in sorted(group.items, key=lambda entry: (entry.code, entry.market or "")):
        code_with_market = f"{item.code}.{item.market}" if item.market else item.code
        rows.append([
            code_with_market,
            item.market or "-",
            _format_price(item.price),
            _format_added_at(item.added_at),
        ])

    print(f"分组 '{group_name}' (ID: {group.group_id}) 包含 {len(group.items)} 个股票:")
    print(tabulate(rows, headers=["代码", "市场", "加入价", "加入时间"], tablefmt="github"))


def main():
    parser = argparse.ArgumentParser(description="同花顺自选股管理工具")
    parser.add_argument("--auth-method", choices=["browser", "credentials", "none"], default="browser",
                        help="选择获取 cookies 的方式: browser / credentials / none")
    parser.add_argument("--browser", default="firefox", help="当 auth-method=browser 时指定浏览器名称")
    parser.add_argument("--username", help="当 auth-method=credentials 时使用的账号")
    parser.add_argument("--password", help="当 auth-method=credentials 时使用的密码")
    parser.add_argument("--cookie-cache", help="自定义 cookies 缓存文件路径")

    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出分组")
    list_parser.add_argument("-g", "--group", help="指定分组名称，列出该分组中的股票")
    
    # add 命令
    add_parser = subparsers.add_parser("add", help="添加股票到分组")
    add_parser.add_argument("group", help="分组名称或ID")
    add_parser.add_argument("stock", help="股票代码，格式: code.market (如: 600519.SH)")
    
    # delete 命令
    del_parser = subparsers.add_parser("delete", help="从分组删除股票")
    del_parser.add_argument("group", help="分组名称或ID")
    del_parser.add_argument("stock", help="股票代码，格式: code.market (如: 600519.SH)")

    # group add
    group_add_parser = subparsers.add_parser("group-add", help="创建新的分组")
    group_add_parser.add_argument("name", help="要创建的分组名称")

    # group delete
    group_delete_parser = subparsers.add_parser("group-delete", help="删除现有分组")
    group_delete_parser.add_argument("group", help="分组名称或ID")

    # group share
    group_share_parser = subparsers.add_parser("group-share", help="分享分组获取链接")
    group_share_parser.add_argument("group", help="分组名称或ID")
    group_share_parser.add_argument("valid_time", type=int, help="分享链接有效期（秒）")
    
    args = parser.parse_args()
    
    # 创建 THSUserFavorite 实例
    with THSUserFavorite(
        auth_method=args.auth_method,
        browser_name=args.browser,
        username=args.username,
        password=args.password,
        cookie_cache_path=args.cookie_cache
    ) as ths:
        # 处理命令
        if args.command == "list":
            if args.group:
                list_stocks(ths, args.group)
            else:
                list_groups(ths)
        elif args.command == "add":
            result = ths.add_item_to_group(args.group, args.stock)
            if result:
                print(f"已成功添加 {args.stock} 到分组 '{args.group}'")
        elif args.command == "delete":
            result = ths.delete_item_from_group(args.group, args.stock)
            if result:
                print(f"已成功从分组 '{args.group}' 删除 {args.stock}")
        elif args.command == "group-add":
            result = ths.add_group(args.name)
            if result:
                print(f"已成功创建分组 '{args.name}'")
        elif args.command == "group-delete":
            result = ths.delete_group(args.group)
            if result:
                print(f"已成功删除分组 '{args.group}'")
        elif args.command == "group-share":
            result = ths.share_group(args.group, args.valid_time)
            if result:
                share_url = result.get("share_url") if isinstance(result, dict) else None
                if share_url:
                    print(f"分享链接: {share_url}")
                else:
                    print("分享分组成功，但未返回链接。")
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    main()

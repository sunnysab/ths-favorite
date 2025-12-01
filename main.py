#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from datetime import datetime
from typing import Any, Optional

from loguru import logger
from tabulate import tabulate

from exceptions import THSAPIError, THSNetworkError
from service import PortfolioManager


def _format_price(value: Optional[Any]) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_epoch_timestamp(value: float) -> str:
    timestamp = value
    if timestamp > 1_000_000_000_000:
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


def build_parser() -> argparse.ArgumentParser:
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--auth-method",
        choices=["browser", "credentials", "none"],
        default=argparse.SUPPRESS,
        help="选择获取 cookies 的方式",
    )
    global_parser.add_argument(
        "--browser",
        default=argparse.SUPPRESS,
        help="当 auth-method=browser 时指定浏览器名称",
    )
    global_parser.add_argument("--username", default=argparse.SUPPRESS, help="当 auth-method=credentials 时使用的账号")
    global_parser.add_argument("--password", default=argparse.SUPPRESS, help="当 auth-method=credentials 时使用的密码")
    global_parser.add_argument("--cookie-cache", default=argparse.SUPPRESS, help="自定义 cookies 缓存文件路径")

    parser = argparse.ArgumentParser(
        description="同花顺自选股管理工具",
        parents=[global_parser],
    )
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list",
        parents=[global_parser],
        help="列出所有分组或指定分组",
    )
    list_parser.add_argument("-g", "--group", help="指定分组名称，列出该分组中的股票")

    group_parser = subparsers.add_parser(
        "group",
        parents=[global_parser],
        help="分组管理相关操作",
    )
    group_subparsers = group_parser.add_subparsers(dest="group_command")
    group_subparsers.required = True

    group_list_parser = group_subparsers.add_parser(
        "list",
        parents=[global_parser],
        help="列出全部分组或指定分组",
    )
    group_list_parser.add_argument("-g", "--group", help="指定分组名称，列出该分组中的股票")

    group_add_parser = group_subparsers.add_parser(
        "add",
        parents=[global_parser],
        help="创建新的分组",
    )
    group_add_parser.add_argument("name", help="要创建的分组名称")

    group_del_parser = group_subparsers.add_parser(
        "del",
        parents=[global_parser],
        help="删除现有分组",
    )
    group_del_parser.add_argument("group", help="分组名称或ID")

    group_share_parser = group_subparsers.add_parser(
        "share",
        parents=[global_parser],
        help="分享分组获取链接",
    )
    group_share_parser.add_argument("group", help="分组名称或ID")
    group_share_parser.add_argument("valid_time", type=int, help="分享链接有效期（秒）")

    stock_parser = subparsers.add_parser(
        "stock",
        parents=[global_parser],
        help="股票相关操作",
    )
    stock_subparsers = stock_parser.add_subparsers(dest="stock_command")
    stock_subparsers.required = True

    stock_add_parser = stock_subparsers.add_parser(
        "add",
        parents=[global_parser],
        help="向分组添加股票",
    )
    stock_add_parser.add_argument("group", help="分组名称或ID")
    stock_add_parser.add_argument("stock", help="股票代码，格式: code.market (如: 600519.SH)")

    stock_del_parser = stock_subparsers.add_parser(
        "del",
        parents=[global_parser],
        help="从分组删除股票",
    )
    stock_del_parser.add_argument("group", help="分组名称或ID")
    stock_del_parser.add_argument("stock", help="股票代码，格式: code.market (如: 600519.SH)")

    return parser


def apply_global_defaults(args: argparse.Namespace) -> None:
    defaults = {
        "auth_method": "browser",
        "browser": "firefox",
        "username": None,
        "password": None,
        "cookie_cache": None,
    }
    for key, value in defaults.items():
        if not hasattr(args, key):
            setattr(args, key, value)


def list_groups(manager: PortfolioManager, group_name: Optional[str] = None) -> None:
    if group_name:
        list_stocks(manager, group_name)
        return

    groups = manager.get_all_groups()
    if not groups:
        print("未找到任何分组。")
        return

    rows = []
    for name in sorted(groups.keys()):
        group = groups[name]
        rows.append([name, group.group_id, len(group.items)])

    print(f"共有 {len(rows)} 个分组:")
    print(tabulate(rows, headers=["分组名称", "分组ID", "股票数量"], tablefmt="github"))


def list_stocks(manager: PortfolioManager, group_name: str) -> None:
    groups = manager.get_all_groups()
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
        rows.append(
            [
                code_with_market,
                item.market or "-",
                _format_price(item.price),
                _format_added_at(item.added_at),
            ]
        )

    print(f"分组 '{group_name}' (ID: {group.group_id}) 包含 {len(group.items)} 个股票:")
    print(tabulate(rows, headers=["代码", "市场", "加入价", "加入时间"], tablefmt="github"))


def handle_group_command(manager: PortfolioManager, args: argparse.Namespace) -> None:
    if args.group_command == "list":
        list_groups(manager, getattr(args, "group", None))
    elif args.group_command == "add":
        manager.add_group(args.name)
        print(f"✅ 已成功创建分组 '{args.name}'")
    elif args.group_command == "del":
        manager.delete_group(args.group)
        print(f"🗑️ 已删除分组 '{args.group}'")
    elif args.group_command == "share":
        result = manager.share_group(args.group, args.valid_time)
        share_url = result.get("share_url") if isinstance(result, dict) else None
        if share_url:
            print(f"🔗 分享链接: {share_url}")
        else:
            print("✅ 分享分组成功，但未返回链接。")


def handle_stock_command(manager: PortfolioManager, args: argparse.Namespace) -> None:
    if args.stock_command == "add":
        manager.add_item_to_group(args.group, args.stock)
        print(f"✅ 已将 {args.stock} 添加到分组 '{args.group}'")
    elif args.stock_command == "del":
        manager.delete_item_from_group(args.group, args.stock)
        print(f"🗑️ 已从分组 '{args.group}' 删除 {args.stock}")


def execute(args: argparse.Namespace) -> None:
    manager_kwargs = {
        "auth_method": args.auth_method,
        "browser_name": args.browser,
        "username": args.username,
        "password": args.password,
        "cookie_cache_path": args.cookie_cache,
    }

    with PortfolioManager(**manager_kwargs) as manager:
        if args.command == "list":
            list_groups(manager, getattr(args, "group", None))
        elif args.command == "group":
            handle_group_command(manager, args)
        elif args.command == "stock":
            handle_stock_command(manager, args)
        else:
            raise THSAPIError("命令", f"未知的命令 {args.command}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    apply_global_defaults(args)
    if args.command is None:
        args.command = "list"
        if not hasattr(args, "group"):
            args.group = None
    execute(args)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    try:
        main()
    except THSNetworkError as exc:
        print(f"❌ 网络错误: {exc}")
        sys.exit(2)
    except THSAPIError as exc:
        print(f"❌ 操作失败: {exc}")
        sys.exit(3)
    except Exception as exc:
        logger.exception("未预料的错误")
        print(f"❌ 未预期错误: {exc}")
        sys.exit(1)

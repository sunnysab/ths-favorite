#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from favorite import THSUserFavorite


def list_groups(ths: THSUserFavorite):
    """列出所有分组及其股票数量"""
    groups = ths.get_all_groups()
    print(f"共有 {len(groups)} 个分组:")
    
    for name, group in groups.items():
        print(f"- {name} (ID: {group.group_id}, 股票数量: {len(group.items)})")


def list_stocks(ths: THSUserFavorite, group_name: str):
    """列出指定分组中的所有股票"""
    groups = ths.get_all_groups()
    
    if group_name not in groups:
        print(f"未找到名为 '{group_name}' 的分组")
        return
    
    group = groups[group_name]
    print(f"分组 '{group_name}' (ID: {group.group_id}) 包含 {len(group.items)} 个股票:")
    
    for item in group.items:
        print(f"- {item.code}.{item.market}")


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
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()

import argparse
import unittest
from unittest.mock import Mock, patch

import main
from config import SELF_STOCK_DEFAULT_NAME, SELF_STOCK_GROUP_ID
from exceptions import THSAPIError
from main import (
    apply_global_defaults,
    build_parser,
    handle_group_command,
    handle_stock_command,
    list_groups,
    list_stocks,
)
from models import StockGroup


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_global_defaults(args)
    return args


class SelfstockCliTest(unittest.TestCase):
    def setUp(self):
        main._TABULATE_MODULE = None

    def test_self_list_command_is_supported(self):
        args = parse_args(["self", "list"])

        self.assertEqual(args.command, "self")
        self.assertEqual(args.self_command, "list")

    def test_stock_add_accepts_selfstock_name(self):
        manager = Mock()
        args = argparse.Namespace(stock_command="add", group="我的自选", stock="600519.SH")

        handle_stock_command(manager, args)

        manager.add_item_to_group.assert_called_once_with("我的自选", "600519.SH")

    def test_group_and_stock_commands_print_plain_text_messages(self):
        manager = Mock()
        manager.share_group.return_value = {"share_url": "https://example.com/share"}

        with patch("main.print") as mock_print:
            handle_group_command(manager, argparse.Namespace(group_command="add", name="消费"))
            handle_group_command(manager, argparse.Namespace(group_command="del", group="消费"))
            handle_group_command(
                manager,
                argparse.Namespace(group_command="share", group="消费", valid_time=3600),
            )
            handle_stock_command(
                manager,
                argparse.Namespace(stock_command="add", group="消费", stock="600519.SH"),
            )
            handle_stock_command(
                manager,
                argparse.Namespace(stock_command="del", group="消费", stock="600519.SH"),
            )

        self.assertEqual(mock_print.call_args_list[0].args[0], "已成功创建分组 '消费'")
        self.assertEqual(mock_print.call_args_list[1].args[0], "已删除分组 '消费'")
        self.assertEqual(mock_print.call_args_list[2].args[0], "分享链接: https://example.com/share")
        self.assertEqual(mock_print.call_args_list[3].args[0], "已将 600519.SH 添加到分组 '消费'")
        self.assertEqual(mock_print.call_args_list[4].args[0], "已从分组 '消费' 删除 600519.SH")

    def test_default_list_includes_selfstock_group(self):
        manager = Mock()
        manager.get_all_groups.return_value = {}

        with patch("main.print"):
            list_groups(manager)

        manager.get_all_groups.assert_called_once_with(include_self_stocks=True)

    def test_list_groups_renders_aligned_table_with_chinese_content(self):
        manager = Mock()
        manager.get_all_groups.return_value = {
            "我的自选": StockGroup(name="我的自选", group_id="__selfstock__", items=[object()] * 10),
            "消费": StockGroup(name="消费", group_id="g1", items=[object()] * 3),
        }

        with patch("main.print") as mock_print:
            list_groups(manager)

        self.assertEqual(mock_print.call_args_list[0].args[0], "共有 2 个分组:")
        self.assertEqual(
            mock_print.call_args_list[1].args[0],
            "| 分组名称   | 分组ID        |   股票数量 |\n"
            "|------------|---------------|------------|\n"
            "| 我的自选   | __selfstock__ |         10 |\n"
            "| 消费       | g1            |          3 |",
        )

    def test_list_group_selfstock_uses_get_self_stocks(self):
        manager = Mock()
        manager.get_self_stocks.return_value = StockGroup(
            name=SELF_STOCK_DEFAULT_NAME,
            group_id=SELF_STOCK_GROUP_ID,
            items=[],
        )

        with patch("main.print"):
            list_stocks(manager, SELF_STOCK_DEFAULT_NAME)

        manager.get_self_stocks.assert_called_once_with(name=SELF_STOCK_DEFAULT_NAME)
        manager.get_all_groups.assert_not_called()

    @patch("main.importlib.import_module", side_effect=ImportError("missing tabulate"))
    def test_list_groups_raises_friendly_error_when_cli_dependency_is_missing(self, _mock_import):
        manager = Mock()
        manager.get_all_groups.return_value = {
            "消费": StockGroup(name="消费", group_id="g1", items=[object()] * 1),
        }

        with self.assertRaisesRegex(THSAPIError, "ths-favorite\\[cli\\]"):
            list_groups(manager)


if __name__ == "__main__":
    unittest.main()

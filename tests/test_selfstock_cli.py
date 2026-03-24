import argparse
import unittest
from unittest.mock import Mock, patch

from config import SELF_STOCK_DEFAULT_NAME, SELF_STOCK_GROUP_ID
from main import (
    apply_global_defaults,
    build_parser,
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
    def test_self_list_command_is_supported(self):
        args = parse_args(["self", "list"])

        self.assertEqual(args.command, "self")
        self.assertEqual(args.self_command, "list")

    def test_stock_add_accepts_selfstock_name(self):
        manager = Mock()
        args = argparse.Namespace(stock_command="add", group="我的自选", stock="600519.SH")

        handle_stock_command(manager, args)

        manager.add_item_to_group.assert_called_once_with("我的自选", "600519.SH")

    def test_default_list_includes_selfstock_group(self):
        manager = Mock()
        manager.get_all_groups.return_value = {}

        with patch("main.print"):
            list_groups(manager)

        manager.get_all_groups.assert_called_once_with(include_self_stocks=True)

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


if __name__ == "__main__":
    unittest.main()

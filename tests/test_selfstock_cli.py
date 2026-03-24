import argparse
import unittest
from unittest.mock import Mock

from main import (
    apply_global_defaults,
    build_parser,
    handle_stock_command,
)


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


if __name__ == "__main__":
    unittest.main()

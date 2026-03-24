import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from config import SELF_STOCK_DEFAULT_NAME, SELF_STOCK_GROUP_ID
from exceptions import THSNetworkError
from models import StockGroup
from service import PortfolioManager


class SelfstockServiceTest(unittest.TestCase):
    def build_manager(self) -> PortfolioManager:
        tmpdir = Path(tempfile.mkdtemp())
        manager = PortfolioManager(
            cookie_cache_path=str(tmpdir / "cookies.json"),
        )
        manager._group_cache_path = str(tmpdir / "groups.json")
        manager._self_stock_cache_path = str(tmpdir / "selfstock.json")
        manager._groups_cache = {}
        manager._self_stock_cache = None
        return manager

    def test_get_self_stocks_returns_virtual_group_without_plaintext_credentials(self):
        manager = self.build_manager()
        manager._api.download_self_stocks = Mock(
            return_value=(
                {
                    "errorCode": 0,
                    "errorMsg": "",
                    "result": [
                        {"code": "300830", "marketid": "33"},
                        {"code": "600366", "marketid": "17"},
                    ],
                    "isT": True,
                },
                [("300830", "33"), ("600366", "17")],
            )
        )
        manager.refresh_selfstock_detail = Mock(return_value=None)

        group = manager.get_self_stocks()

        self.assertIsInstance(group, StockGroup)
        self.assertEqual(group.group_id, SELF_STOCK_GROUP_ID)
        self.assertEqual(group.name, SELF_STOCK_DEFAULT_NAME)
        self.assertEqual(len(group.items), 2)

    def test_get_all_groups_can_include_self_stocks(self):
        manager = self.build_manager()
        manager._api.query_groups = Mock(return_value={"version": 1, "group_list": []})
        manager.refresh_selfstock_detail = Mock(return_value=None)
        manager._api.download_self_stocks = Mock(
            return_value=(
                {
                    "errorCode": 0,
                    "errorMsg": "",
                    "result": [{"code": "300830", "marketid": "33"}],
                    "isT": True,
                },
                [("300830", "33")],
            )
        )

        groups = manager.get_all_groups(include_self_stocks=True, self_stocks_name="默认自选")

        self.assertIn("默认自选", groups)
        self.assertEqual(groups["默认自选"].group_id, SELF_STOCK_GROUP_ID)

    def test_add_item_to_group_routes_virtual_selfstock_to_upload(self):
        manager = self.build_manager()
        manager.get_self_stocks = Mock(
            return_value=StockGroup(name=SELF_STOCK_DEFAULT_NAME, group_id=SELF_STOCK_GROUP_ID, items=[])
        )
        manager._api.upload_self_stocks = Mock(
            return_value={"errorCode": 0, "errorMsg": "修改成功", "result": {}, "isT": True}
        )

        manager.add_item_to_group(SELF_STOCK_GROUP_ID, "600519.SH")

        manager._api.upload_self_stocks.assert_called_once_with(op="add", stockcode="600519_17")

    def test_delete_item_to_group_routes_selfstock_name_to_upload(self):
        manager = self.build_manager()
        manager.get_self_stocks = Mock(
            return_value=StockGroup(
                name=SELF_STOCK_DEFAULT_NAME,
                group_id=SELF_STOCK_GROUP_ID,
                items=[],
            )
        )
        manager._api.upload_self_stocks = Mock(
            return_value={"errorCode": 0, "errorMsg": "修改成功", "result": {}, "isT": True}
        )

        manager.delete_item_from_group(SELF_STOCK_DEFAULT_NAME, "600519.SH")

        manager._api.upload_self_stocks.assert_called_once_with(op="del", stockcode="600519_17")

    def test_get_all_groups_still_returns_groups_when_selfstock_detail_refresh_fails(self):
        manager = self.build_manager()
        manager._api.query_groups = Mock(
            return_value={
                "version": 1,
                "group_list": [
                    {
                        "id": "0_1",
                        "name": "消费",
                        "content": "600519,17",
                    }
                ],
            }
        )
        manager.refresh_selfstock_detail = Mock(side_effect=THSNetworkError("selfstock_detail", "boom"))

        groups = manager.get_all_groups()

        self.assertIn("消费", groups)
        self.assertEqual(groups["消费"].items[0].code, "600519")

    def test_get_self_stocks_still_returns_items_when_selfstock_detail_refresh_fails(self):
        manager = self.build_manager()
        manager._api.download_self_stocks = Mock(
            return_value=(
                {
                    "errorCode": 0,
                    "errorMsg": "",
                    "result": [{"code": "300830", "marketid": "33"}],
                    "isT": True,
                },
                [("300830", "33")],
            )
        )
        manager.refresh_selfstock_detail = Mock(side_effect=THSNetworkError("selfstock_detail", "boom"))

        group = manager.get_self_stocks(refresh=True)

        self.assertEqual([item.code for item in group.items], ["300830"])
        manager.refresh_selfstock_detail.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()

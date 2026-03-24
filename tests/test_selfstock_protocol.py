import unittest
from unittest.mock import Mock, patch

import requests

from api import download_self_stocks, modify_self_stock_v2, upload_self_stocks
from exceptions import THSAPIError, THSNetworkError


class SelfstockProtocolTest(unittest.TestCase):
    @patch("api.requests.get")
    def test_download_self_stocks_parses_result_items(self, mock_get):
        mock_get.return_value = Mock(
            json=Mock(
                return_value={
                    "errorCode": 0,
                    "errorMsg": "",
                    "result": [{"code": "600366", "marketid": "17"}],
                    "isT": True,
                }
            ),
            raise_for_status=Mock(),
        )

        meta, items = download_self_stocks({"userid": "1"})

        self.assertEqual(meta["errorCode"], 0)
        self.assertEqual(items, [("600366", "17")])

    @patch("api.requests.get")
    def test_modify_self_stock_v2_add_uses_stockcode_query(self, mock_get):
        mock_get.return_value = Mock(
            json=Mock(return_value={"errorCode": 0, "errorMsg": "修改成功", "result": {}, "isT": True}),
            raise_for_status=Mock(),
        )

        modify_self_stock_v2({"userid": "1"}, op="add", stockcode="300830_33")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["op"], "add")
        self.assertEqual(kwargs["params"]["stockcode"], "300830_33")

    @patch("api.requests.get")
    def test_modify_self_stock_v2_del_uses_stockcode_query(self, mock_get):
        mock_get.return_value = Mock(
            json=Mock(return_value={"errorCode": 0, "errorMsg": "修改成功", "result": {}, "isT": True}),
            raise_for_status=Mock(),
        )

        modify_self_stock_v2({"userid": "1"}, op="del", stockcode="300830_33")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["op"], "del")
        self.assertEqual(kwargs["params"]["stockcode"], "300830_33")

    @patch("api.requests.get")
    def test_download_self_stocks_raises_api_error_on_nonzero_error_code(self, mock_get):
        mock_get.return_value = Mock(
            json=Mock(return_value={"errorCode": 1001, "errorMsg": "失败", "result": [], "isT": True}),
            raise_for_status=Mock(),
        )

        with self.assertRaises(THSAPIError):
            download_self_stocks({"userid": "1"})

    @patch("api.requests.get", side_effect=requests.RequestException("boom"))
    def test_modify_self_stock_v2_raises_network_error(self, _mock_get):
        with self.assertRaises(THSNetworkError):
            modify_self_stock_v2({"userid": "1"}, op="del", stockcode="300830_33")

    def test_upload_self_stocks_no_longer_accepts_legacy_plaintext_protocol_arguments(self):
        with self.assertRaises(TypeError):
            upload_self_stocks(
                {"userid": "1"},
                account="user",
                password="secret",
                items=[("600366", "17")],
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from exceptions import THSAPIError

from api import (
    _decode_hexin_special_base64_ex,
    _decode_self_stock_response_text,
    _encode_self_stock_request_payload,
    _parse_self_stock_items,
)


GET_SAMPLE = (
    "BE1zMEGK8z8zMvVLCw1lZlOlLCmmtMnUACHYkcHG+rXG1QfqACj8ASGmcmVNYOQwZfNk8z0zCEZfMEQnalNldsoFdlPJ0nok"
    "dlYOTsokdsoLdXkOdsoO0nPJ0fKFdsokTsYkdfGO0jk1dfKF2sPJdlokdsI5Tsokdsol0vkkdsoO0f4J0fGkdlokTsdkds3i"
    "2vkldsoN0lqJ0nok0fKNTsokdnG10jk12swkdnPJ0fGldsokTsYkdfU52vkOdsGO0nzJ0fKFdlKkTsokdswOd9kkdsUk0szJ"
    "0fGOdsGkTsokdsYF0XkkdsoNdfMJdsok2sU5Tsdkds3ld9iU6lULdnhJ0nol0nwOTsYkdlYidvkldsGldlPJdlokdlc9Tsdk"
    "dsdFdvkOdsoidnZJdsoLdfoNTsokdndFdvki0fwF0lPJdlok2fYFTsdkdscl0XkkdsUL0l0JdsoLdndLTsokdnI109ki0fw5"
    "dnhJ0no1dnwOTsYkdfKF2vkOdso90n0J0nok0nYOTsYkdsG9dXkkdsUO2s4JdsoLdn3iTsIkdfo52XkOdsd9dfZJ0nokdlo5"
    "TsYkdsd52vkkdsUN0fZJdsoL0fI1TsYkdsckdjk1dfY92sPJdsoidnwFTsYkdfUL0jkkdsU12fqJdsok0lI5TsYkdfwld9kO"
    "dsd9df4J0nok0nwkTsokdfUi2Xk10nGidsPJdfI50ldLTsokdn390XkldsoL0lqJdsoL0nokTsdkdsILdvk1dfc1dnPJ0fGl"
    "dlGkTsIi0fcidvk1dfd90fPJdfI50foiTsYkds3idvki0fwO0f8J0nok2sKFTsokdnI12vk1dfd50lPJ2sKidfUNTsdkdsoF"
    "0Xki0fwF2sPJ0fGL0sokTsYkdfGl2vk1dfdidlPJdsoLdsY1TsYkdsK12vkOdsdF2szJ0noldsYFTsokdsoOd9kldsGi2fzJ"
    "dsoLdndkTsIF2foidvki0fwF0nzJdfI50l3kTsokdnd1dXki0fw10lPJ0fKF0lYkTsokdn3L2vkOdsd1dl0J0fGldswkTsok"
    "dsoO0jkkdsUFdf4JdfI50fdkTsG12fUk2Xk1dfdkdlPJdfI52fo1TsYkdswkdvk1dno10fPJ0fGL2swkTsIidlGkdvkkdsU9"
    "dfqJ0fKFdfckTsKldsokdvkOdsdOdsVJ0fGk2sKkTsG12fd52XkOdsdi2f0JdsoLdl3kTsG12fYFdXki0fw50nMJ0no1dlok"
    "Tsdkdsold9kkdsUk0fPJdlok0sI5TsIidfo5dvki0fwFdfzJdlok2foFTsokdsIl2vk10nU10lPJ0nok2s31TsYkdsIF2vkO"
    "dsdkdfzJ0nol0fIFTsYkdfK52XkkdsUL0n4JdsoL0sI5TsYkdsG909kldsGOdsZJdfI52sdNTsKF0noidjkkdso9dnVJdsok"
    "2fdFTsokdn3i0Xk1dfo9dnPJ2sKOdsY5TsYkdsYidXkkdsU12s0Jdsok2swFTsKFdfGld9kOdsoldsPJ2sKidfc1TsKFdfGN"
    "0vk10noldsPJ2sKidnc5TsKFdfU90jkOdsoFdlzJdfI5dlokTsG12fwi0Xk12sK5dlPJ0fKFdsYkTsYkdsGk2XkF2sI1dfMJ"
    "2sKOdsclTsG12fdL09kF2sGL0l0J2sKidfI9TsILdsckdvk10nol0nPJ0fGkdsIkTsIidnY5dvk12sKk2sPJ0fYL2fUkTsKF"
    "dfGldvk12sKN0nPJ0fGldfKkTsG12fKF09k12sKLdnPJdfI52fK1Tbkld9ki09kld9ki09kLdvki09kLdvkld9kld9kld9kL"
    "dvkld9kld9ki09kld9kLdvkLdvki09ki09kLdvkld9kld9kLdvkld9kld9kld9kld9ki0lMJdfMJdfMJdl0Jdl0Jdl0JdfMJ"
    "dl0Jdl0JdlZJdl0Jdl0Jdl0Jdl0Jdl0JdlZJdfMJdfMJdfMJdfMJdfMJdl0Jdl0JdnPJdfMJdfMJdfMJdl0Jdl0JdfMJdnPJ"
    "dl0JdfMJdl0Jdl0JdfMJdfMJdfMJdl0JdnPJdlZJdl0Jdl0Jdl0Jdl0JdnPJdnPJdnPJdnPJdlZJdfMJdlZJdfMJdl0JdnPJ"
    "0shJdl0JdlZJdnPJdfMJdnPJdl0JdfMJdfMJdfMJdl0Jdl0Jdl0JdnPJdlZJdlZJdl0JdlZJdnPJdl0JdfMJdnPJdl0Jdl0J"
    "dlZJdlZJdnPJdlZJdfMJdnPJdnPJdnPJdl0JdnPJVV8f6Xki09kLdvkl0jki09kld9kl0jkl0jki09kld9kld9kld9kLdvk"
    "l0jkld9kld9kLdvki09ki09ki09ki09ki09kld9kld9ki09kld9kl0jkN2vkld9kld9kld9kLdvkN2vki09kld9kld9kN2vk"
    "i09kN2vkN2vkLdvkN2vkN2vki09kl0jkl0jkLdvkLdvki09kN2vkN2vkl0jkN2vkN2vkLdvkLdvkLdvkLdvkLdvkLdvkN2vk"
    "LdvkLdvkl0jkLdvkl0jkmCjVtBfGFdxZWZX8laWQuBfcl0LZ6MEztZfNLdsUOdsdLdlUidnIN03=="
)


class SelfstockProtocolTest(unittest.TestCase):
    def test_decode_hexin_special_base64_ex_returns_gbk_payload_bytes(self):
        data = _decode_hexin_special_base64_ex(GET_SAMPLE)

        self.assertTrue(data.startswith(b"<meta &ReturnMsg="))

    def test_decode_self_stock_response_text_extracts_meta_fields(self):
        decoded = _decode_self_stock_response_text(GET_SAMPLE)

        self.assertEqual(decoded["retcode"], "0")
        self.assertEqual(decoded["num"], "182")
        self.assertEqual(decoded["Version"], "737")
        self.assertEqual(decoded["Rtime"], "20260323212545")

    def test_parse_self_stock_items_splits_codes_and_market_ids(self):
        decoded = _decode_self_stock_response_text(GET_SAMPLE)

        items = _parse_self_stock_items(decoded["SelfStock"], int(decoded["num"]))

        self.assertEqual(items[0], ("300830", "33"))
        self.assertEqual(items[27], ("HK2228", "177"))
        self.assertEqual(len(items), 182)

    def test_encode_self_stock_request_payload_matches_expected_shape(self):
        payload = _encode_self_stock_request_payload(
            account="sunnysab",
            password="@sab098.ths",
            marketcode="1",
            do="get",
            expand="1",
            selfcode_crc=" ",
        )

        self.assertIsInstance(payload, str)
        self.assertTrue(payload)

    def test_parse_self_stock_items_raises_when_num_mismatches_payload(self):
        with self.assertRaises(THSAPIError):
            _parse_self_stock_items("600519|000001|,17|33|", 3)


if __name__ == "__main__":
    unittest.main()

"""Tests for pure functions — no mocking, no I/O, just inputs → outputs."""
import base64
import json

from api import _decode_detail_blob, _merge_entries
from exceptions import THSAPIError
from models import StockEntry

# ── _merge_entries ──────────────────────────────────────────────────


class TestMergeEntries:
    def test_add_empty_list_returns_current(self):
        current = [StockEntry('600519', '17'), StockEntry('000001', '33')]
        result = _merge_entries(current, [], 'add')
        assert result == current

    def test_add_new_entries(self):
        current = [StockEntry('600519', '17')]
        new = [StockEntry('000001', '33')]
        result = _merge_entries(current, new, 'add')
        assert len(result) == 2
        assert StockEntry('000001', '33') in result

    def test_add_duplicate_overwrites_by_code(self):
        current = [StockEntry('600519', '17')]
        new = [StockEntry('600519', '33')]
        result = _merge_entries(current, new, 'add')
        assert len(result) == 1
        assert result[0].code == '600519'

    def test_delete_removes_matching(self):
        current = [StockEntry('600519', '17'), StockEntry('000001', '33')]
        to_delete = [StockEntry('600519', '17')]
        result = _merge_entries(current, to_delete, 'delete')
        assert len(result) == 1
        assert result[0].code == '000001'

    def test_delete_non_existent_returns_current(self):
        current = [StockEntry('600519', '17')]
        to_delete = [StockEntry('999999', '17')]
        result = _merge_entries(current, to_delete, 'delete')
        assert result == current

    def test_unknown_action_raises(self):
        current = [StockEntry('600519', '17')]
        try:
            _merge_entries(current, [], 'invalid_action')
            assert False, 'expected THSAPIError'
        except THSAPIError:
            pass


# ── _decode_detail_blob ─────────────────────────────────────────────


class TestDecodeDetailBlob:
    def test_empty_string_returns_empty_list(self):
        assert _decode_detail_blob('') == []

    def test_whitespace_only_returns_empty_list(self):
        encoded = base64.b64encode(b'   ').decode('ascii')
        assert _decode_detail_blob(encoded) == []

    def test_valid_blob_parses_correctly(self):
        data = [{'C': '600519', 'M': '17', 'P': '123.45'}]
        encoded = base64.b64encode(json.dumps(data).encode()).decode('ascii')
        assert _decode_detail_blob(encoded) == data


# ── _parse_symbol ───────────────────────────────────────────────────


class TestParseSymbol:
    def test_sh_stock_returns_stock_entry(self):
        from service import PortfolioManager
        result = PortfolioManager._parse_symbol('600519.SH')
        assert isinstance(result, StockEntry)
        assert result.code == '600519'
        assert result.market_type == '17'

    def test_sz_stock_returns_stock_entry(self):
        from service import PortfolioManager
        result = PortfolioManager._parse_symbol('000001.SZ')
        assert result.code == '000001'
        assert result.market_type == '33'

    def test_missing_dot_raises(self):
        from service import PortfolioManager
        try:
            PortfolioManager._parse_symbol('600519')
            assert False, 'expected THSAPIError'
        except THSAPIError:
            pass

    def test_unknown_market_suffix_passes_through(self):
        from service import PortfolioManager
        result = PortfolioManager._parse_symbol('600519.XX')
        assert result.code == '600519'
        assert result.market_type == 'XX'

    def test_lowercase_market_is_normalized(self):
        from service import PortfolioManager
        result = PortfolioManager._parse_symbol('600519.sh')
        assert result.market_type == '17'


# ── _is_version_conflict_error ──────────────────────────────────────


class TestIsVersionConflictError:
    def _error(self, message: str, code: str | None = None) -> THSAPIError:
        return THSAPIError('test', message, code)

    def test_english_outdated_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('version outdated')
        )

    def test_english_expired_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('version expired')
        )

    def test_english_stale_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('version stale')
        )

    def test_english_conflict_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('version conflict')
        )

    def test_chinese_guoqi_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('版本过期')
        )

    def test_chinese_banbenchongtu_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('版本冲突')
        )

    def test_unrelated_error_returns_false(self):
        from service import PortfolioManager
        assert not PortfolioManager._is_version_conflict_error(
            self._error('network timeout')
        )

    def test_code_409_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('conflict', '409')
        )

    def test_code_version_conflict_returns_true(self):
        from service import PortfolioManager
        assert PortfolioManager._is_version_conflict_error(
            self._error('conflict', 'version_conflict')
        )

    def test_error_no_message_no_code_returns_false(self):
        from service import PortfolioManager
        assert not PortfolioManager._is_version_conflict_error(
            self._error('')
        )

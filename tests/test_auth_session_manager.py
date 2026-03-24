import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from auth import SessionManager, SessionResult
from storage import load_cookie_cache_data


class SessionManagerCacheStrategyTest(unittest.TestCase):
    def write_cache(self, cache_path: Path, payload):
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_auto_mode_prefers_latest_credentials_cache_without_loading_browser(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cookies.json"
            now = time.time()
            self.write_cache(
                cache_path,
                {
                    "credentials::older": {
                        "timestamp": now - 20,
                        "cookies": {"sessionid": "old"},
                    },
                    "credentials::newer": {
                        "timestamp": now - 10,
                        "cookies": {"sessionid": "new"},
                    },
                    "browser::firefox": {
                        "timestamp": now - 5,
                        "cookies": {"sessionid": "browser"},
                    },
                },
            )

            manager = SessionManager(
                auth_method="auto",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
            )
            manager._load_from_browser = Mock(side_effect=AssertionError("browser loader should not run"))

            resolved = manager.resolve()

            self.assertEqual(resolved, {"sessionid": "new"})

    def test_auto_mode_falls_back_to_browser_when_no_credentials_cache_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cookies.json"
            browser_loader = Mock(return_value={"sessionid": "browser-live"})

            manager = SessionManager(
                auth_method="auto",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
            )
            manager._load_from_browser = browser_loader

            resolved = manager.resolve()

            self.assertEqual(resolved, {"sessionid": "browser-live"})
            browser_loader.assert_called_once_with("firefox")

    def test_credentials_mode_ignores_other_accounts_cache_and_uses_requested_account(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cookies.json"
            now = time.time()
            self.write_cache(
                cache_path,
                {
                    "credentials::someone-else": {
                        "timestamp": now - 10,
                        "cookies": {"sessionid": "other-user"},
                    }
                },
            )
            login_factory = Mock(
                return_value=SessionResult(
                    userid="1",
                    sessionid="session",
                    signvalid="sign",
                    cookies={"sessionid": "target-user"},
                )
            )

            manager = SessionManager(
                auth_method="credentials",
                username="target",
                password="secret",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
                login_factory=login_factory,
            )

            resolved = manager.resolve()

            self.assertEqual(resolved, {"sessionid": "target-user"})
            login_factory.assert_called_once_with("target", "secret")

    def test_credentials_mode_persists_plain_password_in_cache_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cookies.json"
            login_factory = Mock(
                return_value=SessionResult(
                    userid="1",
                    sessionid="session",
                    signvalid="sign",
                    cookies={"sessionid": "target-user"},
                )
            )

            manager = SessionManager(
                auth_method="credentials",
                username="target",
                password="secret",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
                login_factory=login_factory,
            )

            manager.resolve()

            cache_data = load_cookie_cache_data(str(cache_path))
            entry = next(iter(cache_data.values()))
            self.assertEqual(entry.get("password"), "secret")


if __name__ == "__main__":
    unittest.main()

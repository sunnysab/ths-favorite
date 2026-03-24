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

    def test_removed_auth_method_kwarg_is_rejected(self):
        with self.assertRaises(TypeError):
            SessionManager(auth_method="browser")

    def test_username_only_reads_matching_cached_cookies(self):
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
                },
            )

            target_key = SessionManager._credentials_cache_key("target")
            cache_data = load_cookie_cache_data(str(cache_path))
            cache_data[target_key] = cache_data.pop("credentials::newer")
            self.write_cache(cache_path, cache_data)

            manager = SessionManager(
                username="target",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
            )

            resolved = manager.resolve()

            self.assertEqual(resolved, {"sessionid": "new"})

    def test_username_and_password_ignore_other_accounts_cache_and_use_requested_account(self):
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
                username="target",
                password="secret",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
                login_factory=login_factory,
            )

            resolved = manager.resolve()

            self.assertEqual(resolved, {"sessionid": "target-user"})
            login_factory.assert_called_once_with("target", "secret")

    def test_username_and_password_do_not_persist_plain_password_in_cache_entry(self):
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
                username="target",
                password="secret",
                cookie_cache_path=str(cache_path),
                cookie_cache_ttl_seconds=10_000,
                login_factory=login_factory,
            )

            manager.resolve()

            cache_data = load_cookie_cache_data(str(cache_path))
            entry = next(iter(cache_data.values()))
            self.assertNotIn("password", entry)


if __name__ == "__main__":
    unittest.main()

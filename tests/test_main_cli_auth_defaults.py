import unittest

from main import apply_global_defaults, build_parser


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_global_defaults(args)
    return args


class MainCliAuthDefaultsTest(unittest.TestCase):
    def test_defaults_to_none_auth_when_no_auth_flags_are_provided(self):
        args = parse_args(["list"])

        self.assertEqual(args.auth_method, "none")

    def test_infers_credentials_auth_when_username_and_password_are_provided_after_subcommand(self):
        args = parse_args(["list", "--username", "user", "--password", "secret"])

        self.assertEqual(args.auth_method, "credentials")

    def test_infers_credentials_auth_when_only_username_is_provided(self):
        args = parse_args(["list", "--username", "user"])

        self.assertEqual(args.auth_method, "credentials")

    def test_rejects_browser_auth_method(self):
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["--auth-method", "browser", "list"])

    def test_rejects_browser_flag(self):
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["list", "--browser", "chrome"])


if __name__ == "__main__":
    unittest.main()

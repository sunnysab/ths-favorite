import unittest

from main import apply_global_defaults, build_parser


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_global_defaults(args)
    return args


class MainCliAuthDefaultsTest(unittest.TestCase):
    def test_defaults_to_auto_auth_when_no_auth_flags_are_provided(self):
        args = parse_args(["list"])

        self.assertEqual(args.auth_method, "auto")

    def test_infers_credentials_auth_when_username_and_password_are_provided_after_subcommand(self):
        args = parse_args(["list", "--username", "user", "--password", "secret"])

        self.assertEqual(args.auth_method, "credentials")

    def test_infers_credentials_auth_when_only_username_is_provided(self):
        args = parse_args(["list", "--username", "user"])

        self.assertEqual(args.auth_method, "credentials")

    def test_keeps_explicit_browser_auth_when_requested(self):
        args = parse_args(
            ["--auth-method", "browser", "list", "--username", "user", "--password", "secret"]
        )

        self.assertEqual(args.auth_method, "browser")

    def test_infers_browser_auth_when_browser_flag_is_provided(self):
        args = parse_args(["list", "--browser", "chrome"])

        self.assertEqual(args.auth_method, "browser")


if __name__ == "__main__":
    unittest.main()

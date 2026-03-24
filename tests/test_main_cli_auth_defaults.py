import unittest

from main import apply_global_defaults, build_parser


def parse_args(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_global_defaults(args)
    return args


class MainCliAuthDefaultsTest(unittest.TestCase):
    def test_defaults_do_not_add_auth_method_when_no_auth_flags_are_provided(self):
        args = parse_args(["list"])

        self.assertFalse(hasattr(args, "auth_method"))

    def test_preserves_credentials_args_when_username_and_password_are_provided_after_subcommand(self):
        args = parse_args(["list", "--username", "user", "--password", "secret"])

        self.assertEqual(args.username, "user")
        self.assertEqual(args.password, "secret")
        self.assertFalse(hasattr(args, "auth_method"))

    def test_preserves_username_when_only_username_is_provided(self):
        args = parse_args(["list", "--username", "user"])

        self.assertEqual(args.username, "user")
        self.assertIsNone(args.password)
        self.assertFalse(hasattr(args, "auth_method"))

    def test_rejects_auth_method_flag(self):
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["--auth-method", "credentials", "list"])

    def test_rejects_browser_flag(self):
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["list", "--browser", "chrome"])


if __name__ == "__main__":
    unittest.main()

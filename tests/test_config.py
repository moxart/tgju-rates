import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from tgju_rates.cli import build_parser, parse_args
from tgju_rates.config import config_defaults, read_config


class ConfigTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "config.ini"

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")
        return str(self.path)

    def test_missing_file_sets_nothing(self):
        self.assertEqual(read_config(self.path), {})

    def test_values_become_defaults_that_the_command_line_overrides(self):
        path = self.write(
            "[defaults]\ntoman = yes\ninterval = 30\nwatch = usd,eur\nmarket = coin,gold\nalert = usd>2,700,000\n"
            "        eur<3,000,000\n"
        )
        args = parse_args(build_parser(), ["--config", path])
        self.assertTrue(args.toman)
        self.assertEqual(args.interval, 30)
        self.assertEqual(args.watch, "usd,eur")
        self.assertEqual(args.market, ["coin", "gold"])
        self.assertEqual(args.alert, ["usd>2,700,000", "eur<3,000,000"])

        args = parse_args(build_parser(), ["--config", path, "--no-toman", "-i", "5", "--alert", "gbp>1"])
        self.assertFalse(args.toman)
        self.assertEqual(args.interval, 5)
        self.assertEqual(args.alert, ["usd>2,700,000", "eur<3,000,000", "gbp>1"])

    def test_bad_values_are_reported_with_the_option(self):
        for text, message in (
            ("[defaults]\ntoman = maybe\n", "toman: expected yes or no"),
            ("[defaults]\ninterval = fast\n", "interval: expected a number, not 'fast'"),
            ("[defaults]\nanimation = spin\n", "animation: 'spin' is not one of"),
            ("[defaults]\nalert = usd=5\n", "alert:"),
            ("[defaults]\nhistory = usd\n", "unknown option 'history'"),
            ("[colors]\nx = 1\n", "unknown section [colors]"),
            ("toman = yes\n", "File contains no section headers"),
        ):
            with self.subTest(text=text), redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
                parse_args(build_parser(), ["--config", self.write(text)])
            self.assertIn(message, stderr.getvalue())

    def test_named_file_must_exist(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            parse_args(build_parser(), ["--config", str(self.path)])
        self.assertIn("settings file not found", stderr.getvalue())

    def test_no_record_flag(self):
        self.assertEqual(config_defaults(build_parser(), {"no-record": "true"}), {"no_record": True})


if __name__ == "__main__":
    unittest.main()

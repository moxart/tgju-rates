import shutil
import subprocess
import unittest

from tgju_rates.cli import build_parser
from tgju_rates.completion import completion_script


class CompletionTest(unittest.TestCase):
    def test_bash_script_has_options_and_codes(self):
        script = completion_script("bash", build_parser())
        self.assertIn("complete -F _tgju_rates tgju-rates", script)
        self.assertIn("--convert", script)
        self.assertIn(" emami ", script)
        self.assertIn("currency coin gold crypto all", script)

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_bash_completes_comma_lists(self):
        script = completion_script("bash", build_parser())
        probe = 'COMP_WORDS=(tgju-rates --watch usd,em); COMP_CWORD=2; _tgju_rates; echo "${COMPREPLY[*]}"'
        result = subprocess.run(["bash", "-c", script + probe], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "usd,emami")

    def test_zsh_loads_bashcompinit(self):
        self.assertIn("bashcompinit", completion_script("zsh", build_parser()))

    def test_fish_lines(self):
        script = completion_script("fish", build_parser())
        self.assertIn("complete -c tgju-rates -l db", script)
        self.assertIn("-r -F", script)
        self.assertIn("-l watch", script)
        self.assertIn(
            "-l watch -d 'comma-separated codes to show, in this order' -x -a '(__tgju_rates_list ada ", script
        )
        self.assertIn("emami=", script)


if __name__ == "__main__":
    unittest.main()

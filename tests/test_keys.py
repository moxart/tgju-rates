import os
import unittest

from tgju_rates.keys import KeyReader, split_keys


class SplitKeysTest(unittest.TestCase):
    def test_plain_keys_split_per_character(self):
        self.assertEqual(split_keys("ts"), ["t", "s"])

    def test_escape_sequence_stays_whole(self):
        self.assertEqual(split_keys("\x1b[A"), ["\x1b[A"])

    def test_held_arrow_gives_one_key_per_press(self):
        self.assertEqual(split_keys("\x1b[B\x1b[B\x1bOA"), ["\x1b[B", "\x1b[B", "\x1bOA"])

    def test_unknown_escape_text_stays_whole(self):
        self.assertEqual(split_keys("\x1bxy"), ["\x1bxy"])

    def test_lone_escape(self):
        self.assertEqual(split_keys("\x1b"), ["\x1b"])


@unittest.skipIf(os.name == "nt", "uses a pipe and select()")
class KeyReaderTest(unittest.TestCase):
    def test_reads_from_a_pipe_without_a_terminal(self):
        read_end, write_end = os.pipe()
        with os.fdopen(read_end) as stream, os.fdopen(write_end, "w") as writer:
            reader = KeyReader(stream)  # not entered: a pipe has no terminal modes to change
            self.assertEqual(reader.read(0), [])
            writer.write("q")
            writer.flush()
            self.assertEqual(reader.read(1), ["q"])


if __name__ == "__main__":
    unittest.main()

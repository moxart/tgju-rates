"""The settings file: defaults for command-line options, so they don't have to be typed on every run.

It's an INI file with a ``[defaults]`` section, one option per line, named like the long option
without its dashes::

    [defaults]
    toman = yes
    watch = usd,eur,emami,btc
    alert = usd>2,700,000
            total>5,000,000,000

Options given on the command line win over the file. Repeatable options (``alert``) take one value per
line, and command-line values are added to the file's.
"""

import argparse
import configparser
import os
from pathlib import Path

SECTION = "defaults"
# The options the file may set. Actions such as --history or --convert stay command-line only.
CONFIG_OPTIONS = (
    "interval",
    "toman",
    "jalali",
    "persian",
    "dashboard",
    "animation",
    "market",
    "watch",
    "alert",
    "color",
    "days",
    "db",
    "holdings",
    "no-record",
    "host",
    "port",
)


def default_config_path():
    config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_home) / "tgju-rates" / "config.ini"


def read_config(path):
    """The file's ``[defaults]`` as {option: text}; {} when the file doesn't exist.

    Raises ValueError for a file that can't be parsed or names an option it can't set.
    """
    parser = configparser.ConfigParser(interpolation=None, default_section="__none__")
    try:
        with open(path, encoding="utf-8") as file:
            parser.read_file(file)
    except FileNotFoundError:
        return {}
    except configparser.Error as error:
        raise ValueError(error.message) from None
    unknown_sections = [name for name in parser.sections() if name != SECTION]
    if unknown_sections:
        raise ValueError(f"unknown section [{unknown_sections[0]}]; options go under [{SECTION}]")
    values = dict(parser[SECTION]) if parser.has_section(SECTION) else {}
    unknown = [name for name in values if name not in CONFIG_OPTIONS]
    if unknown:
        raise ValueError(f"unknown option '{unknown[0]}'; the file can set: {', '.join(CONFIG_OPTIONS)}")
    return values


BOOLEANS = configparser.ConfigParser.BOOLEAN_STATES


def config_defaults(parser, values):
    """Turn the file's text values into argparse defaults, checked the same way as on the command line.

    Raises ValueError naming the option whose value is wrong.
    """
    actions = {long_name(action): action for action in parser._actions if long_name(action)}
    defaults = {}
    for name, text in values.items():
        action = actions[name]
        try:
            if action.nargs == 0:  # a flag: store_true, or --x/--no-x
                if text.strip().lower() not in BOOLEANS:
                    raise ValueError(f"expected yes or no, not '{text}'")
                value = BOOLEANS[text.strip().lower()]
            elif isinstance(action, argparse._AppendAction):
                value = [convert(action, line.strip()) for line in text.splitlines() if line.strip()]
            else:
                value = convert(action, text.strip())
        except (ValueError, argparse.ArgumentTypeError) as error:
            raise ValueError(f"{name}: {error}") from None
        defaults[action.dest] = value
    return defaults


def long_name(action):
    """The option's first long name without dashes ("toman" for --toman/--no-toman), or None."""
    return next((option[2:] for option in action.option_strings if option.startswith("--")), None)


def convert(action, text):
    if action.type is float:
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"expected a number, not '{text}'") from None
    value = action.type(text) if action.type else text
    if action.choices and value not in action.choices:
        raise ValueError(f"'{text}' is not one of {', '.join(action.choices)}")
    return value

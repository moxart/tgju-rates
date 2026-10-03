"""``--completion bash|zsh|fish``: print a shell completion script.

Options come from the argument parser, and codes from the names this program knows, so the script
works offline. A currency the site adds later completes once it has an entry in ENGLISH_NAMES.
"""

from tgju_rates.alerts import TOTAL_KEY
from tgju_rates.animation import ANIMATIONS
from tgju_rates.currencies import known_codes
from tgju_rates.markets import ALL_MARKETS, MARKETS

SHELLS = ("bash", "zsh", "fish")
PROG = "tgju-rates"
# Options whose value is a comma-separated list, a code, a code followed by "=", or a file.
CODE_LIST_OPTIONS = ("--watch",)
CODE_OPTIONS = ("--history",)
RULE_OPTIONS = ("--alert",)
HOLD_OPTIONS = ("--hold",)
FILE_OPTIONS = ("--db", "--holdings")

BASH_TEMPLATE = """\
# bash completion for {prog}
_tgju_rates() {{
    local cur=${{COMP_WORDS[COMP_CWORD]}} prev=${{COMP_WORDS[COMP_CWORD-1]}}
    local codes="{codes}"
    local words
    case $prev in
        {code_lists}|--market)
            words=$codes
            [[ $prev == --market ]] && words="{markets}"
            local head=""
            [[ $cur == *,* ]] && head=${{cur%,*}},
            COMPREPLY=($(compgen -P "$head" -W "$words" -- "${{cur##*,}}"))
            type compopt &>/dev/null && compopt -o nospace 2>/dev/null
            return;;
        {code_options})
            COMPREPLY=($(compgen -W "$codes" -- "$cur"))
            return;;
        {rule_options})
            COMPREPLY=($(compgen -W "$codes {total}" -- "$cur"))
            type compopt &>/dev/null && compopt -o nospace 2>/dev/null
            return;;
        {hold_options})
            COMPREPLY=($(compgen -S = -W "$codes" -- "$cur"))
            type compopt &>/dev/null && compopt -o nospace 2>/dev/null
            return;;
        --animation)
            COMPREPLY=($(compgen -W "{animations}" -- "$cur"))
            return;;
        --completion)
            COMPREPLY=($(compgen -W "{shells}" -- "$cur"))
            return;;
        {file_options})
            COMPREPLY=($(compgen -f -- "$cur"))
            return;;
        {value_options})
            return;;
    esac
    COMPREPLY=($(compgen -W "{options}" -- "$cur"))
}}
complete -F _tgju_rates {prog}
"""


def option_actions(parser):
    """(action, long option) for every option the parser takes, help and version included."""
    for action in parser._actions:
        longs = [option for option in action.option_strings if option.startswith("--")]
        if longs:
            yield action, longs[0]


def bash_script(parser):
    special = {*CODE_LIST_OPTIONS, *CODE_OPTIONS, *RULE_OPTIONS, *HOLD_OPTIONS, *FILE_OPTIONS}
    special |= {"--market", "--animation", "--completion"}
    options, value_options = [], []
    for action, option in option_actions(parser):
        options += action.option_strings
        if action.nargs != 0 and option not in special:
            value_options += action.option_strings
    return BASH_TEMPLATE.format(
        prog=PROG,
        codes=" ".join(known_codes()),
        markets=" ".join([*MARKETS, ALL_MARKETS]),
        animations=" ".join(ANIMATIONS),
        shells=" ".join(SHELLS),
        total=TOTAL_KEY,
        code_lists="|".join(CODE_LIST_OPTIONS),
        code_options="|".join(CODE_OPTIONS),
        rule_options="|".join(RULE_OPTIONS),
        hold_options="|".join(HOLD_OPTIONS),
        file_options="|".join(FILE_OPTIONS),
        value_options="|".join(value_options),
        options=" ".join(options),
    )


def zsh_script(parser):
    # zsh runs bash completion functions through bashcompinit.
    return "# zsh completion for tgju-rates\nautoload -U +X bashcompinit && bashcompinit\n" + bash_script(parser)


# Completes the word after the last comma, keeping what's before it, for comma-separated values.
FISH_LIST_FUNCTION = """\
function __tgju_rates_list
    set -l head (string replace -r '[^,]*$' '' -- (commandline -ct))
    for word in $argv
        echo $head$word
    end
end"""


def fish_quote(text):
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def fish_script(parser):
    codes = " ".join(known_codes())
    candidates = {
        "--market": " ".join([*MARKETS, ALL_MARKETS]),
        "--animation": " ".join(ANIMATIONS),
        "--completion": " ".join(SHELLS),
        **{option: codes for option in (*CODE_OPTIONS, *CODE_LIST_OPTIONS)},
        **{option: f"{codes} {TOTAL_KEY}" for option in RULE_OPTIONS},
        **{option: " ".join(f"{code}=" for code in known_codes()) for option in HOLD_OPTIONS},
    }
    lines = [f"# fish completion for {PROG}", FISH_LIST_FUNCTION, f"complete -c {PROG} -f"]
    for action, option in option_actions(parser):
        parts = [f"complete -c {PROG} -l {option[2:]}"]
        parts += [f"-s {short[1:]}" for short in action.option_strings if len(short) == 2]
        if action.help:
            parts.append("-d " + fish_quote(action.help.split(";")[0].split(" (")[0]))
        if option in FILE_OPTIONS:
            parts.append("-r -F")
        elif option in CODE_LIST_OPTIONS or option == "--market":
            parts.append("-x -a " + fish_quote(f"(__tgju_rates_list {candidates[option]})"))
        elif option in candidates:
            parts.append(f"-x -a {fish_quote(candidates[option])}")
        elif action.nargs != 0:
            parts.append("-x")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def completion_script(shell, parser):
    return {"bash": bash_script, "zsh": zsh_script, "fish": fish_script}[shell](parser)

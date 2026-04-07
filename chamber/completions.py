from __future__ import annotations

import os
import sys


def detect_shell() -> str:
    """Detect the user's shell from $SHELL."""
    shell_path = os.environ.get("SHELL", "")
    basename = os.path.basename(shell_path)
    if basename in ("bash", "zsh", "fish"):
        return basename
    # Fallback: check common indicators
    if "ZSH_VERSION" in os.environ:
        return "zsh"
    if "FISH_VERSION" in os.environ:
        return "fish"
    return "bash"


_INSTRUCTIONS = {
    "bash": {
        "eval_cmd": 'eval "$(_CHAMBER_COMPLETE=bash_source chamber)"',
        "file": "~/.bashrc",
        "setup": (
            "Add this line to your ~/.bashrc:\n\n"
            '  eval "$(_CHAMBER_COMPLETE=bash_source chamber)"\n\n'
            "Then reload your shell:\n\n"
            "  source ~/.bashrc"
        ),
    },
    "zsh": {
        "eval_cmd": 'eval "$(_CHAMBER_COMPLETE=zsh_source chamber)"',
        "file": "~/.zshrc",
        "setup": (
            "Add this line to your ~/.zshrc:\n\n"
            '  eval "$(_CHAMBER_COMPLETE=zsh_source chamber)"\n\n'
            "Then reload your shell:\n\n"
            "  source ~/.zshrc"
        ),
    },
    "fish": {
        "eval_cmd": "_CHAMBER_COMPLETE=fish_source chamber | source",
        "file": "~/.config/fish/completions/chamber.fish",
        "setup": (
            "Run this command to install completions:\n\n"
            "  _CHAMBER_COMPLETE=fish_source chamber > ~/.config/fish/completions/chamber.fish\n\n"
            "Completions will load automatically on next shell start."
        ),
    },
}


def install_completions(shell: str | None = None) -> None:
    """Print shell completion install instructions."""
    if shell is None:
        shell = detect_shell()

    if shell not in _INSTRUCTIONS:
        print(f"Unsupported shell: {shell}. Supported: bash, zsh, fish", file=sys.stderr)
        sys.exit(1)

    info = _INSTRUCTIONS[shell]
    print(f"Shell detected: {shell}\n", file=sys.stderr)
    print(info["setup"], file=sys.stderr)

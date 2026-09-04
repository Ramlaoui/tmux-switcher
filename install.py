# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install into a tmux config, backing up existing files outside the checkout."""

import argparse
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main():
    default = Path.home() / ".config/tmux/tmux.conf"
    if not default.exists():
        default = Path.home() / ".tmux.conf"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=default, help="tmux config to update"
    )
    args = parser.parse_args()
    for command in ("tmux", "fzf", "uv"):
        if not shutil.which(command):
            parser.error(f"missing required command: {command}")
    root = Path(__file__).resolve().parent
    config = args.config.expanduser().resolve()
    text = config.read_text() if config.exists() else ""
    shell_command = shlex.join(["sh", str(root / "tmux-switcher.tmux")])
    source = "run-shell '" + shell_command.replace("'", "'\\''") + "'"
    if source not in text.splitlines():
        state = Path(
            os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))
        )
        backup = (
            state
            / "tmux-switcher"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        backup.mkdir(parents=True, mode=0o700)
        if config.exists():
            shutil.copy2(config, backup / "tmux.conf")
        original = subprocess.run(
            ["tmux", "list-keys", "-T", "prefix", "C-j"], capture_output=True, text=True
        )
        (backup / "original-binding.tmux").write_text(
            original.stdout or "unbind-key C-j\n"
        )
        legacy = f'source-file "{root / "switcher.tmux"}"'
        if legacy in text.splitlines():
            text = text.replace(legacy, source)
        else:
            text = text.rstrip() + "\n\n# tmux-switcher\n" + source + "\n"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(text)
        print(f"Config updated: {config}\nBackup: {backup}")
    if subprocess.run(["tmux", "list-sessions"], capture_output=True).returncode == 0:
        subprocess.run(["sh", str(root / "tmux-switcher.tmux")], check=True)
        print("Prefix + Ctrl-J is active.")
    else:
        print("The binding will load when tmux starts.")


if __name__ == "__main__":
    main()

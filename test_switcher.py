# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Integration smoke on a private tmux server, including real fzf interaction."""

import fcntl
import json
import os
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test():
    with tempfile.TemporaryDirectory(prefix="switcher-test-") as directory:
        socket = str(Path(directory) / "tmux.sock")
        env = dict(os.environ, TMUX=f"{socket},0,0", TERM="xterm-256color")

        def tmux(*args):
            return subprocess.check_output(
                ["tmux", "-S", socket, *args], env=env, text=True
            ).strip()

        def wait_for(check):
            for _ in range(100):
                if check():
                    return
                time.sleep(0.05)
            raise AssertionError("Timed out waiting for picker state")

        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 45, 140, 0, 0))
        client = None
        try:
            tmux(
                "-f",
                "/dev/null",
                "new-session",
                "-d",
                "-s",
                "alpha",
                "-x",
                "140",
                "-y",
                "45",
            )
            tmux("new-session", "-d", "-s", "beta")
            checkout = Path(directory) / "plugin with 'quotes' $literal"
            checkout.mkdir()
            for name in ("switcher.py", "install.py", "tmux-switcher.tmux"):
                shutil.copy2(ROOT / name, checkout / name)
            config = Path(directory) / "test.conf"
            config.write_text("set -g status on\n")
            install_env = dict(env, XDG_STATE_HOME=str(Path(directory) / "state"))
            for _ in range(2):
                subprocess.run(
                    [
                        sys.executable,
                        str(checkout / "install.py"),
                        "--config",
                        str(config),
                    ],
                    env=install_env,
                    check=True,
                    stdout=subprocess.PIPE,
                )
            assert config.read_text().count("run-shell") == 1
            assert len(list((Path(directory) / "state/tmux-switcher").iterdir())) == 1
            tmux("source-file", str(config))
            assert "quotes" in tmux("list-keys", "-T", "prefix", "C-j")
            subprocess.run(
                ["sh", str(ROOT / "tmux-switcher.tmux")], env=env, check=True
            )
            assert "switcher.py" in tmux("list-keys", "-T", "prefix", "C-j")
            target = tmux(
                "split-window",
                "-d",
                "-t",
                "beta",
                "-P",
                "-F",
                "#{pane_id}",
                "-c",
                directory,
            )
            tmux("resize-pane", "-Z", "-t", "beta")
            client = subprocess.Popen(
                ["tmux", "-S", socket, "attach", "-t", "alpha"],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
            )
            wait_for(lambda: tmux("list-clients", "-F", "#{client_name}"))
            client_name = tmux("list-clients", "-F", "#{client_name}")
            current = tmux("display-message", "-p", "-t", "alpha", "#{session_id}")
            listing = json.loads(
                subprocess.check_output(
                    [
                        sys.executable,
                        "-c",
                        "import json, switcher; print(json.dumps(switcher.rows('')))",
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                )
            )
            assert all(row.split("\t")[2] == "session" for row in listing)
            match = subprocess.check_output(
                ["fzf", "--delimiter=\t", "--with-nth=4..", "--filter", directory],
                input="\n".join(listing),
                text=True,
                env=dict(env, FZF_DEFAULT_OPTS="", FZF_DEFAULT_OPTS_FILE=""),
            )
            assert "\tsession\t" in match and "beta" in match

            def launch():
                return tmux(
                    "new-window",
                    "-t",
                    "alpha",
                    "-P",
                    "-F",
                    "#{pane_id}",
                    "uv",
                    "run",
                    "--no-sync",
                    "--script",
                    str(ROOT / "switcher.py"),
                    "choose",
                    client_name,
                    current,
                )

            picker = launch()
            wait_for(lambda: "Tasks" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(lambda: "Panes" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "Down")
            time.sleep(0.1)
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(lambda: "Tasks" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(lambda: "Panes ›" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "C-r")
            time.sleep(0.3)
            tmux("send-keys", "-t", picker, "Enter")
            wait_for(lambda: tmux("list-clients", "-F", "#{session_name}") == "beta")
            assert tmux("display-message", "-p", "-t", "beta", "#{pane_id}") == target
            tmux("switch-client", "-c", client_name, "-t", "alpha")
            picker = launch()
            wait_for(lambda: "Tasks ›" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "-l", directory)
            wait_for(lambda: directory in tmux("capture-pane", "-p", "-t", picker))
            time.sleep(0.3)
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(lambda: "Panes ›" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "-l", directory)
            time.sleep(0.2)
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(
                lambda: (
                    "Tasks › " + directory in tmux("capture-pane", "-p", "-t", picker)
                )
            )
            tmux("send-keys", "-t", picker, "Tab")
            wait_for(
                lambda: (
                    "Panes › " + directory in tmux("capture-pane", "-p", "-t", picker)
                )
            )
            tmux("send-keys", "-t", picker, "C-r")
            time.sleep(0.3)
            tmux("send-keys", "-t", picker, "Enter")
            wait_for(lambda: tmux("list-clients", "-F", "#{session_name}") == "beta")
            assert tmux("display-message", "-p", "-t", "beta", "#{pane_id}") == target
            assert (
                tmux("display-message", "-p", "-t", "beta", "#{window_zoomed_flag}")
                == "1"
            )
            tmux("switch-client", "-c", client_name, "-t", "alpha")
            picker = launch()
            wait_for(lambda: "Tasks" in tmux("capture-pane", "-p", "-t", picker))
            tmux("send-keys", "-t", picker, "C-p")
            wait_for(
                lambda: "Recent panes ›" in tmux("capture-pane", "-p", "-t", picker)
            )
            assert target in tmux("show-options", "-gqv", "@task-switcher-recent")
            tmux("send-keys", "-t", picker, "C-f", "S-Up", "S-Down", "C-f")
            tmux("send-keys", "-t", picker, "Escape")
            wait_for(
                lambda: (
                    picker
                    not in tmux("list-panes", "-a", "-F", "#{pane_id}").splitlines()
                )
            )
            assert tmux("list-clients", "-F", "#{session_name}") == "alpha"
            while select.select([master], [], [], 0)[0]:
                os.read(master, 65536)
            os.write(master, b"\x02\x0a")  # Default test-server prefix, then Ctrl-J.
            output = bytearray()

            def popup_visible():
                if select.select([master], [], [], 0.05)[0]:
                    output.extend(os.read(master, 65536))
                return b"Tasks" in output

            try:
                wait_for(popup_visible)
            except AssertionError:
                raise AssertionError(
                    f"Popup did not open: {bytes(output[-3000:])!r}"
                ) from None
            os.write(master, b"\r")
            wait_for(lambda: tmux("list-clients", "-F", "#{session_name}") == "beta")
            print(
                "PASS: stable session search, Tab round-trip, query/selection restoration, refresh, recent panes, preview controls, exact pane jump, zoom, cancel, popup binding"
            )
        finally:
            subprocess.run(["tmux", "-S", socket, "kill-server"], capture_output=True)
            if client:
                client.kill()
                client.wait(timeout=5)
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    test()

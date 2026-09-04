#!/usr/bin/env -S uv run --no-sync --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Recent tmux sessions and panes, presented by fzf."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def tmux(*args):
    return subprocess.check_output(["tmux", *args], text=True).rstrip("\n")


def recent_panes():
    """Treat manually edited or stale state as an empty history."""
    try:
        value = json.loads(
            tmux("show-options", "-gqv", "@task-switcher-recent") or "[]"
        )
        return (
            [p for p in value if isinstance(p, str) and p.startswith("%")][:20]
            if isinstance(value, list)
            else []
        )
    except json.JSONDecodeError:
        return []


def rows(current, scope=""):
    sessions = [
        line.split("\t")
        for line in tmux(
            "list-sessions",
            "-F",
            "#{session_id}\t#{session_name}\t#{session_last_attached}\t#{session_windows}",
        ).splitlines()
    ]
    sessions.sort(key=lambda s: (s[0] == current, -int(s[2] or 0), s[1]))
    panes = [
        line.split("\t")
        for line in tmux(
            "list-panes",
            "-a",
            "-F",
            "#{session_id}\t#{pane_id}\t#{window_index}.#{pane_index}\t#{window_name}"
            "\t#{pane_current_command}\t#{pane_active}\t#{window_active}\t#{pane_current_path}\t#{pane_title}",
        ).splitlines()
    ]
    recent = recent_panes()
    result = []
    for sid, name, _, windows in sessions:
        if scope not in ("", "recent", sid):
            continue
        members = [p for p in panes if p[0] == sid]
        if not members:
            continue
        active = next((p for p in members if p[5:7] == ["1", "1"]), members[0])
        labels = {}
        for p in members:
            path = p[7]
            if path == str(Path.home()) or path.startswith(str(Path.home()) + "/"):
                path = "~" + path[len(str(Path.home())) :]
            details = [p[4], path]
            if p[3] not in (p[4], "bash", "zsh", "fish", "sh", "node", "python"):
                details.append(p[3])
            title = p[8] if len(p) > 8 else ""
            if (
                title
                and title not in details
                and title != os.uname().nodename
                and not title.startswith(os.environ.get("USER", "") + "@")
            ):
                details.append(title)
            labels[p[1]] = " · ".join(details)
        if not scope:
            marker = " · current" if sid == current else ""
            # Full pane metadata remains searchable even beyond the visible row width.
            description = " | ".join(dict.fromkeys(labels.values()))
            result.append(
                f"{sid}\t{active[1]}\tsession\t{name} · {windows}w/{len(members)}p{marker}  {description}"
            )
        else:
            for p in members:
                if scope == "recent" and p[1] not in recent:
                    continue
                detail = labels[p[1]].split(" · ", 1)[-1]
                result.append(
                    f"{sid}\t{p[1]}\tpane\t{p[4]:<10} {detail}  — {name} {p[2]}"
                )
    if scope == "recent":
        result.sort(key=lambda row: recent.index(row.split("\t")[1]))
    return result


def preview(pane):
    try:
        print(
            tmux(
                "display-message",
                "-p",
                "-t",
                pane,
                "#{session_name} / #{window_index}:#{window_name} / pane #{pane_index}"
                "\n#{pane_current_command} · #{pane_current_path}",
            )
        )
        print("─" * 50)
        print(tmux("capture-pane", "-p", "-t", pane, "-S", "-500").rstrip())
    except subprocess.CalledProcessError:
        print("This pane is no longer available.")


def choose(client, current):
    command = shlex.join([sys.executable, str(Path(__file__).resolve())])
    env = dict(os.environ, FZF_DEFAULT_OPTS="", FZF_DEFAULT_OPTS_FILE="")
    scope = ""
    saved = {}
    while True:
        listing = rows(current, scope)
        query, selected = saved.get(scope, ("", ""))
        base = ["fzf", "--no-sort", "--delimiter=\t", "--with-nth=4.."]
        position = 1
        if selected:
            filtered = subprocess.run(
                [*base, "--filter", query],
                input="\n".join(listing),
                stdout=subprocess.PIPE,
                text=True,
                env=env,
            ).stdout.splitlines()
            position = next(
                (
                    i
                    for i, row in enumerate(filtered, 1)
                    if "\t".join(row.split("\t")[:3]) == selected
                ),
                1,
            )
        title = "Recent panes" if scope == "recent" else "Panes" if scope else "Tasks"
        result = subprocess.run(
            [
                *base,
                "--layout=reverse",
                "--border=rounded",
                "--sync",
                "--query",
                query,
                "--print-query",
                "--expect=tab,ctrl-r,ctrl-p",
                "--prompt",
                f"{title} › ",
                "--border-label= tmux switcher · F1 help ",
                "--header=Enter jump · Tab expand/back · Ctrl-P recent panes · Ctrl-R refresh\nShift-Up/Down scroll preview · Ctrl-F enlarge · Ctrl-/ hide · Esc cancel",
                "--preview",
                f"{command} preview {{2}}",
                "--preview-window=right,45%,border-left,follow",
                "--bind",
                f"start:hide-header+pos({position})",
                "--bind",
                "f1:toggle-header",
                "--bind",
                "ctrl-j:down,ctrl-k:up,ctrl-/:toggle-preview",
                "--bind",
                "shift-up:preview-up,shift-down:preview-down,shift-page-up:preview-page-up,shift-page-down:preview-page-down",
                "--bind",
                "ctrl-f:change-preview-window(right,75%,border-left,follow|right,45%,border-left,follow)",
            ],
            input="\n".join(listing),
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        if result.returncode in (1, 130):
            return
        if result.returncode:
            raise SystemExit(result.returncode)
        query, key, *selection = result.stdout.splitlines()
        row = selection[0].split("\t", 3) if selection else None
        saved[scope] = (query, "\t".join(row[:3]) if row else selected)
        if key == "ctrl-p":
            scope = "" if scope == "recent" else "recent"
        elif key == "tab":
            if scope:
                scope = ""
            elif row:
                scope = row[0]
        elif key == "ctrl-r":
            continue
        elif row:
            sid, pane, kind, _ = row
            if kind == "pane":
                tmux("select-pane", "-Z", "-t", pane)
                tmux("select-window", "-t", pane)
            tmux("switch-client", "-c", client, "-t", sid)
            if kind == "pane":
                recent = recent_panes()
                recent = [pane] + [p for p in recent if p != pane]
                tmux(
                    "set-option", "-g", "@task-switcher-recent", json.dumps(recent[:20])
                )
            return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            "Run install.py to install, or load tmux-switcher.tmux with TPM."
        )
    action, *args = sys.argv[1:]
    try:
        if action == "bind":
            for dependency in ("tmux", "fzf", "uv"):
                if not shutil.which(dependency):
                    raise SystemExit(f"Missing required command: {dependency}")
            command = shlex.join(
                [
                    shutil.which("uv"),
                    "run",
                    "--quiet",
                    "--no-sync",
                    "--script",
                    str(Path(__file__).resolve()),
                    "open",
                ]
            )
            tmux(
                "bind-key",
                "C-j",
                "run-shell",
                command + " #{q:client_name} #{q:session_id}",
            )
        elif action == "preview":
            preview(args[0])
        elif action == "choose":
            choose(*args)
        elif action == "open":
            command = shlex.join(
                [sys.executable, str(Path(__file__).resolve()), "choose", *args]
            )
            subprocess.run(
                [
                    "tmux",
                    "display-popup",
                    "-c",
                    args[0],
                    "-E",
                    "-w",
                    "90%",
                    "-h",
                    "85%",
                    command,
                ],
                check=True,
            )
        else:
            raise SystemExit(f"Unknown action: {action}")
    except subprocess.CalledProcessError:
        raise SystemExit("tmux changed while the picker was open; reopen the switcher.")
    except FileNotFoundError as error:
        raise SystemExit(f"Missing required command: {error.filename}") from None

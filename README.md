# tmux-switcher

A compact tmux task switcher powered by fzf. Search sessions by name, command,
directory, or pane title; expand a session to jump to an exact pane. Preview
terminal output without leaving your current task.

Session results stay stable while typing. Switching views preserves your query
and selection; recently selected panes are one shortcut away.

## Install

Requires **tmux**, **fzf**, and **uv** on `PATH`, with Python 3.11+ available to uv.
Tested with tmux 3.6 and fzf 0.72. Python uses only the standard library.

```sh
git clone https://github.com/Ramlaoui/tmux-switcher.git
cd tmux-switcher
uv run --no-sync --script install.py
```

The installer adds **prefix + Ctrl-J** to your existing tmux config and activates
it immediately if tmux is running. Use `--config /path/to/tmux.conf` to select a
different config. Keep the checkout in place after installation.

Alternatively, with [TPM](https://github.com/tmux-plugins/tpm), add this before
TPM initialization and press **prefix + I**:

```tmux
set -g @plugin 'Ramlaoui/tmux-switcher'
```

## Keys

| Key | Action |
| --- | --- |
| Enter / Esc | Jump / cancel |
| Tab | Expand session / return |
| Ctrl-P | Toggle recent panes |
| Ctrl-J / Ctrl-K | Move down / up |
| Ctrl-R | Refresh, preserving your place |
| Shift-Up / Shift-Down | Scroll preview |
| Shift-PageUp / Shift-PageDown | Scroll preview by a page |
| Ctrl-F / Ctrl-/ | Enlarge / hide preview |
| F1 | Toggle shortcut help |

With an empty query, sessions follow tmux attachment time, with the current
session last. Searching ranks by fuzzy match quality, then by how early the
match appears in the row (favoring session names), then by recency.
Pane views start unfiltered. The 20 most recently selected panes are remembered
in the tmux server; closed panes disappear from results. History resets when
the server exits.

Previews include up to 500 lines of scrollback and refresh on selection or
Ctrl-R. No keys are sent to previewed panes. Existing window zoom is preserved.
The switcher makes no network requests and does not save terminal output to disk.
uv may download Python if a compatible interpreter is unavailable.

## Uninstall

Remove the installer's `run-shell` line (or the TPM plugin entry) from your config.
Restore your previous binding from the backup under
`${XDG_STATE_HOME:-~/.local/state}/tmux-switcher/` using
`tmux source-file /path/to/original-binding.tmux`, or run `tmux unbind-key C-j`.

## Development

```sh
uv run --no-sync --script test_switcher.py
uvx ruff check .
```

The integration test uses a private tmux server and a simulated terminal. It
checks navigation, search, previews, recent panes, zoom preservation, and the
installed popup binding without touching your working sessions.

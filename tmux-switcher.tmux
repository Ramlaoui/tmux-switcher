#!/bin/sh
# TPM entry point; also usable through run-shell in tmux.conf.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec uv run --quiet --no-sync --script "$project_dir/switcher.py" bind

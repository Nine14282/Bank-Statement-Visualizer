#!/usr/bin/env bash
# Install Statement Visualizer on this computer, without opening it (safe to re-run).
#
# Sets up the Python environment and your private settings, and adds the app-menu entry (Linux) or the launcher file
# (macOS). Nothing opens: use the app when you want to, from your app menu or with ./run.sh. Everything after that
# (adding statements, passwords, theme, expected spending) happens in the app. Remove it again with ./uninstall.sh.
# The work is done by ./setup.sh; ./run.sh also calls it by itself on a first run.
set -euo pipefail
cd "$(dirname "$0")"
SV_NO_OPEN=1 exec ./setup.sh

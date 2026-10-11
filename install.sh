#!/usr/bin/env bash
# Install Statement Visualizer on this computer, without opening it (safe to re-run).
#
#   ./install.sh          the app window (default; keeps the mode of an existing install)
#   ./install.sh --app    the app window: also installs pywebview, adds the app-menu entry / launcher
#   ./install.sh --web    browser only: no pywebview, no launcher; ./run.sh opens the pages in your browser
#
# Sets up the Python environment and your private settings, and adds the app-menu entry (Linux) or the launcher file
# (macOS). Nothing opens: use the app when you want to, from your app menu or with ./run.sh. Everything after that
# (adding statements, passwords, theme, expected spending) happens in the app. Remove it again with ./uninstall.sh.
#
# The work is done by workspace/launcher.py, the same on Windows (install.cmd).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" install "$@"

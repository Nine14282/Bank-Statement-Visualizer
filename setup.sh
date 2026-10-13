#!/usr/bin/env bash
# One-time setup (safe to re-run; ./install.sh is the friendly front door): Python venv + packages, settings file. No Node.js needed: the dashboard page
# ships prebuilt (web/prebuilt/index.html) and Python fills in your data.
#   ./setup.sh [--app|--web]   --app: app window (pywebview + launcher); --web: browser only. Default: the mode already
#                              installed (.venv/mode), else app.
#
# The work is done by workspace/launcher.py (on Windows: the StatementVisualizer.exe program, see README).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" setup "$@"

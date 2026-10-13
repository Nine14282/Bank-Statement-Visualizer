#!/usr/bin/env bash
# Uninstall Statement Visualizer.
#
#   ./uninstall.sh          remove what setup installed: the app-menu entry / launcher, .venv, web/node_modules and
#                           the generated dashboard. Keeps your PDFs, ledger, .env and Gmail login; ./run.sh sets
#                           everything up again.
#   ./uninstall.sh --all    also delete this whole project folder: your PDFs, ledger, .env (saved passwords) and the
#                           saved Gmail login. No undo. Asks you to type the folder name first.
#   -y   skip the "Continue?" question of the plain removal      -n   only list what would be removed
#
# Not done for you: a cron line for ./gmail.sh (crontab -e) and the access you gave Google (see the README).
#
# The work is done by workspace/launcher.py, also the entry point of the Windows program (StatementVisualizer.exe uninstall).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" uninstall "$@"

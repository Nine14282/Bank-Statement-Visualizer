#!/usr/bin/env bash
# Option 1 (manual): statement PDFs -> ledger.csv -> web/dist/index.html
#
#   ./run.sh                      opens the app: its own window with the dashboard, Add statements and Settings, or
#                                 the first-time setup when there's no ledger yet (statements, passwords, theme,
#                                 expected spending). Installs what's missing first. No window possible here (no
#                                 Qt web view)? The same setup or add-statements pages open in the browser
#   ./run.sh --web                the browser pages instead of the app window (also the default after ./install.sh --web)
#   ./run.sh --setup              the full setup page again, in the browser (in the app: the Settings button)
#   ./run.sh --app                the app, also with nobody at the terminal (what the launcher from ./setup.sh runs)
#   ./run.sh --rebuild            no browser: rebuild from the PDFs already in Statement/ (asks for a password
#                                 in the terminal if needed). Also what runs when nobody is at the terminal (a script)
#   KTB_PW=... KBANK_PW=... ./run.sh --rebuild   or keep the passwords in .env (the pages can save them there)
#   ./run.sh --password=...       rebuild with this password (visible in shell history)
#
# The work is done by workspace/launcher.py, also the entry point of the Windows program (StatementVisualizer.exe run).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" run "$@"

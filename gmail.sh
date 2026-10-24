#!/usr/bin/env bash
# Download new statement PDFs from Gmail into Statement/, then rebuild the dashboard.
# Read-only Gmail access. First run opens a browser once to authorise; see README for the Google setup.
#
#   ./gmail.sh                    fetch + build
#   ./gmail.sh --no-build         only download the PDFs
#   ./gmail.sh --listen           keep running: fetch + build within seconds of new mail (Pub/Sub; README "Real time")
# The app does the same with no terminal: Fetch from Gmail (Add statements), a fetch each time it opens once signed in,
# and the --listen listener while its window is open when real time is set up (Settings, last step). Unattended runs
# have nobody to type PDF passwords: tick Remember for them in the app (or put KTB_PW / KBANK_PW in .env).
#
# The work is done by workspace/launcher.py, also the entry point of the Windows program (StatementVisualizer.exe gmail).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" gmail "$@"

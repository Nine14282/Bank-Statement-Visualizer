#!/usr/bin/env bash
# Option 2: download new statement PDFs from Gmail into Statement/, then rebuild the dashboard.
# Read-only Gmail access. First run opens a browser once to authorise; see README for the Google setup.
#
#   ./gmail.sh                    fetch + build
#   ./gmail.sh --no-build         only download the PDFs
#   ./gmail.sh --listen           keep running: fetch + build within seconds of new mail (Pub/Sub; README "Real time")
# --listen is the only automatic fetch (nothing runs on a schedule). It has nobody to type PDF passwords: put
# KTB_PW / KBANK_PW in .env first, and run ./gmail.sh once by hand to authorise.
#
# The work is done by workspace/launcher.py, also the entry point of the Windows program (StatementVisualizer.exe gmail).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" gmail "$@"

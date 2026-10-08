#!/usr/bin/env bash
# Option 1 (manual): statement PDFs you put in Statement/ -> ledger.csv -> web/dist/index.html
#
#   ./run.sh                      asks for the PDF password when a file needs one
#   KTB_PW=... KBANK_PW=... ./run.sh   or set KTB_PW / KBANK_PW in .env (never typed again)
#   ./run.sh --password=...       or pass it on the command line (visible in shell history)
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

[ -x .venv/bin/python ] || { echo "Not set up yet. Run ./setup.sh first." >&2; exit 1; }
mkdir -p Statement
if ! ls Statement/*.pdf >/dev/null 2>&1; then
  echo "No PDFs in Statement/. Copy your bank statement PDFs there, then run ./run.sh again." >&2
  exit 1
fi

.venv/bin/python workspace/update_statement.py "$@"
echo "Dashboard: $PWD/web/dist/index.html  (open it in a browser)"

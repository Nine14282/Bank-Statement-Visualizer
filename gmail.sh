#!/usr/bin/env bash
# Option 2 (auto): download new statement PDFs from Gmail into Statement/, then rebuild the dashboard.
# Read-only Gmail access. First run opens a browser once to authorise; see README for the Google setup.
#
#   ./gmail.sh                    fetch + build
#   ./gmail.sh --no-build         only download the PDFs
# Unattended (cron): put KTB_PW / KBANK_PW in .env first, and run ./gmail.sh once by hand to authorise.
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

[ -x .venv/bin/python ] || { echo "Not set up yet. Run ./setup.sh first." >&2; exit 1; }
mkdir -p Statement

.venv/bin/python workspace/fetch_gmail.py "$@"
echo "Dashboard: $PWD/web/dist/index.html"

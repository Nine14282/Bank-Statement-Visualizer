#!/usr/bin/env bash
# One-time setup (safe to re-run): Python venv + packages, web app packages, settings file.
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1. $2" >&2; exit 1; }; }
need python3 "Install Python 3.10 or newer."
need node "Install Node.js 20 or newer (https://nodejs.org)."
need npm "It ships with Node.js."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10+ is required." >&2; exit 1; }
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || { echo "Node.js 20+ is required." >&2; exit 1; }

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
(cd web && npm install --no-audit --no-fund)

mkdir -p Statement
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env from .env.example (private, git-ignored)."
fi

# Build the dashboard now. With no data yet it is a blank "No data yet" page that explains the next steps.
.venv/bin/python workspace/build_dashboard.py

cat <<MSG

Setup done. Open this in a browser (blank until you add data):
  $PWD/web/dist/index.html

Next:
  1. Put your statement PDFs into Statement/
  2. ./run.sh            (manual: build from the PDFs you added)
     ./gmail.sh          (auto: download from Gmail, then build; see README for the one-time Google setup)
MSG

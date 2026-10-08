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
else
  # Settings added by newer versions (e.g. KTB_PW, KBANK_PW) go in blank; existing values are never touched.
  added=()
  [ -z "$(tail -c1 .env)" ] || echo >> .env   # keep the last line intact if it has no newline
  while IFS= read -r line; do
    key=${line%%=*}
    grep -q "^${key}=" .env || { printf '%s=\n' "$key" >> .env; added+=("$key"); }
  done < <(grep -E '^[A-Z_]+=' .env.example)
  [ ${#added[@]} -eq 0 ] || echo "Added new settings to .env (blank, fill them in): ${added[*]}"
fi

# Build the dashboard now. With no data yet it is a blank "No data yet" page that explains the next steps.
.venv/bin/python workspace/build_dashboard.py

cat <<MSG

Setup done. Open this in a browser (blank until you add data):
  $PWD/web/dist/index.html

Next:
  1. Put your statement PDFs into Statement/ (Krungthai, and KBank files named STM_...)
  2. Optional: put the PDF passwords in .env as KTB_PW and KBANK_PW (else you are asked)
  3. ./run.sh            (manual: build from the PDFs you added)
     ./gmail.sh          (auto: download from Gmail, then build; see README for the one-time Google setup)
Updating from an older version? Run ./run.sh once so the ledger gets the new Bank column.
MSG

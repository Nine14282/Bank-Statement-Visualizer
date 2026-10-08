#!/usr/bin/env bash
# One-time setup (safe to re-run): Python venv + packages, web app packages, settings file.
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

# Progress lines: "▸ step" (bold violet on a terminal), "  ✓ result". Each slow step says what it does first.
if [ -t 1 ]; then B=$'\033[1;35m'; G=$'\033[32m'; N=$'\033[0m'; else B= G= N=; fi
say() { printf '%s▸%s %s\n' "$B" "$N" "$*"; }
ok()  { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1. $2" >&2; exit 1; }; }
say "Checking for Python 3.10+ and Node.js 20+"
need python3 "Install Python 3.10 or newer."
need node "Install Node.js 20 or newer (https://nodejs.org)."
need npm "It ships with Node.js."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10+ is required." >&2; exit 1; }
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || { echo "Node.js 20+ is required." >&2; exit 1; }
ok "$(python3 --version), Node.js $(node --version)"

if [ -d .venv ]; then
  ok "Python environment already there (.venv)"
else
  say "Creating the Python environment (.venv)"
  python3 -m venv .venv
  ok "created"
fi
say "Installing Python packages (pdfplumber, Gmail client, ...): about a minute the first time"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
ok "Python packages ready"
say "Installing web packages for the dashboard (npm install): the slowest step, a few minutes the first time"
(cd web && npm install --no-audit --no-fund --loglevel=error)
ok "web packages ready"

say "Preparing folders and your private settings file"
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
ok "Statement/ folder and settings ready"

# Build the dashboard now. With no data yet it is a blank "No data yet" page that explains the next steps.
say "Building the dashboard page"
.venv/bin/python workspace/build_dashboard.py

cat <<MSG

Setup done. Next:
  ./run.sh            opens the setup page in your browser: add statements, unlock them, pick a theme
                      (later runs just rebuild; ./run.sh --setup opens the page again)
  ./gmail.sh          auto: download statements from Gmail, then build (see README for the Google setup)
Dashboard file (blank until you add data): $PWD/web/dist/index.html
Updating from an older version? Run ./run.sh once so the ledger gets the new Bank column.
MSG

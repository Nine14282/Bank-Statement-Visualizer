#!/usr/bin/env bash
# Option 1 (manual): statement PDFs -> ledger.csv -> web/dist/index.html
#
#   ./run.sh                      first run (no ledger yet): installs what's missing, then opens the setup page
#                                 in your browser (statements, passwords, theme, expected spending, Gmail tips).
#                                 After that: rebuilds from the PDFs in Statement/ (asks for a password if needed)
#   ./run.sh --setup              open the setup page again
#   KTB_PW=... KBANK_PW=... ./run.sh   or keep the passwords in .env (the setup page can save them there)
#   ./run.sh --password=...       or pass it on the command line (visible in shell history)
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

# Progress lines: "▸ step" (bold violet on a terminal). Every slow step says what it does first.
if [ -t 1 ]; then B=$'\033[1;35m'; N=$'\033[0m'; else B= N=; fi
say() { printf '%s▸%s %s\n' "$B" "$N" "$*"; }

printf '\n%sStatement Visualizer%s\n\n' "$B" "$N"
if ! { [ -x .venv/bin/python ] && [ -d web/node_modules ]; }; then
  say "First run: installing what it needs (Python and web packages). This happens once and takes a few minutes."
  ./setup.sh
  echo
fi

setup=0; args=()
for a in "$@"; do
  if [ "$a" = "--setup" ]; then setup=1; else args+=("$a"); fi
done
if [ "$setup" = 1 ] || [ ! -f workspace/ledger.csv ]; then
  if [ "$setup" = 1 ]; then say "Opening the setup page (--setup)"; else say "No ledger yet: opening the setup page"; fi
  exec .venv/bin/python workspace/welcome.py
fi

mkdir -p Statement
if ! ls Statement/*.pdf >/dev/null 2>&1; then
  echo "No PDFs in Statement/. Run ./run.sh --setup to add statements, or copy them there and run ./run.sh again." >&2
  exit 1
fi

say "Reading the statements in Statement/ and rebuilding your ledger"
.venv/bin/python workspace/update_statement.py ${args[@]+"${args[@]}"}
echo
say "Done. Dashboard: $PWD/web/dist/index.html  (open it in a browser)"

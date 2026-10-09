#!/usr/bin/env bash
# Option 1 (manual): statement PDFs -> ledger.csv -> web/dist/index.html
#
#   ./run.sh                      first run (no ledger yet): installs what's missing, then opens the setup page
#                                 in your browser (statements, passwords, theme, expected spending, Gmail tips).
#                                 After that: opens a short page to add new statement PDFs (drop them in, type
#                                 a password if one is needed), then rebuilds the dashboard
#   ./run.sh --setup              open the full setup page again
#   ./run.sh --rebuild            no browser: rebuild from the PDFs already in Statement/ (asks for a password
#                                 in the terminal if needed). Also what runs when nobody is at the terminal (cron)
#   KTB_PW=... KBANK_PW=... ./run.sh --rebuild   or keep the passwords in .env (the pages can save them there)
#   ./run.sh --password=...       rebuild with this password (visible in shell history)
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

# Progress lines: "▸ step" (bold violet on a terminal). Every slow step says what it does first.
if [ -t 1 ]; then B=$'\033[1;35m'; N=$'\033[0m'; else B= N=; fi
say() { printf '%s▸%s %s\n' "$B" "$N" "$*"; }

printf '\n%sStatement Visualizer%s\n\n' "$B" "$N"
if [ ! -x .venv/bin/python ]; then
  say "First run: installing what it needs (Python packages). This happens once and takes about a minute."
  ./setup.sh
  echo
fi

setup=0; rebuild=0; args=()
for a in "$@"; do
  case "$a" in
    --setup) setup=1 ;;
    --rebuild) rebuild=1 ;;
    *) args+=("$a") ;;   # e.g. --password=...: means a terminal rebuild
  esac
done
if [ "$setup" = 1 ] || [ ! -f workspace/ledger.csv ]; then
  if [ "$setup" = 1 ]; then say "Opening the setup page (--setup)"; else say "No ledger yet: opening the setup page"; fi
  exec .venv/bin/python workspace/welcome.py
fi
# A person at the terminal gets the add-statements page; --rebuild, --password= or no terminal (cron) rebuild here.
if [ "$rebuild" = 0 ] && [ ${#args[@]} -eq 0 ] && [ -t 0 ]; then
  say "Opening the page to add new statements (./run.sh --rebuild skips it)"
  exec .venv/bin/python workspace/welcome.py --add
fi

mkdir -p Statement
if ! ls Statement/*.pdf >/dev/null 2>&1; then
  echo "No PDFs in Statement/. Run ./run.sh to add statements on a page, or copy them there and run ./run.sh --rebuild." >&2
  exit 1
fi

say "Reading the statements in Statement/ and rebuilding your ledger"
.venv/bin/python workspace/update_statement.py ${args[@]+"${args[@]}"}
echo
say "Done. Dashboard: $PWD/web/dist/index.html  (open it in a browser)"

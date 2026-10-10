#!/usr/bin/env bash
# Option 1 (manual): statement PDFs -> ledger.csv -> web/dist/index.html
#
#   ./run.sh                      opens the app: its own window with the dashboard, Add statements and Settings, or
#                                 the first-time setup when there's no ledger yet (statements, passwords, theme,
#                                 expected spending). Installs what's missing first. No window possible here (no
#                                 pywebview / WebKit)? The same setup or add-statements pages open in the browser
#   ./run.sh --setup              the full setup page again, in the browser (in the app: the Settings button)
#   ./run.sh --app                the app, also with nobody at the terminal (what the launcher from ./setup.sh runs)
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
# .venv/requirements.installed is copied by setup.sh after a good install: an update that changes requirements.txt
# (a new package such as pywebview) reinstalls here instead of leaving the old venv to fail quietly.
if [ ! -x .venv/bin/python ]; then
  say "First run: installing what it needs (Python packages). This happens once and takes about a minute."
  SV_FROM_RUN=1 ./setup.sh   # it opens the app itself unless run from here
  echo
elif ! cmp -s requirements.txt .venv/requirements.installed; then
  say "Updating the Python packages (requirements changed). This takes about a minute."
  SV_FROM_RUN=1 ./setup.sh
  echo
fi

setup=0; rebuild=0; app=0; args=()
for a in "$@"; do
  case "$a" in
    --setup) setup=1 ;;
    --rebuild) rebuild=1 ;;
    --app) app=1 ;;
    *) args+=("$a") ;;   # e.g. --password=...: means a terminal rebuild
  esac
done
# The app (launcher, or a person at the terminal): the dashboard, or the first-time setup with no ledger yet; it adds
# statements and changes settings itself. Exit 3 = no window possible here: the browser pages below instead.
if [ "$setup" = 0 ] && [ "$rebuild" = 0 ] && [ ${#args[@]} -eq 0 ] && { [ "$app" = 1 ] || [ -t 0 ]; }; then
  .venv/bin/python workspace/build_dashboard.py >/dev/null   # always: a pull may bring a newer page, settings may change
  say "Opening the app"
  code=0; .venv/bin/python workspace/app.py || code=$?
  [ "$code" = 3 ] || exit "$code"
  say "No app window here (see README); using the browser instead"
  if [ "$app" = 1 ] && [ -f workspace/ledger.csv ]; then   # the launcher: just show the dashboard
    exec .venv/bin/python -c 'import pathlib, sys, webbrowser; webbrowser.open(pathlib.Path(sys.argv[1]).resolve().as_uri())' \
      web/dist/index.html
  fi
fi
if [ "$setup" = 1 ] || [ ! -f workspace/ledger.csv ]; then
  if [ "$setup" = 1 ]; then say "Opening the setup page (--setup)"; else say "No ledger yet: opening the setup page"; fi
  exec .venv/bin/python workspace/welcome.py
fi
# No app window: a person at the terminal gets the add-statements page; --rebuild, --password= or cron rebuild here.
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
say "Done. Dashboard: double-click Dashboard.html in $PWD"

#!/usr/bin/env bash
# Reset all your data, as on a fresh clone. The installed app stays: .venv, the app-menu entry, the code.
#
#   ./clear.sh     deletes your statement PDFs (Statement/), the ledger and manual entries, the dashboard page (it holds
#                  your transactions inline), the statement cache, the saved Gmail login and "seen" list, your expected
#                  spending, and what the app window saved (labels, theme). It also resets the settings file to the blank
#                  template (PDF passwords, Google client id/secret, your name, theme). Then it rebuilds the blank dashboard.
#   -y             skip the question           (--all is accepted and means the same)
#
# Not removed: the app itself (./uninstall.sh does that) and the access you gave Google (revoke it at
# https://myaccount.google.com/permissions). Labels you saved in a browser live in that browser: clear its site data.
set -euo pipefail
cd "$(dirname "$0")"

yes=0
for a in "$@"; do
  case $a in -y) yes=1 ;; --all) ;; *) echo "usage: ./clear.sh [-y]" >&2; exit 1 ;; esac
done

data=(Statement/*.[pP][dD][fF] workspace/*.csv workspace/expected.json workspace/token.json workspace/credentials.json
      workspace/.gmail_seen.json workspace/.cache workspace/.app web/src/data web/dist/index.html)
found=()
for f in "${data[@]}"; do [ -e "$f" ] && found+=("$f"); done

echo "Will delete:"
if [ ${#found[@]} -gt 0 ]; then printf '  %s\n' "${found[@]}"; else echo "  (no data files found)"; fi
template=.env.example   # the blank settings setup.sh starts from
echo "Will reset to the blank template: your settings file (passwords, Google client id/secret, name, theme)"
echo "Kept: the installed app (.venv, app-menu entry) and the code."
if [ $yes = 0 ]; then read -rp "Continue? [y/N] " r; [[ $r == [yY]* ]] || { echo "Cancelled."; exit 0; }; fi

[ ${#found[@]} -eq 0 ] || rm -rf -- "${found[@]}"
if [ -f "$template" ]; then cp "$template" .env; chmod 600 .env; else rm -f .env; fi

# The blank page needs only the standard library, so it is rebuilt even after ./uninstall.sh removed the .venv.
py=.venv/bin/python; [ -x "$py" ] || py=python3
"$py" workspace/build_dashboard.py || { echo "Cleared, but the blank dashboard was not rebuilt: run ./install.sh." >&2; exit 0; }
echo "Cleared. It is now like a fresh install: open the app to set up again."

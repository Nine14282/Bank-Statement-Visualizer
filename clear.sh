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
#
# The work is done by workspace/launcher.py, the same on Windows (clear.cmd).
command -v python3 >/dev/null 2>&1 || { echo "Missing: python3. Install Python 3.10 or newer." >&2; exit 1; }
exec python3 "$(dirname "$0")/workspace/launcher.py" clear "$@"

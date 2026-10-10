#!/usr/bin/env bash
# Clear the data and rebuild the blank dashboard.
#
#   ./clear.sh          drop ledger.csv, dashboard data, the statement cache, manual_entries.csv and the Gmail "seen" list, so the next
#                       ./gmail.sh re-reads every email (notices come back; hand-typed manual rows are lost).
#                       The seen list and manual_entries.csv go together, else re-read notices would be added twice.
#   ./clear.sh --all    also delete Statement/*.pdf, so the next ./gmail.sh downloads those again too.
# Never touches the settings file or workspace/token.json. Asks before deleting; -y skips the question.
set -euo pipefail
cd "$(dirname "$0")"

all=0 yes=0
for a in "$@"; do
  case $a in --all) all=1 ;; -y) yes=1 ;; *) echo "usage: ./clear.sh [--all] [-y]" >&2; exit 1 ;; esac
done

files=(workspace/ledger.csv web/src/data/ledger.json workspace/manual_entries.csv workspace/.gmail_seen.json workspace/.cache)
[ $all = 1 ] && files+=(Statement/*.pdf)

echo "Will delete (if present):"; printf '  %s\n' "${files[@]}"
if [ $yes = 0 ]; then read -rp "Continue? [y/N] " r; [[ $r == [yY]* ]] || { echo "Cancelled."; exit 0; }; fi

rm -rf -- "${files[@]}"   # -r: workspace/.cache is a folder (parsed statements)
[ -x .venv/bin/python ] || { echo "Cleared. Run ./setup.sh to rebuild the blank dashboard." >&2; exit 0; }
.venv/bin/python workspace/build_dashboard.py
echo "Cleared. Dashboard is empty."

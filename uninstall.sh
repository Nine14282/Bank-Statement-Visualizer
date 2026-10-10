#!/usr/bin/env bash
# Uninstall Statement Visualizer.
#
#   ./uninstall.sh          remove what setup installed: the app-menu entry / launcher, .venv, web/node_modules and
#                           the generated dashboard. Keeps your PDFs, ledger, .env and Gmail login; ./run.sh sets
#                           everything up again.
#   ./uninstall.sh --all    also delete this whole project folder: your PDFs, ledger, .env (saved passwords) and the
#                           saved Gmail login. No undo. Asks you to type the folder name first.
#   -y   skip the "Continue?" question of the plain removal      -n   only list what would be removed
#
# Not done for you: a cron line for ./gmail.sh (crontab -e) and the access you gave Google (see the README).
set -euo pipefail
cd "$(dirname "$0")"

usage() { echo "usage: ./uninstall.sh [--all] [-y] [-n]" >&2; }

# Everything runs inside a function that ends in `exit`: --all deletes this very folder, script file included, and
# bash must have read the whole script before that.
main() {
  all=0; yes=0; dry=0
  for a in "$@"; do
    case $a in --all) all=1 ;; -y) yes=1 ;; -n) dry=1 ;; *) usage; exit 1 ;; esac
  done

  root=$PWD
  [ -f run.sh ] && [ -f workspace/extract_ledger.py ] || { echo "This is not the Statement Visualizer folder." >&2; exit 1; }
  case $root in /|"$HOME") echo "Refusing to remove $root." >&2; exit 1 ;; esac

  # The Linux app-menu entry lives outside this folder (setup.sh writes it); on macOS the launcher is inside.
  launcher="${XDG_DATA_HOME:-$HOME/.local/share}/applications/statement-visualizer.desktop"
  items=("$launcher" .venv web/node_modules web/dist Dashboard.html "Statement Visualizer.command")
  found=()
  for f in "${items[@]}"; do [ -e "$f" ] && found+=("$f"); done

  if [ ${#found[@]} -gt 0 ]; then
    echo "Will delete:"; printf '  %s\n' "${found[@]}"
  else
    echo "Nothing installed to remove."
  fi
  if [ $all = 1 ]; then
    pdfs=$(ls Statement/*.pdf 2>/dev/null | wc -l | tr -d ' ')
    echo
    echo "AND the whole folder $root, including:"
    echo "  Statement/ ($pdfs PDF), workspace/ (ledger, saved Gmail login), .env (saved passwords, Gmail secret)"
  else
    echo "Kept: Statement/, workspace/ (ledger), .env, the code."
  fi
  [ $dry = 1 ] && { echo "(-n: nothing was deleted)"; exit 0; }

  if [ $all = 1 ]; then
    echo; echo "This cannot be undone."
    [ -t 0 ] || { echo "--all needs a terminal to confirm." >&2; exit 1; }
    read -rp "Type the folder name ($(basename "$root")) to delete everything: " r
    [ "$r" = "$(basename "$root")" ] || { echo "Cancelled."; exit 0; }
  elif [ ${#found[@]} -gt 0 ] && [ $yes = 0 ]; then
    [ -t 0 ] || { echo "No terminal to ask; use -y." >&2; exit 1; }
    read -rp "Continue? [y/N] " r; [[ $r == [yY]* ]] || { echo "Cancelled."; exit 0; }
  fi

  [ ${#found[@]} -eq 0 ] || rm -rf -- "${found[@]}"
  [ $all = 0 ] || { cd ..; rm -rf -- "$root"; }

  echo "Removed."
  [ $all = 1 ] || echo "Run ./run.sh to set it up again."
  if crontab -l 2>/dev/null | grep -q 'gmail.sh'; then
    echo "Reminder: a cron line runs ./gmail.sh. Remove it with: crontab -e"
  fi
  echo "Reminder: if you used the Gmail download, also remove the app at https://myaccount.google.com/permissions"
  exit 0
}
main "$@"

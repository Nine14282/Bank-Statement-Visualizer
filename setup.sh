#!/usr/bin/env bash
# One-time setup (safe to re-run; ./install.sh is the friendly front door): Python venv + packages, settings file. No Node.js needed: the dashboard page
# ships prebuilt (web/prebuilt/index.html) and Python fills in your data.
set -euo pipefail
cd "$(dirname "$0")"
umask 077   # files we create (ledger, token, dashboard, settings) are readable by you only

# Progress lines: "▸ step" (bold violet on a terminal), "  ✓ result". Each slow step says what it does first.
if [ -t 1 ]; then B=$'\033[1;35m'; G=$'\033[32m'; N=$'\033[0m'; else B= G= N=; fi
say() { printf '%s▸%s %s\n' "$B" "$N" "$*"; }
ok()  { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1. $2" >&2; exit 1; }; }
say "Checking for Python 3.10+"
need python3 "Install Python 3.10 or newer."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10+ is required." >&2; exit 1; }
ok "$(python3 --version)"

# Linux: the environment also sees the system's Python packages, for the app window's GTK/WebKit bindings (python3-gi
# can't be pip-installed without compilers). Re-running on an existing .venv just switches that on; nothing is lost.
sys_pkgs=; [ "$(uname -s)" = Linux ] && sys_pkgs=--system-site-packages
if [ -d .venv ]; then
  python3 -m venv $sys_pkgs .venv
  ok "Python environment already there (.venv)"
else
  say "Creating the Python environment (.venv)"
  python3 -m venv $sys_pkgs .venv
  ok "created"
fi
say "Installing Python packages (pdfplumber, Google sign-in, app window, ...): about a minute the first time"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
cp requirements.txt .venv/requirements.installed   # run.sh reinstalls when this differs from requirements.txt
ok "Python packages ready"

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

# One click to the dashboard: a launcher that runs ./run.sh --app. Linux: an app-menu entry (outside this folder, so
# it asks first; re-runs refresh it without asking, which also fixes the path after moving the folder). macOS: a file
# in this folder to double-click.
case "$(uname -s)" in
  Linux)
    desk="${XDG_DATA_HOME:-$HOME/.local/share}/applications/statement-visualizer.desktop"
    if [ -f "$desk" ] || { [ -t 0 ] && read -rp "Add Statement Visualizer to your app menu? [Y/n] " r && [[ $r != [nN]* ]]; }; then
      mkdir -p "$(dirname "$desk")"
      # ponytail: the path is quoted, not escaped; a project path containing " $ ` or \ breaks the launcher
      cat > "$desk" <<DESK
[Desktop Entry]
Type=Application
Name=Statement Visualizer
Comment=Your bank statements dashboard (local, offline)
Exec="$PWD/run.sh" --app
Icon=x-office-spreadsheet
Terminal=false
Categories=Office;Finance;
DESK
      ok "App menu: search \"Statement Visualizer\" (to remove: rm $desk)"
    elif [ ! -t 0 ]; then
      echo "  (No terminal to ask, so no app-menu launcher. Run ./install.sh in a terminal to add it.)"
    fi
    .venv/bin/python -c "import webview.platforms.gtk" 2>/dev/null ||
      echo "  (No app window here, so the launcher opens your browser. For the window, Debian/Ubuntu: sudo apt install python3-gi gir1.2-webkit2-4.1)" ;;
  Darwin)
    printf '#!/usr/bin/env bash\ncd "$(dirname "$0")" && exec ./run.sh --app\n' > "Statement Visualizer.command"
    chmod 700 "Statement Visualizer.command"
    ok "Double-click \"Statement Visualizer.command\" in this folder to open the dashboard" ;;
esac

cat <<MSG

Setup done. From now on everything happens in the app: Statement Visualizer in your app menu, or ./run.sh.
  First time: it walks you through adding statements, passwords, a theme and your expected spending.
  Later: Add statements (top bar) for new PDFs, the gear for settings.
  ./gmail.sh          optional: download statements from Gmail, then build (see README for the Google setup)
No app window possible here? ./run.sh opens the same pages in your browser instead.
Updating from an older version? Run one update (Add statements, Update) so the ledger gets the new Bank column.
MSG

# Open the app now (the first-time setup runs in it), unless ./install.sh or ./run.sh called this (SV_NO_OPEN: the
# first installs only, the second opens the app itself) or nobody is at the terminal. Detached: this terminal can be closed.
if [ -t 0 ] && [ -z "${SV_NO_OPEN:-}" ]; then
  say "Opening the app"
  nohup ./run.sh --app >/dev/null 2>&1 &
fi

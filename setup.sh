#!/usr/bin/env bash
# One-time setup (safe to re-run; ./install.sh is the friendly front door): Python venv + packages, settings file. No Node.js needed: the dashboard page
# ships prebuilt (web/prebuilt/index.html) and Python fills in your data.
#   ./setup.sh [--app|--web]   --app: app window (pywebview + launcher); --web: browser only. Default: the mode already
#                              installed (.venv/mode), else app.
set -euo pipefail
cd "$(dirname "$0")"
mode=app; [ ! -r .venv/mode ] || mode=$(cat .venv/mode)
for a in "$@"; do
  case "$a" in
    --app|--web) mode=${a#--} ;;
    *) echo "usage: ./setup.sh [--app|--web]" >&2; exit 2 ;;
  esac
done
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

if [ -d .venv ] && grep -qs '^include-system-site-packages = true' .venv/pyvenv.cfg; then
  # An older install let it see the system's packages (the old GTK window's python3-gi), and pip skipped whatever the
  # system had. Start it clean, so it has everything it needs on its own; the packages are installed again below.
  say "Rebuilding the Python environment (.venv) on its own"
  python3 -m venv --clear .venv
  ok "rebuilt"
elif [ -d .venv ]; then
  python3 -m venv .venv
  ok "Python environment already there (.venv)"
else
  say "Creating the Python environment (.venv)"
  python3 -m venv .venv
  ok "created"
fi
if [ "$mode" = app ] && [ "$(uname -s)" = Linux ]; then
  say "Installing Python packages (pdfplumber, Google sign-in, the app window's Qt web view: a ~200 MB download): a few minutes the first time"
else
  say "Installing Python packages (pdfplumber, Google sign-in$([ "$mode" = app ] && echo ', app window'), ...): about a minute the first time"
fi
reqs=(requirements.txt); [ "$mode" = app ] && reqs+=(requirements-app.txt)
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
# The app window's packages may fail without failing the install: a computer with no ready-made Qt package (32-bit ARM,
# an old glibc) would otherwise try to compile Qt. Then app.py finds no window and run.sh uses the browser pages.
if [ "$mode" = app ] && ! .venv/bin/python -m pip install --quiet \
    --only-binary=PyQt6,PyQt6-Qt6,PyQt6-sip,PyQt6-WebEngine,PyQt6-WebEngine-Qt6 -r requirements-app.txt; then
  echo "  (The app window's package didn't install here, so the app opens in your browser. Run ./install.sh to try again.)"
fi
cat "${reqs[@]}" > .venv/requirements.installed   # run.sh reinstalls when this differs from the requirements files
echo "$mode" > .venv/mode
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
case "$mode-$(uname -s)" in
  app-Linux)
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
    if ! .venv/bin/python -c "import PyQt6.QtWebEngineWidgets" 2>/dev/null; then
      echo "  (Qt's web view doesn't load here, so the launcher opens your browser. See \"App window\" in README.md.)"
    elif [ "${XDG_SESSION_TYPE:-}" != wayland ] && ! .venv/bin/python -c 'import ctypes.util, sys; sys.exit(not ctypes.util.find_library("xcb-cursor"))'; then
      echo "  (No app window on this X11 desktop yet, so the launcher opens your browser. For the window: sudo apt install libxcb-cursor0)"
    fi ;;
  app-Darwin)
    printf '#!/usr/bin/env bash\ncd "$(dirname "$0")" && exec ./run.sh --app\n' > "Statement Visualizer.command"
    chmod 700 "Statement Visualizer.command"
    ok "Double-click \"Statement Visualizer.command\" in this folder to open the dashboard" ;;
esac

if [ "$mode" = web ]; then
  cat <<MSG

Setup done (browser mode). Run ./run.sh: it opens the setup and add-statements pages in your browser.
  First time: it walks you through adding statements, passwords, a theme and your expected spending.
  Leave that terminal open while you use the page; the dashboard opens in your browser when it is built.
  ./gmail.sh          optional: download statements from Gmail, then build (see README for the Google setup)
  Want the app window instead? ./install.sh --app
MSG
  exit 0
fi

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

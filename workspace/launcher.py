#!/usr/bin/env python3
"""The project's commands, the same on Linux, macOS and Windows: install, setup, run, gmail, clear, uninstall.

The .sh files (Linux, macOS) and .cmd files (Windows) at the project root only find a Python and call this with the
command's name, so each command's behaviour lives here once. Standard library only, and no project module is imported:
it runs before .venv exists, with whatever Python the wrapper found. The workspace scripts run in .venv's Python.

  launcher.py install [--app|--web]   set up without opening anything (./install.sh, install.cmd)
  launcher.py setup [--app|--web]     the same, then opens the app (./setup.sh)
  launcher.py run [options]           ./run.sh, run.cmd: see run_cmd()
  launcher.py gmail [options]         ./gmail.sh, gmail.cmd: fetch_gmail.py's options
  launcher.py clear [-y]              ./clear.sh, clear.cmd
  launcher.py uninstall [--all] [-y] [-n]   ./uninstall.sh, uninstall.cmd
"""
import os
import re
import shutil
import subprocess
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is required (this is %d.%d). Get it from https://www.python.org/downloads/"
             % sys.version_info[:2])

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
VPY = os.path.join(".venv", "Scripts", "python.exe") if WIN else os.path.join(".venv", "bin", "python")
TTY_IN = bool(sys.stdin) and sys.stdin.isatty()
LINK_NAME = "statement-visualizer"   # the Linux app-menu entry; app.py names its window and Qt folders the same

os.chdir(ROOT)
# Every Python started from here reads and prints UTF-8: Thai descriptions would crash on a Windows console's code page.
os.environ["PYTHONUTF8"] = "1"
if WIN:
    os.system("")   # turns on colour codes in a Windows console (this one and every script run in it)
else:
    os.umask(0o077)   # files we create (ledger, token, dashboard, settings) are readable by you only

# Progress lines: "▸ step" (bold violet on a terminal), "  ✓ result". Each slow step says what it does first.
COLOUR = sys.stdout.isatty()
B, G, N = ("\033[1;35m", "\033[32m", "\033[0m") if COLOUR else ("", "", "")


def say(msg):
    print(f"{B}▸{N} {msg}", flush=True)


def ok(msg):
    print(f"  {G}✓{N} {msg}", flush=True)


def cmd(name):
    """How to type one of the project's commands here: run.cmd on Windows, ./run.sh elsewhere."""
    return f"{name}.cmd" if WIN else f"./{name}.sh"


def ask(question):
    try:
        return input(question)
    except EOFError:
        return ""


def py(*args, quiet=False):
    """Run a workspace script (or python -m ...) in .venv's Python; its exit code. Ctrl+C reaches it too."""
    try:
        return subprocess.call([VPY, *args], stdout=subprocess.DEVNULL if quiet else None)
    except KeyboardInterrupt:
        return 130


def reqs(mode):
    return ["requirements.txt"] + (["requirements-app.txt"] if mode == "app" else [])


def reqs_text(mode):
    """The mode's requirements files as one text: kept in .venv after a good install, compared on every run."""
    return b"".join(open(r, "rb").read() for r in reqs(mode))


def installed_mode():
    try:
        return open(os.path.join(".venv", "mode"), encoding="utf-8").read().strip() or None
    except OSError:
        return None


# --- install / setup -----------------------------------------------------------------------------------------------

def setup(args, open_after=True):
    """Python venv + packages, settings file, blank dashboard, launcher. Safe to re-run. No Node.js needed: the dashboard
    page ships prebuilt (web/prebuilt/index.html) and Python fills in your data. --app: app window (pywebview, and the
    launcher); --web: browser only. Default: the mode already installed, else app (web on Windows: the app window
    there isn't ready yet)."""
    mode = installed_mode() or ("web" if WIN else "app")
    for a in args:
        if a not in ("--app", "--web"):
            sys.exit(f"usage: {cmd('install')} [--app|--web]")
        mode = a[2:]

    say("Checking for Python 3.10+")
    ok(f"Python {sys.version.split()[0]}")

    cfg = os.path.join(".venv", "pyvenv.cfg")
    try:
        system_pkgs = "include-system-site-packages = true" in open(cfg, encoding="utf-8").read()
    except OSError:
        system_pkgs = False
    try:
        if system_pkgs:
            # An older install let it see the system's packages (the old GTK window's python3-gi), and pip skipped
            # whatever the system had. Start it clean, so it has everything it needs on its own.
            say("Rebuilding the Python environment (.venv) on its own")
            subprocess.check_call([sys.executable, "-m", "venv", "--clear", ".venv"])
            ok("rebuilt")
        elif os.path.isdir(".venv"):
            subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
            ok("Python environment already there (.venv)")
        else:
            say("Creating the Python environment (.venv)")
            subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
            ok("created")
    except subprocess.CalledProcessError:
        sys.exit("Couldn't create the Python environment."
                 + (" Debian/Ubuntu: sudo apt install python3-venv, then again." if LINUX else ""))

    if mode == "app" and LINUX:
        say("Installing Python packages (pdfplumber, Google sign-in, the app window's Qt web view: a ~200 MB "
            "download): a few minutes the first time")
    else:
        say(f"Installing Python packages (pdfplumber, Google sign-in{', app window' if mode == 'app' else ''}, ...): "
            "about a minute the first time")
    if subprocess.call([VPY, "-m", "pip", "install", "--quiet", "--upgrade", "pip"]) or \
            subprocess.call([VPY, "-m", "pip", "install", "--quiet", "-r", "requirements.txt"]):
        sys.exit(f"Installing the packages failed (no internet?). Run {cmd('install')} again.")
    # The app window's packages may fail without failing the install: a computer with no ready-made Qt package (32-bit
    # ARM, an old glibc) would otherwise try to compile Qt. Then app.py finds no window and run uses the browser pages.
    if mode == "app" and subprocess.call([VPY, "-m", "pip", "install", "--quiet",
                                          "--only-binary=PyQt6,PyQt6-Qt6,PyQt6-sip,PyQt6-WebEngine,PyQt6-WebEngine-Qt6",
                                          "-r", "requirements-app.txt"]):
        print("  (The app window's package didn't install here, so the app opens in your browser. "
              f"Run {cmd('install')} to try again.)")
    with open(os.path.join(".venv", "requirements.installed"), "wb") as f:
        f.write(reqs_text(mode))   # run reinstalls when this differs from the requirements files
    with open(os.path.join(".venv", "mode"), "w", encoding="utf-8") as f:
        f.write(mode + "\n")
    ok("Python packages ready")

    say("Preparing folders and your private settings file")
    os.makedirs("Statement", exist_ok=True)
    if not os.path.exists(".env"):
        shutil.copyfile(".env.example", ".env")
        os.chmod(".env", 0o600)
        print("Created .env from .env.example (private, git-ignored).")
    else:
        # Settings added by newer versions (e.g. KTB_PW, KBANK_PW) go in blank; existing values are never touched.
        text = open(".env", encoding="utf-8").read()
        keys = re.findall(r"^([A-Z_]+)=", open(".env.example", encoding="utf-8").read(), re.M)
        added = [k for k in keys if not re.search(rf"^{k}=", text, re.M)]
        if added:
            with open(".env", "a", encoding="utf-8") as f:
                f.write(("" if not text or text.endswith("\n") else "\n") + "".join(f"{k}=\n" for k in added))
            print(f"Added new settings to .env (blank, fill them in): {' '.join(added)}")
    ok("Statement/ folder and settings ready")

    # With no data yet it is a blank "No data yet" page that explains the next steps.
    say("Building the dashboard page")
    if py(os.path.join("workspace", "build_dashboard.py")):
        sys.exit("Building the dashboard page failed (see above).")

    if mode == "app":
        make_launcher()

    run = cmd("run")
    if mode == "web":
        print(f"""
Setup done (browser mode). Run {run}: it opens the setup and add-statements pages in your browser.
  First time: it walks you through adding statements, passwords, a theme and your expected spending.
  Leave that terminal open while you use the page; the dashboard opens in your browser when it is built.
  {cmd('gmail'):<18}  optional: download statements from Gmail, then build (see README for the Google setup)
  Want the app window instead? {cmd('install')} --app""")
        return 0
    print(f"""
Setup done. From now on everything happens in the app: {'Statement Visualizer in your app menu, or ' if LINUX else ''}{run}.
  First time: it walks you through adding statements, passwords, a theme and your expected spending.
  Later: Add statements (top bar) for new PDFs, the gear for settings.
  {cmd('gmail'):<18}  optional: download statements from Gmail, then build (see README for the Google setup)
No app window possible here? {run} opens the same pages in your browser instead.
Updating from an older version? Run one update (Add statements, Update) so the ledger gets the new Bank column.""")
    # Open the app now (the first-time setup runs in it), unless install or run called this (open_after: the first
    # installs only, the second opens the app itself) or nobody is at the terminal. Detached: this terminal can close.
    if open_after and TTY_IN:
        say("Opening the app")
        detach([sys.executable, os.path.abspath(__file__), "run", "--app"])
    return 0


def detach(argv):
    """Start a process that outlives this one and this terminal."""
    if WIN:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(argv, creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


def desktop_entry():
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
                        "applications", f"{LINK_NAME}.desktop")


def make_launcher():
    """One click to the dashboard, a launcher that runs run --app. Linux: an app-menu entry (outside this folder, so it
    asks first; re-runs refresh it without asking, which also fixes the path after moving the folder). macOS: a file in
    this folder to double-click. Windows: none yet (the app window there is the next step)."""
    if LINUX:
        desk = desktop_entry()
        if os.path.exists(desk) or (TTY_IN and not ask("Add Statement Visualizer to your app menu? [Y/n] ").lower()
                                    .startswith("n")):
            os.makedirs(os.path.dirname(desk), exist_ok=True)
            # ponytail: the path is quoted, not escaped; a project path containing " $ ` or \ breaks the launcher
            with open(desk, "w", encoding="utf-8") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=Statement Visualizer
Comment=Your bank statements dashboard (local, offline)
Exec="{os.path.join(ROOT, 'run.sh')}" --app
Icon=x-office-spreadsheet
Terminal=false
Categories=Office;Finance;
""")
            ok(f'App menu: search "Statement Visualizer" (to remove: rm {desk})')
        elif not TTY_IN:
            print(f"  (No terminal to ask, so no app-menu launcher. Run {cmd('install')} in a terminal to add it.)")
        if subprocess.call([VPY, "-c", "import PyQt6.QtWebEngineWidgets"], stderr=subprocess.DEVNULL):
            print("  (Qt's web view doesn't load here, so the launcher opens your browser. See \"App window\" in "
                  "README.md.)")
        elif os.environ.get("XDG_SESSION_TYPE") != "wayland" and subprocess.call(
                [VPY, "-c", 'import ctypes.util, sys; sys.exit(not ctypes.util.find_library("xcb-cursor"))']):
            print("  (No app window on this X11 desktop yet, so the launcher opens your browser. For the window: "
                  "sudo apt install libxcb-cursor0)")
    elif MAC:
        name = "Statement Visualizer.command"
        with open(name, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env bash\ncd "$(dirname "$0")" && exec ./run.sh --app\n')
        os.chmod(name, 0o700)
        ok(f'Double-click "{name}" in this folder to open the dashboard')


# --- run -----------------------------------------------------------------------------------------------------------

def run_cmd(args):
    """Option 1 (manual): statement PDFs -> ledger.csv -> web/dist/index.html

      run                 the app: its own window with the dashboard, Add statements and Settings, or the first-time
                          setup when there's no ledger yet. Installs what's missing first. No window possible here? The
                          same setup or add-statements pages open in the browser
      run --web           the browser pages instead of the app window (also the default after install --web)
      run --setup         the full setup page again, in the browser (in the app: the Settings button)
      run --app           the app, also with nobody at the terminal (what the launcher runs)
      run --rebuild       no browser: rebuild from the PDFs already in Statement/ (asks for a password in the terminal
                          if needed). Also what runs when nobody is at the terminal (a script)
      run --password=...  rebuild with this password (visible in shell history)
    """
    print(f"\n{B}Statement Visualizer{N}\n")
    flags = {a for a in args if a in ("--setup", "--rebuild", "--app", "--web")}
    rest = [a for a in args if a not in flags]   # e.g. --password=...: means a terminal rebuild
    setup_page, rebuild, app, web = ("--setup" in flags, "--rebuild" in flags, "--app" in flags, "--web" in flags)

    # .venv/mode: app or web (install --web = browser only, no pywebview). .venv/requirements.installed: the
    # requirements of the last good install; an update that changes them reinstalls here instead of failing quietly.
    mode = installed_mode() or ("web" if web or WIN else "app")
    if not os.path.exists(VPY):
        say("First run: installing what it needs (Python packages). This happens once and takes about a minute.")
        setup([f"--{mode}"], open_after=False)   # this command opens the app itself
        print()
    elif not os.path.exists(os.path.join(".venv", "requirements.installed")) or \
            open(os.path.join(".venv", "requirements.installed"), "rb").read() != reqs_text(mode):
        say("Updating the Python packages (requirements changed). This takes about a minute.")
        setup([f"--{mode}"], open_after=False)
        print()
    if app and mode == "web":
        sys.exit(f"Installed without the app window. Run {cmd('install')} --app to add it (or {cmd('run')} for the "
                 "browser).")

    ledger = os.path.join("workspace", "ledger.csv")
    # The app (launcher, or a person at the terminal): the dashboard, or the first-time setup with no ledger yet; it
    # adds statements and changes settings itself. Exit 3 = no window possible here: the browser pages below instead.
    if not (setup_page or rebuild or web or rest) and mode == "app" and (app or TTY_IN):
        py(os.path.join("workspace", "build_dashboard.py"), quiet=True)   # a pull may bring a newer page
        say("Opening the app")
        code = py(os.path.join("workspace", "app.py"))
        # 3 = app.py found no window possible (also how abort() ends on Windows); 134 = Qt aborted (Linux, macOS)
        if code not in (3, 134):
            return code
        say("No app window here (see README); using the browser instead")
        if app and os.path.exists(ledger):   # the launcher: just show the dashboard
            import pathlib
            import webbrowser
            webbrowser.open(pathlib.Path("web", "dist", "index.html").resolve().as_uri())
            return 0
    welcome = os.path.join("workspace", "welcome.py")
    if setup_page or not os.path.exists(ledger):
        say("Opening the setup page (--setup)" if setup_page else "No ledger yet: opening the setup page")
        return py(welcome)
    # No app window: a person at the terminal gets the add-statements page; --rebuild, --password= or a script with no
    # terminal rebuild here.
    if not rebuild and not rest and TTY_IN:
        say(f"Opening the page to add new statements ({cmd('run')} --rebuild skips it)")
        return py(welcome, "--add")

    os.makedirs("Statement", exist_ok=True)
    if not any(n.lower().endswith(".pdf") for n in os.listdir("Statement")):
        sys.exit(f"No PDFs in Statement/. Run {cmd('run')} to add statements on a page, or copy them there and run "
                 f"{cmd('run')} --rebuild.")
    say("Reading the statements in Statement/ and rebuilding your ledger")
    code = py(os.path.join("workspace", "update_statement.py"), *rest)
    if code:
        return code
    print()
    say(f"Done. Dashboard: double-click Dashboard.html in {ROOT}")
    return 0


# --- gmail ---------------------------------------------------------------------------------------------------------

def gmail(args):
    """Option 2: download new statement PDFs from Gmail into Statement/, then rebuild the dashboard. Read-only Gmail
    access; the first run opens a browser once to authorise (README has the Google setup). Options: --no-build (only
    download), --listen (keep running: fetch + build within seconds of new mail; README "Real time"). --listen has
    nobody to type PDF passwords: put KTB_PW / KBANK_PW in .env first, and run gmail once by hand to authorise."""
    if not os.path.exists(VPY):
        sys.exit(f"Not set up yet. Run {cmd('install')} first.")
    os.makedirs("Statement", exist_ok=True)
    code = py(os.path.join("workspace", "fetch_gmail.py"), *args)
    if not code:
        print(f"Dashboard: double-click Dashboard.html in {ROOT}")
    return code


# --- clear ---------------------------------------------------------------------------------------------------------

def clear(args):
    """Reset all your data, as on a fresh clone; the installed app stays (.venv, the launcher, the code). Deletes your
    statement PDFs, the ledger and manual entries, the dashboard page (it holds your transactions inline), the statement
    cache, the saved Gmail login and "seen" list, your expected spending, and what the app window saved (labels,
    theme, size); resets the settings file to the blank template; rebuilds the blank dashboard. -y: don't ask
    (--all is accepted and means the same). Not removed: the app (uninstall) and the access you gave Google (revoke it
    at https://myaccount.google.com/permissions). Labels saved in a browser live in that browser."""
    yes = False
    for a in args:
        if a == "-y":
            yes = True
        elif a != "--all":
            sys.exit(f"usage: {cmd('clear')} [-y]")
    data = [os.path.join("Statement", n) for n in sorted(os.listdir("Statement")) if n.lower().endswith(".pdf")] \
        if os.path.isdir("Statement") else []
    data += [os.path.join("workspace", n) for n in sorted(os.listdir("workspace")) if n.endswith(".csv")]
    data += [p for p in (os.path.join("workspace", n) for n in ("expected.json", "token.json", "credentials.json",
                                                                 ".gmail_seen.json", ".cache", ".app"))
             if os.path.exists(p)]
    data += [p for p in (os.path.join("web", "src", "data"), os.path.join("web", "dist", "index.html"))
             if os.path.exists(p)]
    print("Will delete:")
    print("\n".join(f"  {p}" for p in data) if data else "  (no data files found)")
    print("Will reset to the blank template: your settings file (passwords, Google client id/secret, name, theme)")
    print("Kept: the installed app (.venv, launcher) and the code.")
    if not yes and not ask("Continue? [y/N] ").lower().startswith("y"):
        print("Cancelled.")
        return 0
    for p in data:
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    if os.path.exists(".env.example"):
        shutil.copyfile(".env.example", ".env")
        os.chmod(".env", 0o600)
    elif os.path.exists(".env"):
        os.remove(".env")
    # The blank page needs only the standard library, so it is rebuilt even after uninstall removed the .venv.
    builder = VPY if os.path.exists(VPY) else sys.executable
    if subprocess.call([builder, os.path.join("workspace", "build_dashboard.py")]):
        print(f"Cleared, but the blank dashboard was not rebuilt: run {cmd('install')}.", file=sys.stderr)
        return 0
    print("Cleared. It is now like a fresh install: open the app to set up again.")
    return 0


# --- uninstall -----------------------------------------------------------------------------------------------------

def uninstall(args):
    """Remove what install set up: the launcher, .venv, web/node_modules and the generated dashboard (and on Linux the
    app window's Qt folders). Keeps your PDFs, ledger, .env and Gmail login; run sets everything up again.
    --all: also delete this whole project folder (PDFs, ledger, saved passwords, Gmail login). No undo; asks you to
    type the folder name first. -y: skip the "Continue?" question of the plain removal. -n: only list. Not done for you:
    the access you gave Google (README)."""
    all_, yes, dry = False, False, False
    for a in args:
        if a == "--all":
            all_ = True
        elif a == "-y":
            yes = True
        elif a == "-n":
            dry = True
        else:
            sys.exit(f"usage: {cmd('uninstall')} [--all] [-y] [-n]")
    if not (os.path.exists("run.sh") and os.path.exists(os.path.join("workspace", "extract_ledger.py"))):
        sys.exit("This is not the Statement Visualizer folder.")
    if os.path.abspath(ROOT) in (os.path.abspath(os.sep), os.path.expanduser("~")):
        sys.exit(f"Refusing to remove {ROOT}.")

    items = [".venv", os.path.join("web", "node_modules"), os.path.join("web", "dist"), "Dashboard.html",
             "Statement Visualizer.command"]
    if LINUX:   # outside this folder: the app-menu entry (install), the app window's Qt cache and default profile
        items = [desktop_entry(),
                 os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), LINK_NAME),
                 os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), LINK_NAME),
                 ] + items
    found = [p for p in items if os.path.lexists(p)]
    print("Will delete:\n" + "\n".join(f"  {p}" for p in found) if found else "Nothing installed to remove.")
    if all_:
        pdfs = sum(n.lower().endswith(".pdf") for n in os.listdir("Statement")) if os.path.isdir("Statement") else 0
        print(f"\nAND the whole folder {ROOT}, including:\n"
              f"  Statement/ ({pdfs} PDF), workspace/ (ledger, saved Gmail login), .env (saved passwords, Gmail secret)")
    else:
        print("Kept: Statement/, workspace/ (ledger), .env, the code.")
    if dry:
        print("(-n: nothing was deleted)")
        return 0

    name = os.path.basename(ROOT)
    if all_:
        print("\nThis cannot be undone.")
        if not TTY_IN:
            sys.exit("--all needs a terminal to confirm.")
        if ask(f"Type the folder name ({name}) to delete everything: ") != name:
            print("Cancelled.")
            return 0
    elif found and not yes:
        if not TTY_IN:
            sys.exit("No terminal to ask; use -y.")
        if not ask("Continue? [y/N] ").lower().startswith("y"):
            print("Cancelled.")
            return 0

    for p in found:
        shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    if all_:
        os.chdir(os.path.dirname(ROOT))
        # Windows may keep this command's own .cmd file open a moment: whatever is left is named, not hidden.
        shutil.rmtree(ROOT, ignore_errors=True)
        if os.path.exists(ROOT):
            print(f"Some files couldn't be removed (in use?): delete {ROOT} by hand.")
    print("Removed.")
    if not all_:
        print(f"Run {cmd('run')} to set it up again.")
    if shutil.which("crontab") and "gmail.sh" in subprocess.run(["crontab", "-l"], capture_output=True,
                                                                text=True).stdout:
        print("Reminder: a cron line runs ./gmail.sh. Remove it with: crontab -e")
    print("Reminder: if you used the Gmail download, also remove the app at https://myaccount.google.com/permissions")
    return 0


COMMANDS = {"install": lambda a: setup(a, open_after=False), "setup": setup, "run": run_cmd, "gmail": gmail,
            "clear": clear, "uninstall": uninstall}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: launcher.py {{{'|'.join(COMMANDS)}}} [options]")
    try:
        sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
    except KeyboardInterrupt:
        sys.exit(130)

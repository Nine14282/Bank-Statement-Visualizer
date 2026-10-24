#!/usr/bin/env python3
"""The app: the dashboard in its own window, what ./run.sh and the app-menu launcher open. With no ledger yet it runs
the first-time setup itself; Add statements and Settings (the full setup again) open over the dashboard.

Shows web/dist/index.html through pywebview: on Linux in Qt's web view (PyQt6 + QtWebEngine, i.e. Chromium; pip
packages, nothing from apt), on macOS in the system's WebKit, on Windows in WebView2 (Edge's engine, part of Windows;
the .exe build's window). The page's own saved settings (labels, expected spending, theme, seen rows) live in
workspace/.app/ on Linux and Windows, apart from any browser's (macOS keeps them in WebKit's default store: pywebview
ignores storage_path there).
New mail updates the open window by itself: this checks Gmail at start (or runs the real-time listener) and, when it
reports a rebuild, tells the page to swap the new data in (no polling, no reload). Add statements and Settings open right in the
window (Api below). The window has almost no animation (?app, see
DESIGN.md "Desktop app window"); only new rows slide in. No web view (PyQt6 missing, an X11 desktop without
libxcb-cursor0, or Windows without the WebView2 runtime)? Exits with 3 and run.sh opens the same app in the browser
(welcome.py) instead.
Usage: python app.py
"""

import base64
import contextlib
import json
import os
import sys
import threading
from pathlib import Path

import config  # loads the project's env settings into os.environ

PAGE = Path(config.ROOT) / "web" / "dist" / "index.html"
STORE = os.path.join(config.WORK, ".app")  # the window's browser storage (Linux, Windows)
# Where the window kept the page's localStorage before Qt (WebKitGTK, until 2026-10). Moved over once, then renamed.
WEBKIT_STORE = os.path.join(STORE, "localstorage", "file__0.localstorage")


RAISE = os.path.join(STORE, "raise")  # a second launch asks the open app to come to the front (only_window)
WINDOW = os.path.join(STORE, "window.json")  # the window's size and maximized state, kept between runs
THEME_MODE = os.path.join(STORE, "theme")  # light or dark: what the page showed last (Api.theme)


def start_colour() -> str:
    """The window's own colour, seen before the page paints at startup: its theme's --background (index.css) instead of
    white. The theme the page showed last (switched in the window too), else the THEME setting.
    ponytail: one colour per light/dark mode; a theme with its own --background needs its colour here."""
    try:
        with open(THEME_MODE, encoding="utf-8") as f:
            mode = f.read().strip()
    except OSError:
        mode = "dark" if os.environ.get("THEME") == "midnight" else "light"
    return "#f2f2f6" if mode == "light" else "#0a080b"


def our_page() -> bool:
    """Whether the window still shows our own page. pywebview hands the bridge to whatever page the window loads, and
    a file dropped outside a drop zone would load that file (main.tsx stops those drops; this is the backstop). The
    paths are compared decoded: Qt reports the address decoded, as_uri() encodes spaces and Thai letters."""
    from urllib.parse import unquote, urlsplit

    import webview

    shown, ours = urlsplit(webview.windows[0].get_current_url() or ""), urlsplit(PAGE.as_uri())
    same = os.path.normcase  # Windows: C:/ and c:/ name the same file
    return shown.scheme == "file" and same(unquote(shown.path)) == same(unquote(ours.path))


class Api:
    """Add statements and Settings in this window (App.tsx opens the wizard over the dashboard) call
    window.pywebview.api.call() instead of welcome.py's server: same handlers, no port, no login link. PDFs arrive base64-encoded."""

    def save(self, name: str, text: str) -> bool:
        """Export CSV (shell.tsx): the page's own download doesn't work in the window (pywebview leaves downloads off),
        so this asks where to save it and writes there. Only ever the file the person picked in the dialog."""
        import webview

        if not our_page():
            return False
        home = os.path.expanduser("~")
        folder = os.path.join(home, "Downloads")
        picked = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=os.path.basename(name),
            directory=folder if os.path.isdir(folder) else home,
        )
        if not picked:
            return False  # cancelled
        with open(picked if isinstance(picked, str) else picked[0], "w", encoding="utf-8", newline="") as f:
            f.write(text)  # text starts with a BOM already (toCsv), for Excel
        return True

    def theme(self, mode: str) -> None:
        """The theme mode the page shows (themes.ts), for the next start's colour (start_colour)."""
        if mode in ("light", "dark"):
            with open(THEME_MODE, "w", encoding="utf-8") as f:
                f.write(mode)

    def call(self, path: str, name: str = "", data=None) -> dict:
        import welcome  # pdfplumber & co. load on the first call, not at every app start

        if path == "/api/progress":
            return dict(welcome.PROGRESS)  # no LOCK: finish holds it while the build runs
        if not our_page():
            return {"error": "This page can't change your statements."}
        import webview

        if path == "/api/clear":
            stop_gmail(wait=True)  # its log is part of what gets deleted (and Windows won't delete a file open in it)
        try:
            body = base64.b64decode(data or "") if path == "/api/upload" else json.dumps(data or {}).encode()
            if len(body) > welcome.MAX_PDF:
                return {"error": "That file is over 30 MB."}
            with welcome.LOCK:
                welcome.scan(quiet=True)  # statements dropped into Statement/ since the last call
                out = welcome.handle(path, name or "statement.pdf", body)
        except ValueError as e:  # bad input, as the HTTP server answers 400
            return {"error": str(e)}
        if out is None:
            return {"error": f"Unknown request {path}."}
        if path in ("/api/gmail", "/api/google") and os.environ.get("GMAIL_TOPIC"):
            start_gmail(webview.windows[0])  # real time just set up, or signed in with its permission now
        if path == "/api/clear" and out.get("ok"):
            # the page clears its own storage and says goodbye first; the next start is a fresh setup
            threading.Timer(2, webview.windows[0].destroy).start()
        return out


def no_window_reason() -> str | None:
    """Linux: why Qt couldn't open a window here, checked before Qt tries (it aborts the whole process instead of
    raising). Its X11 plugin needs libxcb-cursor0, missing on many desktops; Wayland sessions don't use it."""
    # Qt's own choice: the session type, unless QT_QPA_PLATFORM says otherwise
    platform = os.environ.get("QT_QPA_PLATFORM") or (
        "wayland" if os.environ.get("XDG_SESSION_TYPE") == "wayland" else "xcb"
    )
    if platform.startswith("xcb"):
        import ctypes.util

        if not ctypes.util.find_library("xcb-cursor"):
            return "Qt needs libxcb-cursor0 on an X11 desktop (Debian/Ubuntu: sudo apt install libxcb-cursor0)"
    return None


def show_console(show: bool) -> None:
    """Windows, started by a double-click or the Start Menu (launcher.py sets SV_HIDE_CONSOLE): the console window that
    opened with it isn't needed once the app window is up, so it hides then, and shows again if the app fails, so the
    error can be read. A hard crash of the web view never gets here: launcher.py shows it again then."""
    if os.name == "nt" and os.environ.get("SV_HIDE_CONSOLE"):
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5 if show else 0)  # SW_SHOW, SW_HIDE


def prepare_page(window, colour: str) -> None:
    """Linux, before the page is shown (pywebview's before_show):
    - the web view's own colour before a page paints (Qt's default is white; pywebview only colours the window);
    - its own answer to permission requests. pywebview 6.2.1's passes a plain int where PyQt6 wants an enum, and the
      TypeError inside a Qt slot aborts the whole app: the first navigator.clipboard call (Copy in the transaction
      drawer) closed the window. This grants the clipboard to our own page and denies the rest (pywebview granted
      mic and camera, which nothing here uses)."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from webview.platforms.qt import BrowserView

    # ponytail: pywebview internals; re-check after pywebview upgrades (drop the permission part once it's fixed there)
    page = BrowserView.instances[window.uid].webview.page()
    page.setBackgroundColor(QColor(colour))
    P = QWebEnginePage.PermissionPolicy

    def answer(origin, feature):
        ok = feature == QWebEnginePage.Feature.ClipboardReadWrite and origin.scheme() == "file"
        page.setFeaturePermission(origin, feature, P.PermissionGrantedByUser if ok else P.PermissionDeniedByUser)

    page.featurePermissionRequested.disconnect()
    page.featurePermissionRequested.connect(answer)


def move_webkit_storage(window) -> None:
    """Once, after the first page load in Qt: copy the page's saved settings (ledger-* keys: theme, labels, expected
    spending, seen rows) from the old WebKitGTK window, then rename that file so it never runs again. The old values
    win over anything the page just wrote (its defaults); the page reloads to read them. Runs on every load
    (pywebview's loaded event) and returns at once when there is nothing to move."""
    import sqlite3

    if not os.path.exists(WEBKIT_STORE):
        return
    with sqlite3.connect(f"file:{WEBKIT_STORE}?mode=ro", uri=True) as db:  # WebKit keeps values as UTF-16 text
        items = {
            k: bytes(v).decode("utf-16-le")
            for k, v in db.execute("SELECT key, value FROM ItemTable")
            if k.startswith("ledger-")
        }
    if items:
        window.evaluate_js(f"(o => {{ for (const k in o) localStorage.setItem(k, o[k]) }})({json.dumps(items)})")
    os.replace(WEBKIT_STORE, WEBKIT_STORE + ".moved")  # only after the copy: a failed one is tried again next start
    if items:
        window.evaluate_js("location.reload()")


GMAIL: dict = {"proc": None}  # the Gmail fetch or listener this window started


def start_gmail(window) -> None:
    """Gmail while the window is open. With GMAIL_TOPIC set (README "Real time"), fetch_gmail.py --listen runs in the
    background; else, once signed in to Gmail (token.json, from Fetch from Gmail), one fetch at start brings in what
    arrived while the app was closed. Their output (senders, amounts) goes to workspace/.app/gmail-listen.log, private
    and git-ignored, through a pipe read here: a "Dashboard updated." line (fetch_gmail.UPDATED) makes the page load the
    new data at once. Does nothing while one still runs.
    ponytail: the log only grows, a few lines per email; rotate it once it passes about 1 MB."""
    if GMAIL["proc"] and GMAIL["proc"].poll() is None:
        return
    if os.environ.get("GMAIL_TOPIC"):
        args: tuple = ("--listen",)
    elif (
        os.environ.get("GOOGLE_CLIENT_ID")
        and os.environ.get("GOOGLE_CLIENT_SECRET")
        and os.path.exists(os.path.join(config.WORK, "token.json"))
    ):
        args = ()
    else:
        return
    import subprocess

    os.makedirs(STORE, exist_ok=True)
    listener = GMAIL["proc"] = subprocess.Popen(
        config.script("fetch_gmail", *args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    def relay():  # until the listener exits (its pipe closes)
        with open(os.path.join(STORE, "gmail-listen.log"), "a", encoding="utf-8") as log:
            for line in listener.stdout:
                log.write(line)
                log.flush()
                if line.strip() == "Dashboard updated.":
                    # the page is loading or the window closing: it shows the new build anyway
                    with contextlib.suppress(Exception):
                        window.evaluate_js("window.__ledgerUpdate && window.__ledgerUpdate()")

    threading.Thread(target=relay, daemon=True).start()


def stop_gmail(wait: bool = False) -> None:
    """Linux, macOS: it finishes a fetch or rebuild in progress, then stops by itself; Windows ends it at once.
    wait: until it has (at most 30 s), e.g. before its files are deleted."""
    if GMAIL["proc"]:
        GMAIL["proc"].terminate()
        if wait:
            with contextlib.suppress(Exception):
                GMAIL["proc"].wait(30)


def only_window(on_raise):
    """One app at a time, the window or the app in the browser (welcome.py): a second one would share the first's storage
    (workspace/.app/), get no live updates (one Gmail listener runs) and could build at the same time. Returns the lock,
    held while this process runs; on_raise() then runs whenever a later launch asks for the app. None when another one
    has it: that one is asked to come to the front instead, and the caller just exits."""
    os.makedirs(STORE, exist_ok=True)
    lock = open(os.path.join(STORE, "window.lock"), "a")  # not "w": Windows won't truncate a file another one locked
    if config.lock(lock, wait=False):
        with contextlib.suppress(OSError):
            os.remove(RAISE)  # a request left from before
        threading.Thread(target=watch_raise, args=(on_raise,), daemon=True).start()
        return lock
    lock.close()
    if os.name == "nt":
        import ctypes

        # This launch is the user's click, so it may hand the foreground on: the open app can come to the front.
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    open(RAISE, "w").close()
    return None


def watch_raise(on_raise) -> None:
    """ponytail: looks for a raise request once a second; a local socket if this ever shows up in a profile."""
    import time

    while True:
        time.sleep(1)
        if os.path.exists(RAISE):
            with contextlib.suppress(OSError):
                os.remove(RAISE)
            with contextlib.suppress(Exception):  # e.g. the window is closing
                on_raise()


def bring_forward(w, shown: dict) -> None:
    """The open window to the front: un-minimized (restore() only then: it would also un-maximize), shown and
    activated (pywebview: Qt raises and activates; Windows shows and activates)."""
    if shown["minimized"]:
        w.restore()
    w.show()


def window_state() -> dict:
    """The size and maximized state the window had when it was last closed (window.json), else the defaults."""
    try:
        with open(WINDOW, encoding="utf-8") as f:
            s = json.load(f)
        return {
            "width": max(400, int(s["width"])),
            "height": max(500, int(s["height"])),
            "maximized": s.get("maximized") is True,
        }
    except (OSError, ValueError, KeyError, TypeError):  # none yet, or unreadable: start fresh
        return {"width": 1280, "height": 820, "maximized": False}


def keep_window_state(w, state: dict) -> None:
    """Track maximize/restore, and save the size on close. A maximized window keeps the size it had before, so
    un-maximizing next time goes back to it. Linux only: on macOS reading the size inside closing deadlocks (both
    run on the main thread). ponytail: no position (Wayland ignores it) and no screen-size clamp; add the clamp if
    a window ever opens bigger than the screen (a size saved on a larger monitor)."""
    w.events.maximized += lambda: state.update(maximized=True)
    w.events.restored += lambda: state.update(maximized=False)

    def closing():
        if not state["maximized"]:
            state.update(width=w.width, height=w.height)
        try:
            with open(WINDOW, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except OSError:
            pass  # the size just isn't kept

    w.events.closing += closing


def main() -> int:
    url = PAGE.as_uri()
    linux = sys.platform.startswith("linux")
    window: dict = {}  # filled in once the window exists; a raise request before that is ignored
    shown = {"minimized": False}
    lock = only_window(lambda: bring_forward(window["w"], shown))  # held until main() returns
    if not lock:
        print("Statement Visualizer is already open: it was asked to come to the front.", file=sys.stderr)
        return 0
    try:
        if linux:
            reason = no_window_reason()
            if reason:
                raise RuntimeError(reason)
            os.environ.setdefault("QT_API", "pyqt6")  # pywebview reaches Qt through QtPy: never a system PyQt5
            from PyQt6.QtWidgets import QApplication

            # Same name as the launcher's .desktop file, so the dock shows the window under the launcher's icon. Also
            # names Qt's small cache folder (~/.cache/statement-visualizer; uninstall.sh removes it).
            QApplication.setApplicationName("statement-visualizer")
            QApplication.setDesktopFileName("statement-visualizer")
        import webview

        if os.name == "nt":
            # Without the WebView2 runtime pywebview falls back to Internet Explorer's engine, which can't run the page
            from webview.platforms import winforms

            if winforms.renderer != "edgechromium":
                raise RuntimeError("the Microsoft Edge WebView2 Runtime isn't installed")
        bg = start_colour()
        state = window_state()
        w = webview.create_window(
            "Statement Visualizer",
            url + "?app",
            width=state["width"],
            height=state["height"],
            maximized=state["maximized"],
            min_size=(400, 500),
            js_api=Api(),
            background_color=bg,
            text_select=True,
            zoomable=True,
        )  # select + Ctrl+C, and Ctrl+wheel zoom, as in a tab
        window["w"] = w
        w.events.minimized += lambda: shown.update(minimized=True)
        w.events.restored += lambda: shown.update(minimized=False)
        w.events.maximized += lambda: shown.update(minimized=False)
        if linux:
            keep_window_state(w, state)
            w.events.before_show += lambda window: prepare_page(window, bg)
            w.events.loaded += move_webkit_storage
        w.events.shown += lambda: show_console(False)
        try:
            # Gmail starts once the GUI is up (webview.start's func): Qt aborts the process when it can't open a
            # window, and a listener started before that would be left running with nobody to stop it.
            # Never ship debug=True, settings["REMOTE_DEBUGGING_PORT"] or http_server=True here: each opens a local
            # port (or the "Save page" menu) through which any program on this computer could read the whole ledger
            # in the page and drive Api (save passwords, add statements). Links to other sites need target="_blank":
            # a page opened in this window gets Api too (our_page() refuses it).
            webview.start(
                lambda: start_gmail(w),
                gui="qt" if linux else None,
                private_mode=False,
                storage_path=STORE,
            )
        finally:
            stop_gmail()
    except Exception as e:  # ImportError, or pywebview finding no GUI toolkit
        show_console(True)
        print(f"No app window ({type(e).__name__}: {e}).", file=sys.stderr)
        return 3  # run.sh: the app in the browser instead
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

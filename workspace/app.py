#!/usr/bin/env python3
"""The app: the dashboard in its own window, what ./run.sh and the app-menu launcher open. With no ledger yet it runs
the first-time setup itself; Add statements and Settings (the full setup again) open over the dashboard.

Shows web/dist/index.html in the system's web view through pywebview (WebKitGTK on Linux, WebKit on macOS). The page's
own saved settings (labels, expected spending, theme, seen rows) live in workspace/.app/ on Linux, apart from any
browser's (macOS keeps them in WebKit's default store: pywebview ignores storage_path there).
An open window reloads by itself after a rebuild, as a browser tab does. Add statements opens the add page right in
the window (Api below). The window has no animation (?app, see
DESIGN.md "Desktop app window"): WebKitGTK stutters on them. No web view (pywebview missing, or on Linux the
python3-gi / gir1.2-webkit2-4.1 packages)? Exits with 3 and run.sh opens the browser pages instead. Usage: python app.py
"""
import base64
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = Path(HERE).parent / "web" / "dist" / "index.html"


class Api:
    """The add-statements page in this window (Add statements → ?app&setup&add) calls window.pywebview.api.call()
    instead of welcome.py's server: same handlers, no port, no login link. PDFs arrive base64-encoded."""

    def call(self, path: str, name: str = "", data=None) -> dict:
        import welcome          # pdfplumber & co. load on the first call, not at every app start
        if path == "/api/progress":
            return dict(welcome.PROGRESS)   # no LOCK: finish holds it while the build runs
        try:
            body = base64.b64decode(data or "") if path == "/api/upload" else json.dumps(data or {}).encode()
            if len(body) > welcome.MAX_PDF:
                return {"error": "That file is over 30 MB."}
            with welcome.LOCK:
                welcome.scan(quiet=True)   # statements dropped into Statement/ since the last call
                out = welcome.handle(path, name or "statement.pdf", body)
        except ValueError as e:   # bad input, as the HTTP server answers 400
            return {"error": str(e)}
        return out if out is not None else {"error": f"Unknown request {path}."}


def main_thread_scrolling(window) -> None:
    """Linux: scroll on the page's own thread. WebKitGTK scrolls on a separate thread, and the sticky top bar, moved by
    the page's thread, lags behind it and shakes. Runs before the page loads (pywebview's before_show)."""
    from gi.repository import WebKit2
    from webview.platforms.gtk import BrowserView
    view = BrowserView.instances[window.uid].webview   # ponytail: pywebview internal; re-check after pywebview upgrades
    features = WebKit2.Settings.get_all_features()       # WebKitGTK 2.42+; older ones fail here and keep the default
    for i in range(features.get_length()):
        f = features.get(i)
        if f.get_identifier() in ("ThreadedScrolling", "AsyncFrameScrolling", "AsyncOverflowScrolling"):
            view.get_settings().set_feature_enabled(f, False)


def main() -> int:
    url = PAGE.as_uri()
    try:
        import webview
        if sys.platform.startswith("linux"):
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import GLib
            # Same name as the launcher's .desktop file, so the dock shows the window under the launcher's icon.
            GLib.set_prgname("statement-visualizer")
            from gi.repository import Gtk
            # WebKitGTK reports prefers-reduced-motion from this: CSS keyframes, charts and count-ups stand still.
            Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
        import config   # the settings file, for THEME
        # The window's own colour, seen before a page paints (startup, add page <-> dashboard): the theme's --background
        # (index.css) instead of pywebview's white. ponytail: picked from THEME; a theme switched in the window isn't seen.
        bg = "#f2f2f6" if os.environ.get("THEME") == "daylight" else "#0a080b"
        w = webview.create_window("Statement Visualizer", url + "?app", width=1280, height=820, min_size=(400, 500),
                                  js_api=Api(), background_color=bg)
        if sys.platform.startswith("linux"):
            w.events.before_show += main_thread_scrolling
        # The Linux tweaks above are GTK-only; pywebview would pick Qt on KDE or with PYWEBVIEW_GUI=qt.
        webview.start(gui="gtk" if sys.platform.startswith("linux") else None, private_mode=False,
                      storage_path=os.path.join(HERE, ".app"))
    except Exception as e:   # ImportError, or pywebview finding no GUI toolkit
        print(f"No app window ({type(e).__name__}: {e}).", file=sys.stderr)
        return 3             # run.sh: use the browser pages instead
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

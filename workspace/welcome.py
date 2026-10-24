#!/usr/bin/env python3
"""The app in the browser, for when no app window is possible here (app.py exits with 3), and the full setup page.
run.sh / the launcher start it; the app window (app.py) calls handle() below directly, without this server.

  python welcome.py          the browser app: the dashboard, with Add statements and Settings working in the page
                             (the first-time setup when there is no ledger yet). Stops by itself a few minutes after
                             the page is gone (IDLE)
  python welcome.py --setup  only the full setup page (run --setup); stops once it has built the dashboard

A small local server serves the dashboard page (?web for the app, ?setup for the setup page; the React app shows
the wizard or the dashboard from that, web/src/components/setup/wizard.tsx) and answers its API calls:

  GET  /api/state            banks, statements in Statement/, the current theme and expected spending, Gmail settings
  GET  /api/ping             the open page says it is still there (every 30 s)
  POST /api/upload?name=X    body = one PDF: saved into Statement/, its bank detected
  POST /api/remove           {name}: delete a file uploaded in this session (never an older one)
  POST /api/bank             {name, bank}: the user says which bank a file is from
  POST /api/gmail            download new statements (and payment notices) from Gmail into Statement/; the first
                             time it opens Google's sign-in in the browser. Offered only when the Google keys are set
  POST /api/google           {id, secret, project, topic, subscription}: the Gmail settings, into the settings file
  POST /api/password         {bank, password, remember}: opens and parses that bank's locked files with it
  POST /api/folder           open the data folder (Statement/, workspace/) in the file manager
  POST /api/clear            {confirm: "DELETE"}: delete all your data (launcher.py clear), then this app closes
  POST /api/finish           {theme, plan}: save the choices (each only if sent), build the ledger + dashboard; the
                             setup page then opens it and stops
  GET  /api/progress         what the build is doing ({stage, done, total}), polled by the page while it runs

Only this computer can reach it (127.0.0.1, port PORT). The printed link carries a random one-time token: the
first visit swaps it for an HttpOnly, SameSite=Strict cookie and redirects to a clean URL, so a copy of the link
(e.g. read from the browser's command line in `ps` by another user of this computer) is already spent. Every
later request needs that cookie plus an X-Setup header other sites can't send. Passwords are kept in memory unless
"remember" saves them to the settings file. Usage: python welcome.py [--setup]
"""

import contextlib
import io
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pdfplumber

import config  # loads the project's env settings into os.environ
import update_statement
from build_dashboard import EXPECTED, OUT, build
from extract_ledger import BANKS, BY_ID, bank_from_name, bank_from_text, extract
from update_statement import candidates

MARK = "\033[1;35m▸\033[0m" if sys.stdout.isatty() else "▸"  # as in run.sh: bold violet on a terminal


def say(msg: str) -> None:
    """Progress line: "▸ step"."""
    print(f"{MARK} {msg}", flush=True)


def note(msg: str) -> None:
    print(f"  {msg}", flush=True)


STATEMENTS = os.path.join(config.ROOT, "Statement")
SETUP = "--setup" in sys.argv[1:]  # only the full setup page, not the browser app
# Fixed, so the page keeps one address: a browser keeps what the page saves (labels, expected spending, theme) per
# address, port included. Taken by something else: any free port, and that run's page starts from the defaults.
PORT = 47613
IDLE = 180  # seconds without a word from the page, then the server stops (a hidden tab's timers slow to once a minute)
LAST = [time.monotonic()]  # when the page last asked anything
TOKEN = secrets.token_urlsafe(24)  # one-time: in the printed link, good for the first visit only
SESSION = secrets.token_urlsafe(32)  # the cookie that visit gets; never printed or put in a URL
TOKEN_USED = threading.Event()
MAX_PDF = 30 * 1024 * 1024
FILES: dict[str, dict] = {}  # file name in Statement/ -> {bank, locked, ok, uploaded}
LOCK = threading.Lock()
# What finish() is doing, for the page's loader (/api/progress). Read without LOCK: finish() holds it while it runs.
PROGRESS = {"stage": "", "done": 0, "total": 0}
# Banks whose password is in the settings file: at start, plus any saved with "remember". A password used for
# this run only also sits in os.environ (for the build), so os.environ alone can't tell them apart.
SAVED = {b.id for b in BANKS if any(os.environ.get(k) for k in b.passwords)}


def detect(path: str) -> dict:
    """Bank and lock state of one PDF: opened with no password or a saved one if possible (then its page-1
    text names the bank), else the file name; None = ask the user."""
    rows = update_statement.cached(path)
    if rows is not None:  # read before (workspace/.cache): no need to open it, and no password needed
        return {"bank": rows[0].get("Bank") if rows else None, "locked": False, "ok": True}
    for pw in candidates(path):
        try:
            with pdfplumber.open(path, password=pw) as pdf:
                text = pdf.pages[0].extract_text() or ""
        except Exception:  # noqa: S112  # wrong password or not a PDF: try the next one
            continue
        b = bank_from_text(text) or bank_from_name(path)
        return {"bank": b.id if b else None, "locked": pw is not None, "ok": True}
    b = bank_from_name(path)
    return {"bank": b.id if b else None, "locked": True, "ok": False}


def scan(quiet: bool = False) -> None:
    """Pick up PDFs that appeared in Statement/ (already known names are skipped, so this is cheap to repeat)."""
    os.makedirs(STATEMENTS, exist_ok=True)
    for name in sorted(os.listdir(STATEMENTS)):
        if name.lower().endswith(".pdf") and name not in FILES:
            FILES[name] = {**detect(os.path.join(STATEMENTS, name)), "uploaded": False}
    if quiet:
        return
    locked = sum(not f["ok"] for f in FILES.values())
    note(
        f"{len(FILES)} PDF(s) already there" + (f", {locked} need a password" if locked else "")
        if FILES
        else "none yet"
    )


def state() -> dict:
    try:
        plan = json.load(open(EXPECTED, encoding="utf-8"))
    except (OSError, ValueError):
        plan = []
    return {
        "banks": [{"id": b.id, "name": b.name, "saved": b.id in SAVED} for b in BANKS],
        "files": [{"name": n, **f} for n, f in FILES.items()],
        "theme": os.environ.get("THEME", ""),
        "gmail": bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")),
        # the Gmail settings for their form: the secret only as "saved or not"
        "google": {k: bool(os.environ.get(v)) if k == "secret" else os.environ.get(v, "") for k, v in GOOGLE.items()},
        "folder": config.ROOT,
        "plan": plan,
    }


def safe_name(raw: str) -> str:
    name = re.sub(r"[^\w.() -]+", "_", os.path.basename(raw)).strip(" .") or "statement"
    return name if name.lower().endswith(".pdf") else name + ".pdf"


def upload(raw_name: str, data: bytes) -> dict:
    if not data.startswith(b"%PDF-"):
        raise ValueError("That file isn't a PDF.")
    name = safe_name(raw_name)
    stem, n = name[:-4], 2
    while os.path.exists(os.path.join(STATEMENTS, name)) and open(os.path.join(STATEMENTS, name), "rb").read() != data:
        name, n = f"{stem} ({n}).pdf", n + 1  # a different file with the same name: keep both
    path = os.path.join(STATEMENTS, name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    # Re-adding an identical file that was already in Statement/ must not make it removable from the page.
    FILES[name] = {**detect(path), "uploaded": FILES.get(name, {}).get("uploaded", True)}
    bank = BY_ID[FILES[name]["bank"]].name if FILES[name]["bank"] else "bank not recognised yet"
    note(f"added {name} ({bank})")
    return {"name": name, **FILES[name]}


def gmail() -> dict:
    import fetch_gmail  # Google's libraries load on the first press, not at every start

    say("Fetching new statements from Gmail…")
    try:
        got, notices = fetch_gmail.pull(interactive=True)
    except (SystemExit, OSError) as e:  # no keys / sign-in refused, network or Gmail API error
        raise ValueError(f"Gmail: {e}") from e
    scan(quiet=True)
    for path in got:  # new this session: listed on the add page like an upload
        FILES[os.path.basename(path)]["uploaded"] = True
    note(f"{len(got)} new statement(s), {notices} payment notice(s)")
    return {"files": len(got), "notices": notices}


# The Gmail settings the page can set (Settings, last step): its field -> the setting's name, and what each must look
# like (Google Cloud console values; a topic or subscription also as its full path, as the console copies it).
GOOGLE = {
    "id": "GOOGLE_CLIENT_ID",
    "secret": "GOOGLE_CLIENT_SECRET",
    "project": "GOOGLE_PROJECT_ID",
    "topic": "GMAIL_TOPIC",
    "subscription": "GMAIL_SUBSCRIPTION",
}
_NAME = r"[A-Za-z][\w.~+%-]{2,254}"
_PROJECT = r"[a-z][a-z0-9-]{4,29}"
GOOGLE_FORMAT = {
    "id": (r"[\w.-]+\.apps\.googleusercontent\.com", "client ID"),
    "secret": (r"[\w-]{10,100}", "client secret"),
    "project": (_PROJECT, "project ID"),
    "topic": (rf"(projects/{_PROJECT}/topics/)?{_NAME}", "topic"),
    "subscription": (rf"(projects/{_PROJECT}/subscriptions/)?{_NAME}", "subscription"),
}


def google(data: dict) -> dict:
    """Save the Gmail settings. A blank secret keeps the saved one; blank real-time fields turn real time off."""
    got = {k: str(data.get(k) or "").strip() for k in GOOGLE}
    for k, v in got.items():
        pattern, label = GOOGLE_FORMAT[k]
        if v and not re.fullmatch(pattern, v):
            raise ValueError(f"That {label} doesn't look right: copy it again from the Google Cloud console.")
    if not got["id"] or not (got["secret"] or os.environ.get(GOOGLE["secret"])):
        raise ValueError("Paste both the client ID and the client secret.")
    if any(got[k] for k in ("topic", "subscription")) and not all(got[k] for k in ("project", "topic", "subscription")):
        raise ValueError("Real time needs the project ID, the topic and the subscription.")
    for k, v in got.items():
        if v or k != "secret":
            config.save(GOOGLE[k], v)
    sys.modules.pop("fetch_gmail", None)  # it reads these when imported: the next Gmail fetch imports it afresh
    note("Gmail settings saved" + (" (real time on)" if got["topic"] else ""))
    return {"ok": True}


def show_folder() -> dict:
    """The data folder in the file manager: Statement/ (the PDFs), workspace/ (the ledger), the settings file."""
    if os.name == "nt":
        os.startfile(config.ROOT)  # noqa: S606  # our own folder, nothing from the page
    else:
        import subprocess

        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, config.ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
    return {"ok": True}


def wipe(confirm: str) -> dict:
    """Delete all your data with launcher.py's clear (the same list, by name), as a fresh install: PDFs, ledger,
    settings file, Gmail login. The app's own storage (workspace/.app/) is in use, so it stays: the page clears what it
    saved there itself, and this app closes afterwards (the window in app.py, the server in handle())."""
    import subprocess

    if confirm != "DELETE":
        raise ValueError("Type DELETE to confirm.")
    launcher = [sys.executable] if config.FROZEN else [sys.executable, os.path.join(config.HERE, "launcher.py")]
    say("Deleting all your data…")
    r = subprocess.run(  # noqa: S603
        [*launcher, "clear", "-y", "--in-app"], capture_output=True, encoding="utf-8", errors="replace"
    )
    sys.stdout.write(r.stdout + r.stderr)
    if r.returncode:
        raise ValueError(f"Not everything could be deleted. {(r.stderr or r.stdout).strip()[-400:]}")
    FILES.clear()
    SAVED.clear()
    return {"ok": True}


def unlock(bank: str, password: str, remember: bool) -> dict:
    """Try one password on every locked file of a bank: it must open and parse each of them."""
    if bank not in BY_ID:
        raise ValueError("Unknown bank.")
    names = [n for n, f in FILES.items() if f["bank"] == bank and not f["ok"]]
    if not names:  # nothing locked to check it against: don't keep or save an unchecked password
        return {"ok": True, "files": 0, "rows": 0}
    bad, rows = [], 0
    for n in names:
        path, buf = os.path.join(STATEMENTS, n), io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                got = extract(path, password)
        except Exception:
            bad.append(n)
            continue
        update_statement.remember(path, got, buf.getvalue())  # the update then takes it from the cache: one read
        rows += len(got)
    if bad:
        note(f"{BY_ID[bank].name}: that password didn't open {len(bad)} file(s)")
        return {"ok": False, "bad": bad}
    for n in names:
        FILES[n]["ok"] = True
    key = BY_ID[bank].passwords[0]
    if remember:
        config.save(key, password)  # also sets os.environ
        SAVED.add(bank)
    else:
        os.environ[key] = password  # this run only: the build at "finish" uses it
    note(
        f"{BY_ID[bank].name}: unlocked {len(names)} file(s), {rows} transactions"
        + (" (password saved in the settings file)" if remember else " (password kept for this run only)")
    )
    return {"ok": True, "files": len(names), "rows": rows}


def clean_plan(plan) -> list:
    out = []
    for i in (plan or [])[:100]:
        name = str(i.get("name", "")).strip()[:80]
        amount = float(i.get("amount", 0))
        if name and 0 <= amount < 1e9 and i.get("every") in ("day", "month"):
            item = {
                "id": str(i.get("id", ""))[:40] or secrets.token_hex(4),
                "name": name,
                "amount": round(amount, 2),
                "every": i["every"],
            }
            if i.get("key"):
                item["key"] = str(i["key"])[:300]
            out.append(item)
    return out


def finish(server, theme: str, plan) -> dict:
    if theme:
        if not re.fullmatch(r"[a-z0-9-]{1,30}", theme):
            raise ValueError("Bad theme.")
        config.save("THEME", theme)
    if plan is not None:  # the add page sends none: the saved list stays as it is
        fd = os.open(EXPECTED, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean_plan(plan), f, ensure_ascii=False)
        say(f"Saved your choices (theme: {theme or 'default'}, {len(clean_plan(plan))} expected-spending item(s))")
    say("Reading your statements and building the ledger and dashboard…")
    PROGRESS.update(stage="start", done=0, total=0)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = update_statement.main(
                progress=lambda stage, done=0, total=0: PROGRESS.update(stage=stage, done=done, total=total)
            )
        except SystemExit as e:  # e.g. a file no known password opens
            print(e)
            code = 1
    PROGRESS.update(stage="failed" if code else "done")
    log = buf.getvalue()
    sys.stdout.write(log)
    if code:
        say("The build stopped; the page shows why. Fix it there and press Try again.")
        return {"ok": False, "log": log[-3000:]}
    if server is None or not SETUP:  # the app (window or browser) goes back to the dashboard itself
        for f in FILES.values():  # its next add page lists only files added after this update
            f["uploaded"] = False
        say("Done. The dashboard is rebuilt.")
        return {"ok": True, "dashboard": OUT, "log": log[-1500:]}
    say(f"Done. Opening your dashboard: {OUT}")
    # Done: open the dashboard (a file on disk, which a web page can't link to) and stop the server.
    threading.Timer(0.8, lambda: (webbrowser.open(Path(OUT).as_uri()), server.shutdown())).start()
    return {"ok": True, "dashboard": OUT, "log": log[-1500:]}


def handle(path: str, name: str, body: bytes, server=None) -> dict | None:
    """One call from the setup/add page: over HTTP (Handler below) or straight from the app window (app.py).
    Bad input raises ValueError, which the page shows; an unknown path returns None. Call it holding LOCK."""
    if path == "/api/state":
        return state()
    if path == "/api/upload":
        return upload(name, body)
    data = json.loads(body or b"{}")
    if path == "/api/remove":
        name = str(data.get("name", ""))
        if not FILES.get(name, {}).get("uploaded"):
            raise ValueError("Only files added in this setup can be removed here.")
        os.remove(os.path.join(STATEMENTS, name))
        del FILES[name]
        return {"ok": True}
    if path == "/api/bank":
        name, bank = str(data.get("name", "")), str(data.get("bank", ""))
        if name not in FILES or bank not in BY_ID:
            raise ValueError("Unknown file or bank.")
        FILES[name]["bank"] = bank
        return {"ok": True}
    if path == "/api/gmail":
        return gmail()
    if path == "/api/password":
        return unlock(str(data.get("bank", "")), str(data.get("password", "")), bool(data.get("remember")))
    if path == "/api/google":
        return google(data)
    if path == "/api/folder":
        return show_folder()
    if path == "/api/clear":
        out = wipe(str(data.get("confirm", "")))
        if server:  # the page says goodbye first (app.py closes the window itself)
            threading.Timer(2, server.shutdown).start()
        return out
    if path == "/api/finish":
        return finish(server, str(data.get("theme", "")), data.get("plan"))
    return None


class Server(ThreadingHTTPServer):
    """The page's server, its port for this program alone. SO_REUSEADDR on Windows lets another program (another
    account's too) bind the same 127.0.0.1 port and take the one-time link's visit: off there, and Windows gets
    SO_EXCLUSIVEADDRUSE. Elsewhere it only lets PORT be bound again right after the last run closed it."""

    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version = "LedgerSetup"

    def log_message(self, *args):  # quiet: no request lines in the terminal
        pass

    def allowed(self) -> bool:
        LAST[0] = time.monotonic()  # the page is still there (IDLE)
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")  # no DNS rebinding

    def cookie_name(self) -> str:
        return f"sv_setup_{self.server.server_address[1]}"  # cookies ignore ports: keep each run's apart

    def signed_in(self) -> bool:
        jar = SimpleCookie(self.headers.get("Cookie") or "")
        got = jar[self.cookie_name()].value if self.cookie_name() in jar else ""
        return secrets.compare_digest(got, SESSION)

    def api_ok(self) -> bool:
        # cookie (only the browser that opened the link has it) + a custom header (forces a CORS preflight, which
        # this server never grants, so no other site can make a request that carries the cookie)
        return self.allowed() and self.signed_in() and self.headers.get("X-Setup") == "1"

    def send(self, code: int, body: bytes, kind: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code: int = 200) -> None:
        self.send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        url = urlparse(self.path)
        if not self.allowed():
            return self.send(403, b"forbidden", "text/plain")
        if url.path == "/":
            given = parse_qs(url.query).get("setup", [""])[0]
            if given and secrets.compare_digest(given, TOKEN) and not TOKEN_USED.is_set():
                TOKEN_USED.set()  # first visit: swap the link's token for a cookie, then drop it from the URL
                self.send_response(303)
                self.send_header("Set-Cookie", f"{self.cookie_name()}={SESSION}; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Location", "/?setup" if SETUP else "/?web")
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return None
            if self.signed_in():
                return self.send(200, open(OUT, "rb").read(), "text/html; charset=utf-8")
            return self.send(
                403,
                b"This link has already been used (or is wrong). Open Statement Visualizer again for a new one.",
                "text/plain",
            )
        if url.path == "/api/state" and self.api_ok():
            with LOCK:
                scan(quiet=True)  # statements dropped into Statement/ meanwhile (Open data folder), as in app.py
                return self.json(state())
        if url.path == "/api/progress" and self.api_ok():
            return self.json(dict(PROGRESS))  # no LOCK: finish() holds it while the build runs
        if url.path == "/api/ping" and self.api_ok():
            return self.send(204, b"", "text/plain")  # allowed() noted the time
        self.send(404, b"not found", "text/plain")

    def do_POST(self):
        url = urlparse(self.path)
        if not self.api_ok():
            return self.send(403, b"forbidden", "text/plain")
        size = int(self.headers.get("Content-Length") or 0)
        if size < 0:
            return self.json({"error": "Bad request."}, 400)
        if size > MAX_PDF:
            return self.json({"error": "That file is over 30 MB."}, 413)
        body = self.rfile.read(size)
        try:
            with LOCK:
                scan(quiet=True)
                out = handle(url.path, parse_qs(url.query).get("name", ["statement.pdf"])[0], body, self.server)
        except ValueError as e:
            return self.json({"error": str(e)}, 400)
        if out is None:
            return self.send(404, b"not found", "text/plain")
        self.json(out)


def make_server() -> Server:
    try:
        return Server(("127.0.0.1", PORT), Handler)
    except OSError:  # taken
        return Server(("127.0.0.1", 0), Handler)


def stop_when_idle(server) -> None:
    """The page pings every 30 s while it is open (main.tsx); a few minutes without a word, and it is gone."""
    while time.monotonic() - LAST[0] < IDLE:
        time.sleep(10)
    say("The page has been closed for a few minutes: stopping. Open Statement Visualizer again to use it.")
    server.shutdown()


def link(server) -> str:
    """A fresh one-time link: each opens the page once (a later launch of the app gets its own, see main)."""
    global TOKEN
    TOKEN = secrets.token_urlsafe(24)
    TOKEN_USED.clear()
    return f"http://127.0.0.1:{server.server_address[1]}/?setup={TOKEN}"


def main() -> int:
    import app  # its one-app-at-a-time lock and console helper; nothing that needs a web view

    server = None
    # Another launch while this runs (the app menu, the Start Menu): a new tab of this same page.
    lock = app.only_window(lambda: server and webbrowser.open(link(server)))
    if not lock:
        print("Statement Visualizer is already open: it was asked to open its page again.")
        return 0
    page = "The setup page" if SETUP else "Statement Visualizer"
    say("Building the page (it is part of the dashboard)")
    build()  # make sure web/dist/index.html (which holds the wizard) is current
    say("Looking at the statements already in Statement/")
    scan()
    server = make_server()
    url = link(server)
    say(f"{page} is ready (this computer only). Opening it in your browser…")
    note(f"If it didn't open, go to: {url}")
    note("What you do there is logged below. This stops by itself a few minutes after you close the page.")
    threading.Thread(target=stop_when_idle, args=(server,), daemon=True).start()
    if webbrowser.open(url):
        app.show_console(False)  # Windows, a double-click: nothing to do in this window (only if the page did open)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        say("Closed. Open Statement Visualizer again to continue.")
        return 0
    print(f"Dashboard: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

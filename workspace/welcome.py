#!/usr/bin/env python3
"""First-run setup wizard. ./run.sh starts it on the first run (no ledger yet) or with --setup.

A small local server serves the dashboard page with ?setup, which shows the setup wizard instead of the
dashboard (web/src/components/setup/wizard.tsx), and answers its API calls:

  GET  /api/state            banks, statements in Statement/, the current theme and expected spending
  POST /api/upload?name=X    body = one PDF: saved into Statement/, its bank detected
  POST /api/remove           {name}: delete a file uploaded in this session (never an older one)
  POST /api/bank             {name, bank}: the user says which bank a file is from
  POST /api/password         {bank, password, remember}: opens and parses that bank's locked files with it
  POST /api/finish           {theme, plan}: save the choices, build the ledger + dashboard, open it, stop

Only this computer can reach it (127.0.0.1, random port). The printed link carries a random one-time token: the
first visit swaps it for an HttpOnly, SameSite=Strict cookie and redirects to a clean URL, so a copy of the link
(e.g. read from the browser's command line in `ps` by another user of this computer) is already spent. Every
later request needs that cookie plus an X-Setup header other sites can't send. Passwords are kept in memory unless
"remember" saves them to the settings file. Usage: python welcome.py
"""
import contextlib
import io
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import config  # loads the project's env settings into os.environ
import pdfplumber
from build_dashboard import EXPECTED, OUT, build
from extract_ledger import BANKS, BY_ID, bank_from_name, bank_from_text, extract
import update_statement
from update_statement import candidates

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "\033[1;35m▸\033[0m" if sys.stdout.isatty() else "▸"   # as in run.sh: bold violet on a terminal


def say(msg: str) -> None:
    """Progress line: "▸ step"."""
    print(f"{MARK} {msg}", flush=True)


def note(msg: str) -> None:
    print(f"  {msg}", flush=True)
STATEMENTS = os.path.join(os.path.dirname(HERE), "Statement")
TOKEN = secrets.token_urlsafe(24)       # one-time: in the printed link, good for the first visit only
SESSION = secrets.token_urlsafe(32)     # the cookie that visit gets; never printed or put in a URL
TOKEN_USED = threading.Event()
MAX_PDF = 30 * 1024 * 1024
FILES: dict[str, dict] = {}     # file name in Statement/ -> {bank, locked, ok, uploaded}
LOCK = threading.Lock()
# Banks whose password is in the settings file: at start, plus any saved with "remember". A password used for
# this run only also sits in os.environ (for the build), so os.environ alone can't tell them apart.
SAVED = {b.id for b in BANKS if any(os.environ.get(k) for k in b.passwords)}


def detect(path: str) -> dict:
    """Bank and lock state of one PDF: opened with no password or a saved one if possible (then its page-1
    text names the bank), else the file name; None = ask the user."""
    for pw in candidates(path):
        try:
            with pdfplumber.open(path, password=pw) as pdf:
                text = pdf.pages[0].extract_text() or ""
        except Exception:
            continue
        b = bank_from_text(text) or bank_from_name(path)
        return {"bank": b.id if b else None, "locked": pw is not None, "ok": True}
    b = bank_from_name(path)
    return {"bank": b.id if b else None, "locked": True, "ok": False}


def scan() -> None:
    os.makedirs(STATEMENTS, exist_ok=True)
    for name in sorted(os.listdir(STATEMENTS)):
        if name.lower().endswith(".pdf") and name not in FILES:
            FILES[name] = {**detect(os.path.join(STATEMENTS, name)), "uploaded": False}
    locked = sum(not f["ok"] for f in FILES.values())
    note(f"{len(FILES)} PDF(s) already there" + (f", {locked} need a password" if locked else "") if FILES else "none yet")


def state() -> dict:
    try:
        plan = json.load(open(EXPECTED, encoding="utf-8"))
    except (OSError, ValueError):
        plan = []
    return {
        "banks": [{"id": b.id, "name": b.name, "saved": b.id in SAVED} for b in BANKS],
        "files": [{"name": n, **f} for n, f in FILES.items()],
        "theme": os.environ.get("THEME", ""),
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
        name, n = f"{stem} ({n}).pdf", n + 1        # a different file with the same name: keep both
    path = os.path.join(STATEMENTS, name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    FILES[name] = {**detect(path), "uploaded": True}
    bank = BY_ID[FILES[name]["bank"]].name if FILES[name]["bank"] else "bank not recognised yet"
    note(f"added {name} ({bank})")
    return {"name": name, **FILES[name]}


def unlock(bank: str, password: str, remember: bool) -> dict:
    """Try one password on every locked file of a bank: it must open and parse each of them."""
    if bank not in BY_ID:
        raise ValueError("Unknown bank.")
    names = [n for n, f in FILES.items() if f["bank"] == bank and not f["ok"]]
    if not names:                      # nothing locked to check it against: don't keep or save an unchecked password
        return {"ok": True, "files": 0, "rows": 0}
    bad, rows = [], 0
    for n in names:
        try:
            rows += len(extract(os.path.join(STATEMENTS, n), password))
        except Exception:
            bad.append(n)
    if bad:
        note(f"{BY_ID[bank].name}: that password didn't open {len(bad)} file(s)")
        return {"ok": False, "bad": bad}
    for n in names:
        FILES[n]["ok"] = True
    key = BY_ID[bank].passwords[0]
    if remember:
        config.save(key, password)     # also sets os.environ
        SAVED.add(bank)
    else:
        os.environ[key] = password     # this run only: the build at "finish" uses it
    note(f"{BY_ID[bank].name}: unlocked {len(names)} file(s), {rows} transactions"
         + (" (password saved in the settings file)" if remember else " (password kept for this run only)"))
    return {"ok": True, "files": len(names), "rows": rows}


def clean_plan(plan) -> list:
    out = []
    for i in (plan or [])[:100]:
        name = str(i.get("name", "")).strip()[:80]
        amount = float(i.get("amount", 0))
        if name and 0 <= amount < 1e9 and i.get("every") in ("day", "month"):
            item = {"id": str(i.get("id", ""))[:40] or secrets.token_hex(4), "name": name, "amount": round(amount, 2),
                    "every": i["every"]}
            if i.get("key"):
                item["key"] = str(i["key"])[:300]
            out.append(item)
    return out


def finish(server, theme: str, plan) -> dict:
    if theme:
        if not re.fullmatch(r"[a-z0-9-]{1,30}", theme):
            raise ValueError("Bad theme.")
        config.save("THEME", theme)
    fd = os.open(EXPECTED, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(clean_plan(plan), f, ensure_ascii=False)
    say(f"Saved your choices (theme: {theme or 'default'}, {len(clean_plan(plan))} expected-spending item(s))")
    say("Reading your statements and building the ledger and dashboard…")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = update_statement.main()
        except SystemExit as e:        # e.g. a file no known password opens
            print(e)
            code = 1
    log = buf.getvalue()
    sys.stdout.write(log)
    if code:
        say("The build stopped; the setup page shows why. Fix it there and press Try again.")
        return {"ok": False, "log": log[-3000:]}
    say(f"Done. Opening your dashboard: {OUT}")
    # Done: open the dashboard (a file on disk, which a web page can't link to) and stop the server.
    threading.Timer(0.8, lambda: (webbrowser.open(Path(OUT).as_uri()), server.shutdown())).start()
    return {"ok": True, "dashboard": OUT, "log": log[-1500:]}


class Handler(BaseHTTPRequestHandler):
    server_version = "LedgerSetup"

    def log_message(self, *args):   # quiet: no request lines in the terminal
        pass

    def allowed(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")   # no DNS rebinding

    def cookie_name(self) -> str:
        return f"sv_setup_{self.server.server_address[1]}"   # cookies ignore ports: keep each run's apart

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
                TOKEN_USED.set()       # first visit: swap the link's token for a cookie, then drop it from the URL
                self.send_response(303)
                self.send_header("Set-Cookie", f"{self.cookie_name()}={SESSION}; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Location", "/?setup")
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return None
            if self.signed_in():
                return self.send(200, open(OUT, "rb").read(), "text/html; charset=utf-8")
            return self.send(403, b"This setup link has already been used (or is wrong). Run ./run.sh --setup for a new one.",
                             "text/plain")
        if url.path == "/api/state" and self.api_ok():
            with LOCK:
                return self.json(state())
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
                if url.path == "/api/upload":
                    return self.json(upload(parse_qs(url.query).get("name", ["statement.pdf"])[0], body))
                data = json.loads(body or b"{}")
                if url.path == "/api/remove":
                    name = str(data.get("name", ""))
                    if not FILES.get(name, {}).get("uploaded"):
                        raise ValueError("Only files added in this setup can be removed here.")
                    os.remove(os.path.join(STATEMENTS, name))
                    del FILES[name]
                    return self.json({"ok": True})
                if url.path == "/api/bank":
                    name, bank = str(data.get("name", "")), str(data.get("bank", ""))
                    if name not in FILES or bank not in BY_ID:
                        raise ValueError("Unknown file or bank.")
                    FILES[name]["bank"] = bank
                    return self.json({"ok": True})
                if url.path == "/api/password":
                    return self.json(unlock(str(data.get("bank", "")), str(data.get("password", "")),
                                            bool(data.get("remember"))))
                if url.path == "/api/finish":
                    return self.json(finish(self.server, str(data.get("theme", "")), data.get("plan")))
        except ValueError as e:
            return self.json({"error": str(e)}, 400)
        self.send(404, b"not found", "text/plain")


def selfcheck() -> None:
    """python welcome.py --selfcheck: file names and the spending list are cleaned before use."""
    assert safe_name("../../etc/passwd") == "passwd.pdf"
    assert safe_name("My Statement (1).PDF") == "My Statement (1).PDF"
    assert safe_name("a;b|c.pdf") == "a_b_c.pdf"
    plan = clean_plan([{"name": " Lunch ", "amount": 120, "every": "day"}, {"name": "", "amount": 5, "every": "day"},
                       {"name": "Rent", "amount": -1, "every": "month"}, {"name": "X", "amount": 1, "every": "week"},
                       {"name": "Phone", "amount": "299.5", "every": "month", "key": "k"}])
    assert [(p["name"], p["amount"], p["every"]) for p in plan] == [("Lunch", 120, "day"), ("Phone", 299.5, "month")], plan
    assert plan[1]["key"] == "k" and "key" not in plan[0]
    print("selfcheck ok")


def main() -> int:
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
        return 0
    say("Building the setup page (it is part of the dashboard)")
    build()                 # make sure web/dist/index.html (which holds the wizard) is current
    say("Looking at the statements already in Statement/")
    scan()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/?setup={TOKEN}"
    say("Setup page is ready (this computer only). Opening it in your browser…")
    note(f"If it didn't open, go to: {url}")
    note("Leave this window open while you use the page. What you do there is logged below. Ctrl+C quits.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        say("Setup closed before finishing. Run ./run.sh --setup to continue.")
        return 0
    print(f"Dashboard: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

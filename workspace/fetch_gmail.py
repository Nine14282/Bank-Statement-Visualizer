#!/usr/bin/env python3
"""Pull bank statement PDFs and payment emails from Gmail into Statement/, then update.

Workflow: Gmail API -> find statement emails -> download new PDF attachments
into Statement/ -> run update_statement (merge -> ledger.csv -> dashboard).

Read-only access to Gmail is used; nothing is modified in your mailbox. Which
emails are imported is fixed per bank in banks/ (statement_mail, notice_mail): only
those senders and subjects, so nobody can mail a fake statement into the ledger.

One-time setup (see the notes printed if the .env keys are missing):
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create an OAuth client ID (type: Desktop app) and put its client id and
     secret in <project root>/.env as GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET.
  3. First run opens a browser to authorise; the token is cached in token.json.

Usage:
    python fetch_gmail.py            # fetch new statements + rebuild
    python fetch_gmail.py --no-build # only download, don't rebuild
    python fetch_gmail.py --listen   # keep running; fetch within seconds of new mail (Pub/Sub, see README)
"""

import base64
import csv
import html
import json
import os
import re
import sys
from collections import Counter

import config  # loads the project's env settings into os.environ
from banks import BANKS, manual_bank

# manual_entries.csv columns. Payment emails (each bank's parse_notice) go there: no PDF, outgoing only, no balance;
# once the statement has the same payment, update_statement keeps the statement row.
MANUAL = ["Date", "Description", "Category", "Amount", "Balance", "Bank"]

# Real-time mode (--listen): Gmail announces mailbox changes on this Pub/Sub topic and we pull them from the
# subscription. Both blank = off, and the sign-in stays Gmail read-only.
TOPIC = (os.environ.get("GMAIL_TOPIC") or "").rsplit("/", 1)[-1]  # also accepts the console's full path
SUBSCRIPTION = (os.environ.get("GMAIL_SUBSCRIPTION") or "").rsplit("/", 1)[-1]
PROJECT = os.environ.get("GOOGLE_PROJECT_ID") or ""
# The listener only searches recent mail (Gmail query syntax): each wake-up is cheap, and it never re-walks years of
# history. Older mail (listener off for longer) comes in with a plain ./gmail.sh, which searches everything.
LISTEN_WINDOW = "newer_than:7d"
UPDATED = "Dashboard updated."  # printed after a rebuild; the same text in app.py
RECENT = ""  # added to every search; --recent (the listener's per-email fetch) sets it

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
if TOPIC:
    SCOPES.append("https://www.googleapis.com/auth/pubsub")  # to pull the notifications from the subscription
# Three read-only GETs (list, get, attachment) over plain HTTPS: google-api-python-client would add ~100 MB of
# API discovery documents to the venv for them.
API = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
WATCH = "https://gmail.googleapis.com/gmail/v1/users/me/watch"
PUBSUB = "https://pubsub.googleapis.com/v1"

# Absolute paths (config.py), so it runs from any working directory.
HERE = config.WORK  # workspace/
ROOT = config.ROOT  # project root

OUTDIR = os.path.join(ROOT, "Statement")  # PDFs land in root/Statement
TOKEN = os.path.join(HERE, "token.json")
SEEN = os.path.join(HERE, ".gmail_seen.json")
LOCK = os.path.join(HERE, ".gmail.lock")  # one fetch at a time (pull)
LISTEN_LOCK = os.path.join(HERE, ".gmail-listen.lock")  # one listener at a time (listen)


def client_config():
    cid, secret = os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (cid and secret):
        sys.exit(SETUP_HELP)
    return {
        "installed": {
            "client_id": cid,
            "client_secret": secret,
            "project_id": os.environ.get("GOOGLE_PROJECT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }


def service(interactive=False):
    """interactive: a person is there to sign in (the setup page's button), even without a terminal."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
        if not set(SCOPES) <= set(json.load(open(TOKEN)).get("scopes", [])):
            print("The saved Gmail login lacks the Pub/Sub permission GMAIL_TOPIC needs — signing in again.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Refresh token revoked/expired (Google expires them after 7
                # days while the OAuth app is in "Testing"). Re-authorise.
                print("Saved login expired — opening browser to re-authorise.")
                creds = None
        if not creds or not creds.valid:
            if not (interactive or sys.stdin.isatty()):  # the listener: nobody to click through the browser
                sys.exit(
                    f"Gmail login missing or expired: run {config.command('gmail')} by hand once to sign in again."
                )
            flow = InstalledAppFlow.from_client_config(client_config(), SCOPES)
            creds = flow.run_local_server(port=0)
        fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
        os.chmod(TOKEN, 0o600)  # also tightens a token file created earlier with looser permissions
    session = AuthorizedSession(creds)  # refreshes the access token itself
    # Back off and retry on rate limits (429) and Google-side errors, which a big first run can hit.
    session.mount(
        "https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=(429, 500, 502, 503)))
    )
    return session


def api(svc, path="", **params):
    """GET one Gmail API resource as JSON."""
    r = svc.get(API + path, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def iter_attachments(payload):
    """Yield (filename, attachment_id) for every PDF part, recursively."""
    stack = [payload]
    while stack:
        part = stack.pop()
        for child in part.get("parts", []) or []:
            stack.append(child)
        name = part.get("filename") or ""
        body = part.get("body", {})
        if name.lower().endswith(".pdf") and body.get("attachmentId"):
            yield name, body["attachmentId"]


def message_ids(svc, query):
    """All message ids matching the query, following pagination."""
    ids, page = [], None
    while True:
        resp = api(svc, q=f"{query} {RECENT}".strip(), pageToken=page)
        ids += [m["id"] for m in resp.get("messages", [])]
        page = resp.get("nextPageToken")
        if not page:
            return ids


def safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip() or "statement.pdf"


def fetch(svc, seen):
    os.makedirs(OUTDIR, exist_ok=True)
    downloaded = []
    for mid in (m for b in BANKS if b.statement_mail for m in message_ids(svc, b.statement_mail)):
        if mid in seen:
            continue
        msg = api(svc, f"/{mid}")
        sender = next(
            (h["value"] for h in msg["payload"].get("headers", []) if h["name"].lower() == "from"), "unknown sender"
        )
        for name, att_id in iter_attachments(msg["payload"]):
            target = os.path.join(OUTDIR, f"{mid[:8]}_{safe_name(name)}")
            if not os.path.exists(target):
                att = api(svc, f"/{mid}/attachments/{att_id}")
                data = base64.urlsafe_b64decode(att["data"])
                with open(target, "wb") as f:
                    f.write(data)
                downloaded.append(target)
                print(f"  downloaded {os.path.basename(target)} ({len(data):,} bytes) from {sender}")
        seen.add(mid)
    return downloaded


def body_text(payload):
    """text/plain part if there is one, else the tags-stripped text/html part."""
    stack, found = [payload], {}
    while stack:
        part = stack.pop()
        stack += part.get("parts", []) or []
        if part.get("body", {}).get("data"):
            found[part["mimeType"]] = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
    if "text/plain" in found:
        return found["text/plain"]
    return html.unescape(re.sub(r"<[^>]+>", "\n", found.get("text/html", "")))


def fetch_notices(svc, seen):
    """Append new notification emails to manual_entries.csv; returns how many rows were added."""
    rows = []
    for bank in BANKS:
        if not bank.notice_mail:
            continue
        for mid in message_ids(svc, bank.notice_mail):
            if "n:" + mid in seen:
                continue
            msg = api(svc, f"/{mid}", format="full")
            row = bank.parse_notice(body_text(msg["payload"]))
            if row:
                rows.append(row)
            seen.add("n:" + mid)
    return append_manual(os.path.join(HERE, "manual_entries.csv"), rows)


def append_manual(path, rows):
    """Add payment-email rows to manual_entries.csv, skipping ones it already holds; returns how many were added."""
    have, header = [], MANUAL
    if rows and os.path.exists(path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            have, header = list(reader), reader.fieldnames or MANUAL
        for r in have:
            r["Bank"] = manual_bank(r)
        # Re-reading old emails (seen list lost/reset) must not add them twice. Skip a row while the file still
        # holds an unmatched identical copy; a real second same-minute payment exceeds that count and is kept.
        key = lambda r: tuple(r.get(k) or "" for k in MANUAL)
        count = Counter(key(r) for r in have)
        fresh = []
        for r in rows:
            if count[key(r)]:
                count[key(r)] -= 1
            else:
                fresh.append(r)
        rows = fresh
    for row in rows:
        print(f"  notice {row['Date']}  {row['Amount']}  {row['Description']}")
    if rows:
        old = "Bank" not in header  # a file from before the Bank column: rewrite it once with the column added
        fields = [*header, "Bank"] if old else header
        new = old or not os.path.exists(path)
        out = path + ".tmp" if old else path  # a failed rewrite must leave the old file as it was
        with open(out, "w" if old else "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fields)
            if new:
                w.writeheader()
            if old:
                w.writerows(have)
            w.writerows(
                sorted(rows, key=lambda r: r["Date"])
            )  # oldest first, so same-minute repeats keep a stable order
        if old:
            os.replace(out, path)
    return len(rows)


def pull(interactive=False):
    """Download new statement PDFs and payment notices; returns (PDF paths, notice count). One at a time: a second
    fetch (the listener's, ./gmail.sh, the page's Gmail button) waits, then reads the seen list the first one wrote, so
    the two never append the same notices or overwrite each other's seen list."""
    with open(LOCK, "a") as lock:
        config.lock(lock)  # released when the file closes, also if this process dies
        seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
        svc = service(interactive)
        downloaded = fetch(svc, seen)
        save_seen(seen)  # the PDFs are on disk: a failure while reading notices must not redo a big first run
        notices = fetch_notices(svc, seen)
        save_seen(seen)  # only now: notice ids are marked seen once their rows are in manual_entries.csv
        return downloaded, notices


def save_seen(seen):
    with open(SEEN, "w") as f:
        json.dump(sorted(seen), f)


def run(build):
    """One fetch of both kinds (statement PDFs and payment notices), then a rebuild if anything was new."""
    print("Searching Gmail: " + ", ".join(b.name for b in BANKS if b.statement_mail or b.notice_mail))
    downloaded, notices = pull()

    if not (downloaded or notices):
        print("No new statement emails found.")
        return
    print(f"\nDownloaded {len(downloaded)} new statement PDF(s) into {OUTDIR}/; {notices} new payment notice(s)")

    if build:
        import update_statement

        print()
        update_statement.main()
        print(UPDATED, flush=True)  # app.py, reading the listener's output, updates its open window on this line


def notified(svc, sub):
    """One long-poll pull of the subscription; True once it got (and acknowledged) a Gmail change notification."""
    import requests

    try:
        r = svc.post(f"{sub}:pull", json={"maxMessages": 100}, timeout=(10, 120))
    except requests.exceptions.ReadTimeout:
        return False  # the long poll ended with no mailbox change
    r.raise_for_status()
    acks = [m["ackId"] for m in r.json().get("receivedMessages", [])]
    if acks:  # ack before fetching: a slow rebuild must not get the same notice redelivered
        svc.post(f"{sub}:acknowledge", json={"ackIds": acks}, timeout=60).raise_for_status()
    return bool(acks)


def listen(build):
    """--listen: fetch within seconds of new mail. Gmail posts every inbox change to the Pub/Sub topic; this waits
    on the subscription and runs the normal fetch per notification (the seen list skips mail already handled, so
    the notification's content is not needed)."""
    import signal
    import subprocess
    import time

    import requests
    from google.auth.exceptions import RefreshError, TransportError

    if not (TOPIC and SUBSCRIPTION and PROJECT):
        sys.exit(LISTEN_HELP)
    me = open(LISTEN_LOCK, "a")  # one listener at a time (the app window's and a service's)
    if not config.lock(me, wait=False):
        sys.exit("Another listener is already running.")
    state = {"busy": False, "stop": False}

    def on_term(*_):  # the app window closing, or systemctl stop
        # logged, so a listener that's gone can be told apart from one that crashed (parent: the app window, if any)
        print(
            f"Asked to stop (SIGTERM, parent pid {os.getppid()}); {'finishing the fetch first' if state['busy'] else 'stopping'}."
        )
        if not state["busy"]:
            sys.exit(0)
        state["stop"] = True  # a fetch is appending to manual_entries.csv or rebuilding: let it finish

    signal.signal(signal.SIGTERM, on_term)
    sub = f"{PUBSUB}/projects/{PROJECT}/subscriptions/{SUBSCRIPTION}"
    svc, renew, wait = None, 0, 5
    pending = True  # catch up first: mail may have arrived while nothing was listening
    print(f"Listening for new mail (topic {TOPIC}, subscription {SUBSCRIPTION}). Ctrl+C stops.")
    while not state["stop"]:
        try:
            svc = svc or service()  # in the loop: started offline (app opened before the network) = retried below
            if time.time() > renew:  # a watch lasts 7 days; Google advises renewing it daily
                svc.post(
                    WATCH, json={"topicName": f"projects/{PROJECT}/topics/{TOPIC}", "labelIds": ["INBOX"]}, timeout=60
                ).raise_for_status()
                renew = time.time() + 86400
            if pending:
                state["busy"] = True
                try:
                    # A fresh process per fetch: code updated after the listener started (a git pull, a fix) is used
                    # on the next email, without restarting the listener or the app window.
                    done = (
                        subprocess.run(
                            config.script("fetch_gmail", "--recent", *([] if build else ["--no-build"]))
                        ).returncode
                        == 0
                    )
                finally:
                    state["busy"] = False
                if not done:  # stays pending: retried after the usual back-off
                    print(f"  fetch failed; retrying in {wait}s")
                    time.sleep(wait)
                    wait = min(wait * 2, 300)
                    continue
                pending = False
            elif notified(svc, sub):
                pending = True
                # ponytail: a fixed pause, because Gmail search can lag a fresh delivery by a few seconds; a mail
                # it still misses is fetched on the next inbox change (opening the mail is one). If the log shows
                # pushes that fetch nothing followed by late fetches, search again after a second pause instead.
                time.sleep(5)
            wait = 5
        except RefreshError:
            sys.exit(f"Gmail login missing or expired: run {config.command('gmail')} by hand once to sign in again.")
        except (requests.RequestException, TransportError) as e:  # TransportError: the login refresh, offline
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (400, 401, 403, 404):  # wrong name, missing permission or scope: retrying won't help
                sys.exit(f"Pub/Sub or Gmail refused the request ({code}): {e.response.text.strip()}\n\n{LISTEN_HELP}")
            print(f"  {e.__class__.__name__} ({code or 'no connection'}); retrying in {wait}s")  # offline, asleep, 5xx
            time.sleep(wait)
            wait = min(wait * 2, 300)


def main() -> int:
    build = "--no-build" not in sys.argv
    if "--listen" not in sys.argv:
        if "--recent" in sys.argv:  # the listener's per-email fetch: recent mail only
            global RECENT
            RECENT = LISTEN_WINDOW
        run(build)
        return 0
    try:
        listen(build)  # runs until stopped
    except KeyboardInterrupt:
        print("\nStopped listening.")
    return 0


LISTEN_HELP = """\
Real-time Gmail (--listen) needs GMAIL_TOPIC, GMAIL_SUBSCRIPTION and GOOGLE_PROJECT_ID in .env, a Pub/Sub topic
that gmail-api-push@system.gserviceaccount.com may publish to, a pull subscription on it, and the Pub/Sub scope
on the OAuth consent screen. See README "Real time: Gmail push (optional)" for the one-time steps.
"""


SETUP_HELP = """\
Gmail is not set up yet — GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are missing from .env.

  1. Go to https://console.cloud.google.com/ and create a project.
  2. APIs & Services -> Library -> enable "Gmail API".
  3. APIs & Services -> Credentials -> Create credentials -> OAuth client ID
     -> Application type: Desktop app.
  4. Put the client id and secret in .env at the project root:
       GOOGLE_CLIENT_ID=...
       GOOGLE_CLIENT_SECRET=...
     then re-run.

On first run a browser window asks you to grant read-only Gmail access;
after that the login is remembered in token.json.
"""

if __name__ == "__main__":
    raise SystemExit(main())

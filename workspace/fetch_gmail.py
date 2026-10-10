#!/usr/bin/env python3
"""Pull Krungthai statement PDFs from Gmail into Statement/, then update.

Workflow: Gmail API -> find statement emails -> download new PDF attachments
into Statement/ -> run update_statement (merge -> ledger.csv -> dashboard).

Read-only access to Gmail is used; nothing is modified in your mailbox. Which
emails count as "a statement" is controlled by GMAIL_QUERY below — edit it to
match your bank's sender/subject.

One-time setup (see the notes printed if the .env keys are missing):
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create an OAuth client ID (type: Desktop app) and put its client id and
     secret in <project root>/.env as GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET.
  3. First run opens a browser to authorise; the token is cached in token.json.

Usage:
    python fetch_gmail.py            # fetch new statements + rebuild
    python fetch_gmail.py --no-build # only download, don't rebuild
    python fetch_gmail.py --selfcheck
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

# Gmail search that selects statement emails (Gmail query syntax). The default matches the
# subject of Krungthai's statement emails; override with GMAIL_QUERY in the env settings, e.g.
#   from:<your bank's sender address> has:attachment filename:pdf
GMAIL_QUERY = os.environ.get("GMAIL_QUERY") or "ส่งรายการเดินบัญชีเงินฝาก"

# Per-transaction "payment done" emails from Krungthai NEXT (no PDF, outgoing only, no balance). They go
# into manual_entries.csv; once the monthly statement has the same minute + amount the statement row wins.
NOTIFY_QUERY = 'from:noreply@krungthai.com "แจ้งผลการ"'

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
# Three read-only GETs (list, get, attachment) over plain HTTPS: google-api-python-client would add ~100 MB of
# API discovery documents to the venv for them.
API = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

# Anchor paths to this script's folder so it runs from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root

OUTDIR = os.path.join(ROOT, "Statement")            # PDFs land in root/Statement
TOKEN = os.path.join(HERE, "token.json")
SEEN = os.path.join(HERE, ".gmail_seen.json")


def client_config():
    cid, secret = os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (cid and secret):
        sys.exit(SETUP_HELP)
    return {"installed": {
        "client_id": cid, "client_secret": secret,
        "project_id": os.environ.get("GOOGLE_PROJECT_ID", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"]}}


def service():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import AuthorizedSession
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
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
            if not sys.stdin.isatty():      # cron: nobody to click through the browser, don't hang
                sys.exit("Gmail login missing or expired: run ./gmail.sh by hand once to sign in again.")
            flow = InstalledAppFlow.from_client_config(client_config(), SCOPES)
            creds = flow.run_local_server(port=0)
        fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
        os.chmod(TOKEN, 0o600)   # also tightens a token file created earlier with looser permissions
    session = AuthorizedSession(creds)      # refreshes the access token itself
    # Back off and retry on rate limits (429) and Google-side errors, which a big first run can hit.
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1,
                                                            status_forcelist=(429, 500, 502, 503))))
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
        resp = api(svc, q=query, pageToken=page)
        ids += [m["id"] for m in resp.get("messages", [])]
        page = resp.get("nextPageToken")
        if not page:
            return ids


def safe_name(name):
    return (
        "".join(c for c in name if c.isalnum() or c in "._- ").strip()
        or "statement.pdf"
    )


def fetch(svc, seen):
    os.makedirs(OUTDIR, exist_ok=True)
    downloaded = []
    for mid in message_ids(svc, GMAIL_QUERY):
        if mid in seen:
            continue
        msg = api(svc, f"/{mid}")
        sender = next((h["value"] for h in msg["payload"].get("headers", [])
                       if h["name"].lower() == "from"), "unknown sender")
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


def parse_notice(text):
    """Krungthai NEXT notice -> manual_entries row dict, or None if it is not a completed payment."""
    def field(*names):
        m = re.search(rf"(?:{'|'.join(names)})\s*:\s*(.+)", text)
        return m.group(1).strip() if m else None

    when = re.search(r"วันที่ทำรายการ\s*:\s*(\d\d)/(\d\d)/(\d{4})\s+(\d\d:\d\d)", text)
    amt = re.search(r"(?:จำนวนเงินที่ชำระ|จำนวนเงิน)\s*:\s*([\d,.]+)", text)
    if not (when and amt):
        return None
    fee = re.search(r"ค่าธรรมเนียม\s*:\s*([\d,.]+)", text)
    dd, mm, be, hm = when.groups()
    total = float(amt.group(1).replace(",", "")) + (float(fee.group(1).replace(",", "")) if fee else 0)
    if "โอนเงินพร้อมเพย์" in text:
        kind, to = "PromptPay out", field("ไปยังบัญชีพร้อมเพย์")
    elif "โอนเงิน" in text:
        kind, to = "Transfer out", field("ไปยังบัญชี")
    else:   # จ่ายบิล / ชำระค่าสินค้าและบริการ
        kind, to = "Bill / purchase", field("ไปยังผู้ให้บริการ", "ไปยังร้านค้า")
    return {"Date": f"{int(be) - 543:04d}-{mm}-{dd} {hm}", "Description": f"{kind} (email) {to or ''}".strip(),
            "Category": kind, "Amount": f"{-total:.2f}", "Balance": ""}


def fetch_notices(svc, seen):
    """Append new notification emails to manual_entries.csv; returns how many rows were added."""
    rows = []
    for mid in message_ids(svc, NOTIFY_QUERY):
        if "n:" + mid in seen:
            continue
        msg = api(svc, f"/{mid}", format="full")
        row = parse_notice(body_text(msg["payload"]))
        if row:
            rows.append(row)
        seen.add("n:" + mid)
    path = os.path.join(HERE, "manual_entries.csv")
    if rows and os.path.exists(path):
        # Re-reading old emails (seen list lost/reset) must not add them twice. Skip a row while the file still
        # holds an unmatched identical copy; a real second same-minute payment exceeds that count and is kept.
        have = Counter(tuple(r.values()) for r in csv.DictReader(open(path, encoding="utf-8-sig")))
        fresh = []
        for r in rows:
            k = tuple(r.values())
            if have[k]:
                have[k] -= 1
            else:
                fresh.append(r)
        rows = fresh
    for row in rows:
        print(f"  notice {row['Date']}  {row['Amount']}  {row['Description']}")
    if rows:
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, ["Date", "Description", "Category", "Amount", "Balance"])
            if new:
                w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["Date"]))   # oldest first, so same-minute repeats keep a stable order
    return len(rows)


def save_seen(seen):
    with open(SEEN, "w") as f:
        json.dump(sorted(seen), f)


def selfcheck():
    """python fetch_gmail.py --selfcheck: paging, attachment download and the seen list against a fake session."""
    import tempfile
    global OUTDIR

    class Resp:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    pdf = base64.urlsafe_b64encode(b"%PDF-1 x").decode()
    calls = []

    class Fake:
        def get(self, url, params=None, timeout=None):
            calls.append((url.removeprefix(API), dict(params or {})))
            path = url.removeprefix(API)
            if path == "":
                if params.get("pageToken") is None:
                    return Resp({"messages": [{"id": "aaaaaaaa11"}], "nextPageToken": "p2"})
                return Resp({"messages": [{"id": "bbbbbbbb22"}]})
            if path.endswith("/attachments/att1"):
                return Resp({"data": pdf})
            return Resp({"payload": {"headers": [{"name": "From", "value": "bank"}],
                                     "parts": [{"filename": "s.pdf", "body": {"attachmentId": "att1"}}]}})

    old, OUTDIR = OUTDIR, tempfile.mkdtemp()
    try:
        seen = {"bbbbbbbb22"}
        got = fetch(Fake(), seen)
        assert [os.path.basename(g) for g in got] == ["aaaaaaaa_s.pdf"], got      # paged, and the seen one skipped
        assert open(got[0], "rb").read() == b"%PDF-1 x" and "aaaaaaaa11" in seen
    finally:
        OUTDIR = old
    print("selfcheck ok")


def main() -> int:
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
        return 0
    seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
    print(f"Searching Gmail: {GMAIL_QUERY}")
    if "from:" not in GMAIL_QUERY.lower():
        print("  Note: the query matches any sender. Anyone can email a PDF with that subject and it would\n"
              "  be added to your ledger. Add from:<your bank's address> to GMAIL_QUERY in the settings file.")
    svc = service()
    downloaded = fetch(svc, seen)
    save_seen(seen)         # the PDFs are on disk: a failure while reading notices must not redo a big first run
    notices = fetch_notices(svc, seen)
    save_seen(seen)         # only now: notice ids are marked seen once their rows are in manual_entries.csv

    if not (downloaded or notices):
        print("No new statement emails found.")
        return 0
    print(f"\nDownloaded {len(downloaded)} new statement PDF(s) into {OUTDIR}/; {notices} new payment notice(s)")

    if "--no-build" not in sys.argv:
        import update_statement

        print()
        update_statement.main()
    return 0


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

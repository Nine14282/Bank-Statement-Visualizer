#!/usr/bin/env python3
"""One-shot updater: every statement PDF in Statement/ -> ledger.csv -> dashboard.

Drop a new statement PDF into Statement/ and run this single script. It:
  1. reads every PDF in Statement/ (unlocking encrypted ones),
  2. merges them, dropping duplicates — a transaction is unique by its ID
     (txid.py: minute + signed amount + occurrence within one statement),
  3. writes the combined ledger.csv, and
  4. rebuilds the local, self-contained dashboard (web/dist/index.html).

Everything stays on your machine; nothing is uploaded. Open the resulting
web/dist/index.html in any browser (works offline).

Encrypted PDFs are unlocked on the fly. Each bank has its own password setting (BANKS in
extract_ledger.py: KTB_PW, KBANK_PW). Each file tries no password, then its own bank's setting (by
file name; KBank files are named STM_..., Gmail downloads add an 8-character message-id prefix),
then every other bank's, then --password= / ones typed this run, then an interactive prompt
(asked once and reused for every encrypted file).

Usage:
    python update_statement.py [STATEMENT_DIR] [OUTPUT_CSV]
    KTB_PW=xxxx KBANK_PW=yyyy python update_statement.py
Defaults: Statement/ -> ledger.csv -> web/dist/index.html
"""
import contextlib
import csv
import getpass
import glob
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timedelta

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

import build_dashboard
import config  # loads the project's env settings (KTB_PW, KBANK_PW, ...) into os.environ
from extract_ledger import BANKS, bank_from_name, extract, write_csv
from txid import differences, stamp_ids

# Anchor paths to this script's folder so it runs from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root

# Parsed rows per PDF, so an update only reads statements it hasn't read before (re-reading all 9 took ~40 s). An entry
# is keyed by the file's bytes plus everything else that shapes its rows: the parser code, the pdfplumber version and
# the reference-number settings categorize() reads; change any and the file is read again. It holds transactions like
# ledger.csv: private (0600), git-ignored, deleted by clear.sh; entries no PDF uses any more go after each good run.
CACHE = os.path.join(HERE, ".cache")
USED: set[str] = set()      # entries this run used (the rest are pruned)
CACHE_SETTINGS = ("LEDGER_CASH_REF", "LEDGER_PEER_REF", "LEDGER_STOCK_REF")


def passwords(cache=[]):
    """--password= and passwords typed during this run, reused for the next files."""
    if not cache:
        cache += [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--password=")]
    return cache


def candidates(path):
    """Passwords to try for one file: none, its own bank's settings first (by file name), then every other
    bank's (a file may be named unusually), then any typed this run. STATEMENT_PW is the old name of KTB_PW."""
    own = bank_from_name(path)
    keys = [*(own.passwords if own else ()), *(k for b in BANKS for k in b.passwords)]
    out = []
    for pw in (None, *(os.environ.get(k) for k in keys), *passwords()):   # None: the file may not be encrypted
        if pw not in out and (pw is None or pw):
            out.append(pw)
    return out


def why(e):
    """Error type plus any wrapped error types, e.g. 'PdfminerException: PDFPasswordIncorrect' (never contents)."""
    inner = [type(a).__name__ for a in getattr(e, "args", ()) if isinstance(a, BaseException)]
    return type(e).__name__ + (f": {', '.join(inner)}" if inner else "")


def cache_entry(path) -> str:
    parts = [open(path, "rb").read(), open(os.path.join(HERE, "extract_ledger.py"), "rb").read(),
             pdfplumber.__version__.encode(), *(os.environ.get(k, "").encode() for k in CACHE_SETTINGS)]
    key = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).hexdigest()[:40]
    USED.add(key)
    return os.path.join(CACHE, key + ".json")


def remember(path, rows, log=""):
    """Cache one PDF's rows and what reading it printed (its CHECK lines, shown again on every run)."""
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    fd = os.open(cache_entry(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "log": log}, f, ensure_ascii=False)


def cached(path):
    """This PDF's cached rows, or None if it hasn't been read yet (quiet, needs no password)."""
    try:
        with open(cache_entry(path), encoding="utf-8") as f:
            return json.load(f)["rows"]
    except (OSError, ValueError, KeyError):
        return None


def load(path):
    """Rows of one PDF: from the cache if this exact file was read before (same parser, same settings; no password
    needed then), else read and cached."""
    try:
        with open(cache_entry(path), encoding="utf-8") as f:
            hit = json.load(f)
        print(hit["log"], end="")
        return hit["rows"]
    except (OSError, ValueError, KeyError):
        pass                       # not read before (or an unreadable entry): read the PDF
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rows = read_pdf(path)
    print(buf.getvalue(), end="")
    remember(path, rows, buf.getvalue())
    return rows


def prune_cache():
    """Drop entries no PDF used this run (a deleted statement, an older parser or setting)."""
    for name in os.listdir(CACHE) if os.path.isdir(CACHE) else []:
        if name.endswith(".json") and name[:-5] not in USED:
            os.remove(os.path.join(CACHE, name))


def read_pdf(path):
    """Extract rows from a PDF: no password, then each known password, then ask (if someone can answer)."""
    errors = []
    for pw in candidates(path):
        try:
            return extract(path, pw)
        except PdfminerException as e:   # pdfplumber wraps every open/decrypt failure in this: wrong or missing
            errors.append(e)             # password. Anything else is a parser problem: let it reach main()'s SKIP
    if not sys.stdin.isatty():      # cron / watcher: nobody to ask. Stop rather than write a ledger missing this file.
        keys = " / ".join(b.passwords[0] for b in BANKS)
        sys.exit(f"No known password opens {os.path.basename(path)} ({why(errors[-1])}). Set {keys} "
                 "in the env settings (see .env.example), run ./run.sh --setup, or run this by hand to type it. "
                 "Ledger left unchanged.")
    named = bank_from_name(path)
    last = None
    for _ in range(3):
        pw = getpass.getpass(f"{named.name if named else 'PDF'} password for {os.path.basename(path)}: ")
        try:
            rows = extract(path, pw)
        except PdfminerException as e:
            last = e
            print(f"  that password doesn't open it ({why(e)})")
            continue
        passwords().append(pw)      # reuse for the next file
        return rows
    raise last


def by_minute(r):
    """Sort key. Date only: a stable sort keeps rows of one minute in statement order, which is the order their
    balances chain (sorting Balance as text put "70.00" after "160.00" and the dashboard read the wrong last row)."""
    return r["Date"]


def own_transfers(rows):
    """Money moved between your own accounts (KTB <-> KBank) is neither income nor spending.

    A pair = same amount, opposite direction, different banks, within 2 minutes. Both rows become
    "Own transfer", which the dashboard leaves out of income, expenses and the spend rate.
    ponytail: greedy 1:1 scan; an unrelated same-amount pair inside 2 minutes would also match.
    """
    when = lambda r: datetime.fromisoformat(r["Date"])   # time is optional
    banks = [r for r in rows if r.get("Bank") not in (None, "", "Manual")]
    used = set()
    for a in banks:
        if float(a["Amount"]) >= 0 or a["ID"] in used:
            continue
        b = next((b for b in banks if b["ID"] not in used and b["Bank"] != a["Bank"]
                  and abs(float(b["Amount"]) + float(a["Amount"])) < 0.005
                  and abs(when(b) - when(a)) <= timedelta(minutes=2)), None)
        if b:
            used |= {a["ID"], b["ID"]}
            a["Category"] = b["Category"] = "Own transfer"
            print(f"  own transfer: {a['Date']} {a['Bank']} -> {b['Bank']} {-float(a['Amount']):,.2f}")


def main(progress=None) -> int:
    """progress(stage, done=0, total=0), if given, hears each stage as it starts ("read" per file, "merge",
    "build"): the add page's loader shows it."""
    step = progress or (lambda *a: None)
    USED.clear()                # a long-running process (the app) calls main() again: prune from this run only
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src_dir = args[0] if len(args) > 0 else os.path.join(ROOT, "Statement")
    dst = args[1] if len(args) > 1 else os.path.join(HERE, "ledger.csv")

    pdfs = sorted(glob.glob(os.path.join(src_dir, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {src_dir}/", file=sys.stderr)
        return 1

    by_id, merged, skipped, conflicts = {}, [], [], []
    reworded = 0
    for i, path in enumerate(pdfs, 1):
        name = os.path.basename(path)
        step("read", i, len(pdfs))
        try:
            rows = load(path)
        except Exception as e:
            reason = (str(e).splitlines() or [type(e).__name__])[0][:60]
            skipped.append((name, reason))
            detail = f": {e}" if isinstance(e, ValueError) else ""   # our own parse checks explain themselves
            print(f"  SKIP {name}: could not read ({why(e)}{detail})")
            continue
        new = 0
        for r in stamp_ids(rows):
            old = by_id.get(r["ID"])
            if old is not None:      # same minute + same signed amount + same occurrence = same transaction
                diff = differences(old, r)
                if diff == ["description differs"]:
                    # Same money, new wording: the bank renamed the type in a later statement (e.g. จ่ายค่าสินค้า/บริการ
                    # (CGSWP) became หักบัญชีอัตโนมัติ (CGSWP)). Files load oldest first (Gmail ids grow over time), so
                    # take the newer wording; then one payee reads the same in every month and labels match all of it.
                    old["Description"], old["Category"] = r["Description"], r["Category"]
                    reworded += 1
                elif diff:
                    conflicts.append(f"{r['Date']}  {float(r['Amount']):+,.2f}  in {name}: {', '.join(diff)}")
                continue
            by_id[r["ID"]] = r; merged.append(r); new += 1
        print(f"  {name}: {len(rows):>4} rows, {new:>4} new, "
              f"{len(rows) - new:>4} duplicate")

    if reworded:
        print(f"  {reworded} row(s) took the newer statement's wording for the same transaction")

    step("merge")
    # Hand-entered rows (spends no bank record covers) live in manual_entries.csv.
    manual = os.path.join(HERE, "manual_entries.csv")
    if os.path.exists(manual):
        with open(manual, newline="", encoding="utf-8-sig") as f:
            typed = list(csv.DictReader(f))
        extra = []
        for n, r in enumerate(typed, 2):     # line 1 is the header
            try:
                datetime.fromisoformat(r["Date"])
                float(r["Amount"])
            except (KeyError, TypeError, ValueError):
                print(f"  manual_entries.csv line {n} skipped: needs a Date like 2026-01-31 or 2026-01-31 14:05 "
                      "and a numeric Amount")
                continue
            extra.append(r)
        for r in extra:   # payment emails come from Krungthai NEXT; anything else was typed by hand
            r["Bank"] = "KTB" if "(email)" in r["Description"] else "Manual"
        extra = stamp_ids(extra)
        added = 0
        stmt = list(merged)          # statement rows only (before any manual row is added)
        claimed = set()              # statement rows already matched to a manual row
        when = lambda r: datetime.fromisoformat(r["Date"])   # time is optional
        for r in extra:
            if r["ID"] in by_id:     # the bank statement already has it
                claimed.add(r["ID"])
                print(f"  manual entry skipped, already in a statement: {r['Date']}  "
                      f"{float(r['Amount']):+,.2f}  {r['Description']}")
                continue
            if "(email)" in r["Description"]:
                # Payment-notice emails carry the payment time, but the statement can post bills minutes to
                # hours later. Same amount within 4h of a not-yet-matched statement row = same transaction.
                # "Future Amount" rows are payments made after KTB's nightly cut-off (~23:00), posted ~01:30-02:30
                # the next day: they get 6h so a late-evening notice still finds its statement row.
                # ponytail: fixed windows, 1:1 greedy; widen/narrow if bills post later/earlier than that
                hit = next((s for s in stmt if s["ID"] not in claimed and s.get("Bank") == "KTB"
                            and float(s["Amount"]) == float(r["Amount"])
                            and abs(when(s) - when(r)) <= timedelta(hours=6 if "Future Amount" in s["Description"] else 4)), None)
                if hit:
                    claimed.add(hit["ID"])
                    print(f"  notice matched to statement row, skipped: {r['Date']}  {float(r['Amount']):+,.2f}  "
                          f"(statement {hit['Date']})")
                    if "Future Amount" in hit["Description"]:
                        # The statement prints when the bank posted it (~01:48 next day); the notice says when it was
                        # paid. Keep the paid time. Amount, balance and ID stay the statement's.
                        hit["Date"] = r["Date"]
                    continue
            by_id[r["ID"]] = r; merged.append(r); added += 1
        print(f"  manual entries: {added} added of {len(extra)}")

    if not merged:
        # Never overwrite a good ledger.csv with nothing.
        print("\nNo transactions were read — ledger and dashboard left unchanged.")
        if skipped:
            print(f"  {len(skipped)} file(s) skipped (wrong/no password): "
                  + ", ".join(n for n, _ in skipped))
        print("(Check the password, or that Statement/ holds valid PDFs.)")
        return 1

    if conflicts:
        print(f"\n  CONFLICT: {len(conflicts)} transaction(s) appear in two statements with different details "
              "(the earlier copy was kept; check them):")
        for c in conflicts:
            print(f"    {c}")
    assert len({r["ID"] for r in merged}) == len(merged), "duplicate transaction IDs after merge"

    own_transfers(merged)
    merged.sort(key=by_minute)
    write_csv(merged, dst)
    prune_cache()

    print(f"\nMerged {len(pdfs) - len(skipped)} statement(s) -> {dst}")
    print(f"  {len(merged)} unique transactions")
    print(f"  {merged[0]['Date']}  ->  {merged[-1]['Date']}")
    if skipped:
        print(f"  {len(skipped)} file(s) skipped (wrong/no password): "
              + ", ".join(n for n, _ in skipped))

    # Rebuild the local dashboard from the freshly merged ledger.
    print()
    step("build")
    build_dashboard.build(csv_path=dst)
    print("\nDone. Open Dashboard.html (project folder) in your browser.")
    return 0


def selfcheck():
    """python update_statement.py --selfcheck: a PDF is read once, then served from the cache (CHECK lines included)
    until the file or a setting changes; pruning keeps only what the run used."""
    import tempfile
    global CACHE, read_pdf
    real_cache, real_read, reads = CACHE, read_pdf, []

    def fake_read(path):
        reads.append(path)
        print("CHECK a.pdf: one row doesn't reconcile")
        return [{"Date": "2026-01-01 10:00", "Description": "x", "Category": "Food", "Amount": "-1.00", "Balance": "9.00"}]

    def quiet_load(path):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return load(path), buf.getvalue()

    same_minute = [{"Date": "2026-01-01 10:00", "Balance": b} for b in ("150.00", "140.00", "130.00")]
    assert [r["Balance"] for r in sorted(same_minute, key=by_minute)] == ["150.00", "140.00", "130.00"]

    saved = os.environ.get(CACHE_SETTINGS[0])
    try:
        with tempfile.TemporaryDirectory() as d:
            CACHE, read_pdf = os.path.join(d, "cache"), fake_read
            pdf = os.path.join(d, "a.pdf")
            open(pdf, "wb").write(b"%PDF-1 first")
            (rows, log), (again, log2) = quiet_load(pdf), quiet_load(pdf)
            assert rows == again and len(reads) == 1, reads                 # second load: the cache, no read
            assert "CHECK" in log and log2 == log, (log, log2)             # the warning shows on every run
            os.environ[CACHE_SETTINGS[0]] = "changed"
            quiet_load(pdf)
            assert len(reads) == 2, reads                                   # a setting changed: read again
            open(pdf, "wb").write(b"%PDF-1 second")
            quiet_load(pdf)
            assert len(reads) == 3, reads                                   # the file changed: read again
            USED.clear()
            quiet_load(pdf)
            prune_cache()
            assert len(os.listdir(CACHE)) == 1, os.listdir(CACHE)           # older entries pruned
            assert oct(os.stat(os.path.join(CACHE, os.listdir(CACHE)[0])).st_mode & 0o777) == "0o600"
    finally:
        CACHE, read_pdf = real_cache, real_read
        if saved is None:
            os.environ.pop(CACHE_SETTINGS[0], None)
        else:
            os.environ[CACHE_SETTINGS[0]] = saved
    print("selfcheck ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
        raise SystemExit(0)
    raise SystemExit(main())

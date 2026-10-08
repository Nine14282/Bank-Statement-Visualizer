#!/usr/bin/env python3
"""One-shot updater: every statement PDF in Statement/ -> ledger.csv -> dashboard.

Drop a new statement PDF into Statement/ and run this single script. It:
  1. reads every PDF in Statement/ (unlocking encrypted ones),
  2. merges them, dropping duplicates — a transaction is unique by
     (date-time, amount, balance) since the running balance never repeats,
  3. writes the combined ledger.csv, and
  4. rebuilds the local, self-contained dashboard (web/dist/index.html).

Everything stays on your machine; nothing is uploaded. Open the resulting
web/dist/index.html in any browser (works offline).

Encrypted PDFs are unlocked on the fly. KTB and KBank use different passwords: KTB_PW and
KBANK_PW. KBank files are named STM_... (Gmail downloads add an 8-character message-id prefix),
so each file tries its own bank's password first, then the other, then --password= / a typed
one, then an interactive prompt (asked
once and reused for every encrypted file).

Usage:
    python update_statement.py [STATEMENT_DIR] [OUTPUT_CSV]
    KTB_PW=xxxx KBANK_PW=yyyy python update_statement.py
Defaults: Statement/ -> ledger.csv -> web/dist/index.html
"""
import csv
import getpass
import glob
import os
import re
import sys
from datetime import datetime, timedelta

import build_dashboard
import config  # loads the project's env settings (KTB_PW, KBANK_PW, ...) into os.environ
from extract_ledger import extract, write_csv
from txid import differences, stamp_ids

# Anchor paths to this script's folder so it runs from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root


def passwords(cache=[]):
    """--password= and passwords typed during this run, reused for the next files."""
    if not cache:
        cache += [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--password=")]
    return cache


def is_kbank(path):
    """KBank statements are named STM_...; Gmail downloads prefix the name with 8 hex chars + '_'."""
    return re.sub(r"^[0-9a-f]{8}_", "", os.path.basename(path)).startswith("STM")


def candidates(path):
    """Passwords to try for one file, its own bank's first. STATEMENT_PW is the old name of KTB_PW."""
    ktb, kbank = os.environ.get("KTB_PW") or os.environ.get("STATEMENT_PW"), os.environ.get("KBANK_PW")
    own, other = (kbank, ktb) if is_kbank(path) else (ktb, kbank)
    out = []
    for pw in (None, own, other, *passwords()):   # None: the file may not be encrypted
        if pw not in out and (pw is None or pw):
            out.append(pw)
    return out


def load(path):
    """Extract rows from a PDF: no password, then each known password, then ask (if someone can answer)."""
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    for pw in candidates(path):
        try:
            return extract(path, pw)
        except Exception as e:      # pdfplumber wraps PDFPasswordIncorrect in a PdfminerException
            if not any(isinstance(x, PDFPasswordIncorrect) for x in (e, *e.args)):
                raise              # a real parse problem: let main() report it, don't hide it
    if not sys.stdin.isatty():      # cron / watcher: nobody to ask. Stop rather than write a ledger missing this file.
        sys.exit(f"No known password opens {os.path.basename(path)}. Set KTB_PW / KBANK_PW in the env "
                 "settings (see .env.example) or run this by hand to type it. Ledger left unchanged.")
    pw = getpass.getpass(f"{'KBank' if is_kbank(path) else 'KTB'} password for {os.path.basename(path)}: ")
    rows = extract(path, pw)
    passwords().append(pw)          # reuse for the next file
    return rows


def own_transfers(rows):
    """Money moved between your own accounts (KTB <-> KBank) is neither income nor spending.

    A pair = same amount, opposite direction, different banks, within 2 minutes. Both rows become
    "Own transfer", which the dashboard leaves out of income, expenses and the spend rate.
    ponytail: greedy 1:1 scan; an unrelated same-amount pair inside 2 minutes would also match.
    """
    when = lambda r: datetime.strptime(r["Date"], "%Y-%m-%d %H:%M")
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


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src_dir = args[0] if len(args) > 0 else os.path.join(ROOT, "Statement")
    dst = args[1] if len(args) > 1 else os.path.join(HERE, "ledger.csv")

    pdfs = sorted(glob.glob(os.path.join(src_dir, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {src_dir}/", file=sys.stderr)
        return 1

    by_id, merged, skipped, conflicts = {}, [], [], []
    for path in pdfs:
        name = os.path.basename(path)
        try:
            rows = load(path)
        except Exception as e:
            reason = (str(e).splitlines() or [type(e).__name__])[0][:60]
            skipped.append((name, reason))
            print(f"  SKIP {name}: could not read ({type(e).__name__})")
            continue
        new = 0
        for r in stamp_ids(rows):
            old = by_id.get(r["ID"])
            if old is not None:      # same minute + same signed amount + same occurrence = same transaction
                diff = differences(old, r)
                if diff:
                    conflicts.append(f"{r['Date']}  {float(r['Amount']):+,.2f}  in {name}: {', '.join(diff)}")
                continue
            by_id[r["ID"]] = r; merged.append(r); new += 1
        print(f"  {name}: {len(rows):>4} rows, {new:>4} new, "
              f"{len(rows) - new:>4} duplicate")

    # Hand-entered rows (spends no bank record covers) live in manual_entries.csv.
    manual = os.path.join(HERE, "manual_entries.csv")
    if os.path.exists(manual):
        extra = list(csv.DictReader(open(manual, encoding="utf-8-sig")))
        for r in extra:   # payment emails come from Krungthai NEXT; anything else was typed by hand
            r["Bank"] = "KTB" if "(email)" in r["Description"] else "Manual"
        extra = stamp_ids(extra)
        added = 0
        stmt = list(merged)          # statement rows only (before any manual row is added)
        claimed = set()              # statement rows already matched to a manual row
        when = lambda r: datetime.strptime(r["Date"], "%Y-%m-%d %H:%M")
        for r in extra:
            if r["ID"] in by_id:     # the bank statement already has it
                claimed.add(r["ID"])
                print(f"  manual entry skipped, already in a statement: {r['Date']}  "
                      f"{float(r['Amount']):+,.2f}  {r['Description']}")
                continue
            if "(email)" in r["Description"]:
                # Payment-notice emails carry the payment time, but the statement can post bills minutes to
                # hours later. Same amount within 4h of a not-yet-matched statement row = same transaction.
                # ponytail: 4h window, 1:1 greedy; widen/narrow if bills post later/earlier than that
                hit = next((s for s in stmt if s["ID"] not in claimed and s.get("Bank") == "KTB"
                            and float(s["Amount"]) == float(r["Amount"])
                            and abs(when(s) - when(r)) <= timedelta(hours=4)), None)
                if hit:
                    claimed.add(hit["ID"])
                    print(f"  notice matched to statement row, skipped: {r['Date']}  {float(r['Amount']):+,.2f}  "
                          f"(statement {hit['Date']})")
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
    merged.sort(key=lambda r: (r["Date"], r["Balance"]))
    write_csv(merged, dst)

    print(f"\nMerged {len(pdfs) - len(skipped)} statement(s) -> {dst}")
    print(f"  {len(merged)} unique transactions")
    print(f"  {merged[0]['Date']}  ->  {merged[-1]['Date']}")
    if skipped:
        print(f"  {len(skipped)} file(s) skipped (wrong/no password): "
              + ", ".join(n for n, _ in skipped))

    # Rebuild the local dashboard from the freshly merged ledger.
    print()
    build_dashboard.build(csv_path=dst)
    print("\nDone. Open web/dist/index.html in your browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

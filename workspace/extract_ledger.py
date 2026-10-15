#!/usr/bin/env python3
"""Extract a bank statement PDF (any bank in banks/) into a clean CSV ledger.

Columns: Date, Description, Category, Amount, Balance, ID, Bank
  - Amount is signed: deposits positive (income), withdrawals negative (expense).
  - Each bank's parser lives in its own module under banks/ (ktb.py, kbank.py); this file picks the
    bank for a PDF and writes the CSV.
  - A row that doesn't reconcile prints a CHECK line and is still imported, never dropped.

Usage:
    python extract_ledger.py IN.pdf OUT.csv
    python extract_ledger.py IN.pdf OUT.csv --password=...
The password comes from --password=, else the password setting of the bank the file name points to
(banks/: KBANK_PW for STM_* files, KTB_PW for others; see .env.example), else it is asked for
(typed, hidden).
"""

import csv
import getpass
import os
import re
import sys

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

import config  # loads the project's env settings into os.environ
from banks import BANKS, Bank
from txid import stamp_ids

HEADER = ["Date", "Description", "Category", "Amount", "Balance", "ID", "Bank"]  # ID: see txid.py

BY_ID = {b.id: b for b in BANKS}


def bank_from_name(path: str) -> Bank | None:
    """The bank a statement's file name says, or None (no password needed to tell)."""
    name = re.sub(r"^[0-9a-f]{8}_", "", os.path.basename(path))
    return next((b for b in BANKS if b.file.search(name)), None)


def bank_from_text(text: str) -> Bank | None:
    return next((b for b in BANKS if any(m in text for m in b.markers)), None)


def password_for(path: str) -> str | None:
    """The settings password for this file's bank (by file name), or None."""
    b = bank_from_name(path)
    return next((os.environ[k] for k in (b.passwords if b else ()) if os.environ.get(k)), None)


def bank_of(pdf_path: str, password: str | None = None) -> Bank:
    """The bank a statement is from: its page-1 text, else its file name, else the registry's fallback."""
    with pdfplumber.open(pdf_path, password=password) as pdf:
        text = pdf.pages[0].extract_text() or ""
    return bank_from_text(text) or bank_from_name(pdf_path) or BANKS[-1]


def extract(pdf_path: str, password: str | None = None):
    """Public helper: a statement PDF (any registered bank) -> list of ledger-row dicts."""
    return bank_of(pdf_path, password).parse(pdf_path, password)


def write_csv(rows, dst):
    """Written whole, then renamed over dst: a crash or a build reading it at the same moment never sees half a ledger.
    The temporary name ends in .csv, so .gitignore's workspace/*.csv covers a leftover one."""
    tmp = os.path.join(os.path.dirname(dst), ".tmp-" + os.path.basename(dst))
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    try:
        os.replace(tmp, dst)
    except PermissionError:  # Windows won't replace a file another program has open
        os.remove(tmp)
        sys.exit(f"Can't update {dst}: close it in the program that has it open (Excel?), then try again.")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--password=")]
    if len(args) != 2:
        print("Usage: extract_ledger.py IN.pdf OUT.csv [--password=...]", file=sys.stderr)
        return 2
    src, dst = args

    # --password= wins, then the settings password for this file's bank, then ask.
    typed = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--password=")]
    pw = typed[0] if typed else password_for(src)
    try:
        bank = bank_of(src, pw)
    except (
        PdfminerException
    ):  # wrong or missing password (pdfplumber wraps every open failure in this): ask, if someone can
        if not sys.stdin.isatty():
            raise
        named = bank_from_name(src)
        pw = getpass.getpass(f"{named.name if named else 'PDF'} password for {os.path.basename(src)}: ")
        bank = bank_of(src, pw)
    rows = bank.parse(src, pw)  # prints a CHECK line for anything that doesn't reconcile
    stamp_ids(rows)
    write_csv(rows, dst)
    print(f"Wrote {len(rows)} {bank.name} transactions to {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Extract a Krungthai bank-statement PDF into a clean CSV ledger.

Columns: Date, Description, Amount, Balance
  - Amount is signed: deposits positive (income), withdrawals negative (expense).
  - Withdrawal vs deposit is decided by the amount's x-position under the
    statement's own column headers, not by guessing.

Usage:
    python extract_ledger.py [INPUT_PDF] [OUTPUT_CSV]
Defaults: statement_clean.pdf -> ledger.csv
"""
import csv
import os
import re
import sys

import pdfplumber

import config  # loads the project's env settings into os.environ
from txid import stamp_ids

MONEY = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
TIME = re.compile(r"^\d{2}:\d{2}$")

# Column x-centre boundaries (from statement layout):
#   withdrawal ~369 | deposit ~429 | balance ~503 | branch(514) ~550
WD_MAX, DEP_MAX = 400, 470

# --- Semantic categories keyed off the reference in the detail column ---
# Direction (money out vs in) flips the meaning of the same counterparty.
# Optional, personal: account numbers that appear in the transaction detail. Set them in the
# env settings (see .env.example); a blank value turns that category off.
REF_CASH = os.environ.get("LEDGER_CASH_REF", "")    # your own cash channel
REF_PEER = os.environ.get("LEDGER_PEER_REF", "")    # a person you lend to
REF_STOCK = os.environ.get("LEDGER_STOCK_REF", "")  # your stock/investment account

# Fallback: map the Thai transaction-type prefix to an English label.
TYPE_EN = {
    "จ่ายค่าสินค้า/บริการ": "Bill / purchase",
    "โอนเงินออก-พร้อมเพย์": "PromptPay out",
    "โอนเงินออก": "Transfer out",
    "เงินโอนเข้า-พร้อมเพย์": "PromptPay in",
    "เงินโอนเข้า": "Transfer in",
    "ดอกเบี้ยและภาษี": "Interest & tax",
    "ฝากเงินผ่าน ADM": "ADM cash deposit",
}

# Statement footer boilerplate that can bleed into a last-of-page row's detail.
FOOTER = re.compile(r"\s*บริษัท ธนาคารกรุงไทย.*$")


def categorize(desc: str, amount: float) -> str:
    """Meaning of a row, from its reference number and money direction."""
    out = amount < 0
    if REF_CASH and REF_CASH in desc:
        return "Cash withdrawal" if out else "Cash deposit"
    if REF_PEER and REF_PEER in desc:
        return "Lent out" if out else "Loan repaid to me"
    if REF_STOCK and REF_STOCK in desc:
        return "Stock investment" if out else "Stock return"
    ttype = desc.split(" (")[0].strip()
    return TYPE_EN.get(ttype, ttype)


def to_iso(d: str) -> str:
    """'DD/MM/YY' in short Buddhist era -> 'YYYY-MM-DD' Gregorian."""
    dd, mm, yy = d.split("/")
    be = 2500 + int(yy)
    return f"{be - 543:04d}-{mm}-{dd}"


def classify(cx: float) -> str:
    if cx < WD_MAX:
        return "wd"
    if cx < DEP_MAX:
        return "dep"
    return "bal"


def is_branch(w) -> bool:
    # branch-code column sits far right (x0 ~544); balance ends well before 540
    return w["x0"] > 540


def group_lines(words):
    """Cluster words into visual lines by their vertical position."""
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 2), []).append(w)
    out = []
    for k in sorted(lines):
        row = sorted(lines[k], key=lambda w: w["x0"])
        out.append(row)
    return out


def parse(pdf_path: str, password: str | None = None):
    records = []
    cur = None
    with pdfplumber.open(pdf_path, password=password) as pdf:
        for pg in pdf.pages:
            for line in group_lines(pg.extract_words()):
                texts = [w["text"] for w in line]
                if texts and DATE.match(texts[0]):
                    if cur:
                        records.append(cur)
                    cur = {"date": texts[0], "time": "", "desc": [],
                           "wd": None, "dep": None, "bal": None}
                    for w in line[1:]:
                        t = w["text"]
                        if MONEY.match(t):
                            col = classify((w["x0"] + w["x1"]) / 2)
                            cur[col] = float(t.replace(",", ""))
                        elif is_branch(w):
                            continue
                        else:
                            cur["desc"].append(t)
                elif cur is not None:
                    # continuation line: time + any wrapped detail text
                    for w in line:
                        t = w["text"]
                        if TIME.match(t) and not cur["time"]:
                            cur["time"] = t
                        elif is_branch(w) or MONEY.match(t):
                            continue
                        else:
                            cur["desc"].append(t)
            if cur:
                records.append(cur)
                cur = None
    return records


HEADER = ["Date", "Description", "Category", "Amount", "Balance", "ID"]   # ID: see txid.py


def build_rows(records):
    """Turn raw parsed records into ledger rows + a balance-continuity report.

    Returns (rows, stats) where each row is a dict keyed by HEADER names and
    stats holds withdrawal/deposit totals and any balance-jump warnings.
    """
    rows, wd_sum, dep_sum, wd_n, dep_n = [], 0.0, 0.0, 0, 0
    prev_bal = None
    warnings = []
    for r in records:
        amount = (r["dep"] or 0.0) - (r["wd"] or 0.0)
        if r["dep"]:
            dep_sum += r["dep"]; dep_n += 1
        if r["wd"]:
            wd_sum += r["wd"]; wd_n += 1
        if prev_bal is not None and r["bal"] is not None:
            if abs(prev_bal + amount - r["bal"]) > 0.01:
                warnings.append(f"{r['date']} {r['time']}: balance jump "
                                f"{prev_bal:.2f}+{amount:.2f}!={r['bal']:.2f}")
        prev_bal = r["bal"] if r["bal"] is not None else prev_bal

        when = f"{to_iso(r['date'])} {r['time']}".strip()
        desc = re.sub(r"\s+", " ", " ".join(r["desc"])).strip()
        desc = FOOTER.sub("", desc).strip()
        rows.append({
            "Date": when, "Description": desc,
            "Category": categorize(desc, amount),
            "Amount": f"{amount:.2f}",
            "Balance": f"{r['bal']:.2f}" if r["bal"] is not None else "",
        })
    stats = {"wd_n": wd_n, "wd_sum": wd_sum, "dep_n": dep_n,
             "dep_sum": dep_sum, "warnings": warnings}
    return rows, stats


def extract(pdf_path: str, password: str | None = None):
    """Public helper: a statement PDF -> list of ledger-row dicts."""
    return build_rows(parse(pdf_path, password))[0]


def write_csv(rows, dst):
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "statement_clean.pdf"
    dst = sys.argv[2] if len(sys.argv) > 2 else "ledger.csv"

    rows, stats = build_rows(parse(src))
    stamp_ids(rows)
    write_csv(rows, dst)

    print(f"Wrote {len(rows)} transactions to {dst}")
    print(f"  Withdrawals: {stats['wd_n']} rows, total {stats['wd_sum']:,.2f}")
    print(f"  Deposits:    {stats['dep_n']} rows, total {stats['dep_sum']:,.2f}")
    if stats["warnings"]:
        print(f"  WARNINGS ({len(stats['warnings'])}):")
        for w in stats["warnings"][:10]:
            print("   ", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

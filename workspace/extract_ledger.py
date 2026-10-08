#!/usr/bin/env python3
"""Extract a Krungthai (KTB) or Kasikorn (KBank) statement PDF into a clean CSV ledger.

Columns: Date, Description, Category, Amount, Balance, ID, Bank
  - Amount is signed: deposits positive (income), withdrawals negative (expense).
  - KTB: withdrawal vs deposit is decided by the amount's x-position under the
    statement's own column headers, not by guessing.
  - KBank: decided by the balance change, cross-checked against the x-position and
    the statement's own totals (a mismatch rejects the file).

Usage:
    python extract_ledger.py [INPUT_PDF] [OUTPUT_CSV]
    python extract_ledger.py IN.pdf OUT.csv --password=...
The password comes from --password=, else KBANK_PW for STM_* files / KTB_PW for others (see
.env.example), else it is asked for (typed, hidden).
Defaults: statement_clean.pdf -> ledger.csv
"""
import csv
import getpass
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
    # KBank
    "ชำระเงิน": "Bill / purchase",
    "โอนเงิน": "Transfer out",
    "รับโอนเงิน": "Transfer in",
    "รับดอกเบี้ยเงินฝาก": "Interest & tax",
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


HEADER = ["Date", "Description", "Category", "Amount", "Balance", "ID", "Bank"]   # ID: see txid.py


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
            "Bank": "KTB",
        })
    stats = {"wd_n": wd_n, "wd_sum": wd_sum, "dep_n": dep_n,
             "dep_sum": dep_sum, "warnings": warnings}
    return rows, stats


# --- KBank (Kasikorn) -------------------------------------------------------------------------
# One amount column for both directions: money out sits left (right edge ~252), money in is
# right-aligned (~267); balance ends ~329; channel starts ~333; detail starts ~404.
KB_DATE = re.compile(r"^\d{2}-\d{2}-\d{2}$")   # DD-MM-YY, Christian era
KB_OUT_MAX, KB_AMT_MAX, KB_BAL_MAX = 260, 300, 335   # right edge (x1) boundaries
KB_CHAN_MIN, KB_DETAIL_MIN = 330, 400                # left edge (x0) boundaries


def _num(t: str) -> float:
    return float(t.replace(",", ""))


def parse_kbank(pdf_path: str, password: str | None = None):
    """KBank statement -> ledger rows. Raises ValueError if the rows don't add up to the statement's totals."""
    rows, cur, prev, opening = [], None, None, None
    with pdfplumber.open(pdf_path, password=password) as pdf:
        head = pdf.pages[0].extract_text() or ""
        for pg in pdf.pages:
            last_top = None
            for line in group_lines(pg.extract_words()):
                if KB_DATE.match(line[0]["text"]):
                    cur = {"date": line[0]["text"], "time": "", "desc": [], "chan": [], "detail": [],
                           "amt": None, "out_pos": None, "bal": None}
                    rows.append(cur)
                    cols = line[1:]
                elif cur is not None and last_top is not None and line[0]["top"] - last_top <= 14:
                    cols = line   # wrapped text belonging to the row above
                else:
                    continue      # header, totals, footer
                last_top = line[0]["top"]
                for w in cols:
                    t, x0, x1 = w["text"], w["x0"], w["x1"]
                    if TIME.match(t) and x0 < 120 and not cur["time"]:
                        cur["time"] = t
                    elif MONEY.match(t) and x1 <= KB_AMT_MAX:
                        cur["amt"], cur["out_pos"] = _num(t), x1 < KB_OUT_MAX
                    elif MONEY.match(t) and x1 <= KB_BAL_MAX:
                        cur["bal"] = _num(t)
                    elif x0 >= KB_DETAIL_MIN:
                        cur["detail"].append(t)
                    elif x0 >= KB_CHAN_MIN:
                        cur["chan"].append(t)
                    else:
                        cur["desc"].append(t)
            cur = None   # never continue a row across a page break

    out, wd_sum, dep_sum = [], 0.0, 0.0
    for r in rows:
        if r["amt"] is None:              # ยอดยกมา: opening balance, not a transaction
            opening = r["bal"] if opening is None else opening
            prev = r["bal"]
            continue
        sign = -1 if r["out_pos"] else 1
        if prev is not None and abs(abs(r["bal"] - prev) - r["amt"]) < 0.011:
            by_balance = -1 if r["bal"] < prev else 1
            if by_balance != sign:
                raise ValueError(f"KBank {r['date']} {r['time']}: column position and balance disagree on direction")
            sign = by_balance
        elif prev is not None:
            raise ValueError(f"KBank {r['date']} {r['time']}: balance jump {prev:.2f} -> {r['bal']:.2f} "
                             f"for amount {r['amt']:.2f}")
        prev = r["bal"]
        amount = sign * r["amt"]
        wd_sum, dep_sum = wd_sum + (r["amt"] if sign < 0 else 0), dep_sum + (r["amt"] if sign > 0 else 0)
        dd, mm, yy = r["date"].split("-")
        desc = " ".join(r["desc"])
        if r["chan"]:
            desc += f" ({' '.join(r['chan'])})"
        if r["detail"]:
            desc += " " + " ".join(r["detail"])
        out.append({"Date": f"20{yy}-{mm}-{dd} {r['time']}".strip(), "Description": desc,
                    "Category": categorize(desc, amount), "Amount": f"{amount:.2f}",
                    "Balance": f"{r['bal']:.2f}", "Bank": "KBANK"})

    # The statement prints its own totals; the parsed rows must reproduce them exactly.
    def total(label):
        m = re.search(label + r"\s+\d+\s+รายการ\s+([\d,]+\.\d{2})", head)
        return _num(m.group(1)) if m else 0.0
    end = re.search(r"ยอดยกไป\s+([\d,]+\.\d{2})", head)
    checks = [("withdrawals", wd_sum, total("รวมถอนเงิน")), ("deposits", dep_sum, total("รวมฝากเงิน"))]
    if end and prev is not None:
        checks.append(("closing balance", prev, _num(end.group(1))))
    for what, got, want in checks:
        if abs(got - want) > 0.011:
            raise ValueError(f"KBank {what}: parsed {got:,.2f} but the statement says {want:,.2f}")
    return out


def is_kbank(path: str) -> bool:
    """KBank statements are named STM_...; Gmail downloads prefix the name with 8 hex chars + '_'."""
    return re.sub(r"^[0-9a-f]{8}_", "", os.path.basename(path)).startswith("STM")


def password_for(path: str) -> str | None:
    """The settings password for this file's bank (STATEMENT_PW is the old name of KTB_PW)."""
    if is_kbank(path):
        return os.environ.get("KBANK_PW") or None
    return os.environ.get("KTB_PW") or os.environ.get("STATEMENT_PW") or None


def bank_of(pdf_path: str, password: str | None = None) -> str:
    with pdfplumber.open(pdf_path, password=password) as pdf:
        text = pdf.pages[0].extract_text() or ""
    return "KBANK" if "K Contact Center" in text or "ถอนเงิน / ฝากเงิน" in text else "KTB"


def extract(pdf_path: str, password: str | None = None):
    """Public helper: a statement PDF (KTB or KBank) -> list of ledger-row dicts."""
    if bank_of(pdf_path, password) == "KBANK":
        return parse_kbank(pdf_path, password)
    return build_rows(parse(pdf_path, password))[0]


def write_csv(rows, dst):
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--password=")]
    src = args[0] if len(args) > 0 else "statement_clean.pdf"
    dst = args[1] if len(args) > 1 else "ledger.csv"

    # --password= wins, then the settings password for this file's bank, then ask.
    typed = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--password=")]
    pw = typed[0] if typed else password_for(src)
    try:
        bank_of(src, pw)
    except Exception:           # wrong/missing password (the error type varies by PDF): ask, if someone can answer
        if not sys.stdin.isatty():
            raise
        pw = getpass.getpass(f"{'KBank' if is_kbank(src) else 'KTB'} password for {os.path.basename(src)}: ")
    if bank_of(src, pw) == "KBANK":
        rows = parse_kbank(src, pw)
        stamp_ids(rows)
        write_csv(rows, dst)
        print(f"Wrote {len(rows)} KBank transactions to {dst} (totals match the statement)")
        return 0
    rows, stats = build_rows(parse(src, pw))
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

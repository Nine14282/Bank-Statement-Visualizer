#!/usr/bin/env python3
"""Extract a Krungthai (KTB) or Kasikorn (KBank) statement PDF into a clean CSV ledger.

Columns: Date, Description, Category, Amount, Balance, ID, Bank
  - Amount is signed: deposits positive (income), withdrawals negative (expense).
  - KTB: withdrawal vs deposit is decided by the amount's x-position under the
    statement's own column headers, not by guessing.
  - KBank: decided by the balance change, cross-checked against the x-position and
    the statement's own totals.
  - A row that doesn't reconcile prints a CHECK line and is still imported, never dropped.

Usage:
    python extract_ledger.py [INPUT_PDF] [OUTPUT_CSV]
    python extract_ledger.py IN.pdf OUT.csv --password=...
The password comes from --password=, else the password setting of the bank the file name points to
(BANKS below: KBANK_PW for STM_* files, KTB_PW for others; see .env.example), else it is asked for
(typed, hidden).
Defaults: statement_clean.pdf -> ledger.csv
"""
import csv
import getpass
import os
import re
import sys

from collections.abc import Callable
from dataclasses import dataclass

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
    "หักบัญชีอัตโนมัติ": "Auto debit",
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


# The statement's closing summary: "จำนวนหน้าทั้งหมด N C/F", then "รายการถอนทั้งหมด <count> <total>" and
# "รายการฝากทั้งหมด <count> <total>". It ends the last row (else its words were glued onto that row's description)
# and its counts/totals are what the parsed rows must reproduce.
SUMMARY = "จำนวนหน้าทั้งหมด"
TOTALS = {"รายการถอนทั้งหมด": "wd", "รายการฝากทั้งหมด": "dep"}


def parse(pdf_path: str, password: str | None = None):
    """KTB statement -> (raw records, the statement's own totals {"wd": (count, sum), "dep": ...})."""
    records, totals = [], {}
    cur = None
    with pdfplumber.open(pdf_path, password=password) as pdf:
        for pg in pdf.pages:
            for line in group_lines(pg.extract_words()):
                texts = [w["text"] for w in line]
                if texts and texts[0] == SUMMARY:
                    if cur:
                        records.append(cur)
                    cur = None
                    continue
                if texts and texts[0] in TOTALS and len(texts) >= 3 and MONEY.match(texts[2]):
                    totals[TOTALS[texts[0]]] = (int(texts[1]), float(texts[2].replace(",", "")))
                    continue
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
    return records, totals


def check_totals(stats, totals):
    """Messages for counts/totals the rows don't reproduce (empty = all match). The statement is always right, so a
    mismatch means this parser misread a row: it is reported, and the rows are still imported, never dropped.
    A statement without the summary (another layout) is not compared."""
    out = []
    for col, label in (("wd", "withdrawals"), ("dep", "deposits")):
        if col not in totals:
            continue
        n, total = totals[col]
        got_n, got = stats[f"{col}_n"], stats[f"{col}_sum"]
        if got_n != n or abs(got - total) > 0.011:
            out.append(f"{label}: parsed {got_n} rows / {got:,.2f} but the statement says {n} / {total:,.2f}")
    return out


def report(name, problems):
    """Print parser self-check problems (the data is imported anyway) so a misread row is seen, not hidden."""
    for p in problems:
        print(f"  CHECK {name}: {p}  <- the statement is right; this row was read wrong, please report it")


HEADER = ["Date", "Description", "Category", "Amount", "Balance", "ID", "Bank"]   # ID: see txid.py

INTEREST = "ดอกเบี้ยและภาษี"


def interest_last(records):
    """KTB prints the half-year interest row at the top of its day (01:xx) but with that day's *closing*
    balance: it is credited after the day's last transaction (e.g. 94.51 + 1.53 printed as 555.04, which is
    553.51, the day's last balance, + 1.53). Such a row is moved to the end of its day at 23:59 (the time
    KBank uses for interest) so the balance chain holds. A row whose balance already chains stays put."""
    out, held, prev = [], [], None
    for r in records:
        if held and r["date"] != held[0]["date"]:
            out += held
            held = []
        amt = (r["dep"] or 0.0) - (r["wd"] or 0.0)
        early = " ".join(r["desc"]).startswith(INTEREST) and prev is not None and r["bal"] is not None \
            and abs(prev + amt - r["bal"]) > 0.01
        if early:
            held.append({**r, "time": "23:59"})
        else:
            out.append(r)
            prev = r["bal"] if r["bal"] is not None else prev
    return out + held


def build_rows(records):
    """Turn raw parsed records into ledger rows + a balance-continuity report.

    Returns (rows, stats) where each row is a dict keyed by HEADER names and
    stats holds withdrawal/deposit totals and any balance-jump warnings.
    """
    rows, wd_sum, dep_sum, wd_n, dep_n = [], 0.0, 0.0, 0, 0
    prev_bal = None
    warnings = []
    for r in interest_last(records):
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
# One amount column for both directions, then the balance; the channel and detail columns follow. Amount and
# balance are read as the row's first two figures (layout-independent); direction comes from the balance.
# Positions measured on one statement, used only for text columns and as a direction fallback: money out's
# right edge ~252 vs money in ~267; channel starts ~333; detail starts ~404.
KB_DATE = re.compile(r"^\d{2}-\d{2}-\d{2}$")   # DD-MM-YY, Christian era
KB_OUT_MAX = 260                                 # amount right edge (x1) left of this = money out (fallback only)
KB_CHAN_MIN, KB_DETAIL_MIN = 330, 400            # left edge (x0) boundaries


def _num(t: str) -> float:
    return float(t.replace(",", ""))


def parse_kbank(pdf_path: str, password: str | None = None):
    """KBank statement -> ledger rows. Problems (rows that don't reconcile with the bank's balances or totals)
    are reported by name and the rows kept; nothing is dropped."""
    rows, cur = [], None
    with pdfplumber.open(pdf_path, password=password) as pdf:
        head = pdf.pages[0].extract_text() or ""
        for pg in pdf.pages:
            last_top = None
            for line in group_lines(pg.extract_words()):
                if KB_DATE.match(line[0]["text"]):
                    cur = {"date": line[0]["text"], "time": "", "desc": [], "chan": [], "detail": [], "money": []}
                    rows.append(cur)
                    cols, first = line[1:], True
                elif cur is not None and last_top is not None and line[0]["top"] - last_top <= 14:
                    cols, first = line, False   # wrapped text belonging to the row above
                else:
                    continue      # header, totals, footer
                last_top = line[0]["top"]
                for w in cols:
                    t, x0 = w["text"], w["x0"]
                    if TIME.match(t) and x0 < 120 and not cur["time"]:
                        cur["time"] = t
                    elif first and MONEY.match(t) and len(cur["money"]) < 2 and not cur["chan"] and not cur["detail"]:
                        # Amount and balance are the first two figures on the row, left to right, whatever the
                        # exact column positions (they move between layouts); figures inside the detail don't count.
                        cur["money"].append((w["x1"], _num(t)))
                    elif x0 >= KB_DETAIL_MIN:
                        cur["detail"].append(t)
                    elif x0 >= KB_CHAN_MIN:
                        cur["chan"].append(t)
                    else:
                        cur["desc"].append(t)
            cur = None   # never continue a row across a page break
    out, problems = kbank_amounts(rows)

    # The statement prints its own totals; the parsed rows should reproduce them exactly.
    # A total the statement doesn't print (other layout/language) is skipped, never compared against 0.
    def total(label):
        # (?:...) keeps the label's "Thai|English" alternation from splitting the whole pattern
        m = re.search(rf"(?:{label})\s+\d+\s+(?:รายการ|Items?|Transactions?)\s+([\d,]+\.\d{{2}})", head, re.I)
        return _num(m.group(1)) if m else None
    end = re.search(r"(?:ยอดยกไป|Ending Balance)\s+([\d,]+\.\d{2})", head, re.I)
    wd = sum(-float(r["Amount"]) for r in out if float(r["Amount"]) < 0)
    dep = sum(float(r["Amount"]) for r in out if float(r["Amount"]) > 0)
    last = float(out[-1]["Balance"]) if out else None
    for what, got, want in (("withdrawals", wd, total("รวมถอนเงิน|Total Withdrawal")),
                            ("deposits", dep, total("รวมฝากเงิน|Total Deposit")),
                            ("closing balance", last, _num(end.group(1)) if end else None)):
        if want is not None and got is not None and abs(got - want) > 0.011:
            problems.append(f"{what}: parsed {got:,.2f} but the statement says {want:,.2f}")
    report(os.path.basename(pdf_path), problems)
    return out


def kbank_amounts(rows):
    """Raw KBank rows -> (ledger rows, problems). Signed amounts come from the bank's own running balance:
    balance down = money out. The amount column's position is only a fallback (first row, or a row whose balance
    doesn't move by its amount, which is then reported and kept)."""
    out, problems, prev = [], [], None
    for r in rows:
        money = r["money"]
        if len(money) < 2:                # ยอดยกมา (opening / brought-forward): balance only, not a transaction
            if money:
                prev = money[-1][1]
            continue
        (ax1, amt), (_, bal) = money[0], money[1]
        if prev is not None and abs(abs(bal - prev) - amt) < 0.011:
            sign = -1 if bal < prev else 1
        else:
            sign = -1 if ax1 < KB_OUT_MAX else 1
            if prev is not None:
                problems.append(f"{r['date']} {r['time']}: balance {prev:,.2f} -> {bal:,.2f} does not move by "
                                f"the amount {amt:,.2f}")
        prev = bal
        amount = sign * amt
        dd, mm, yy = r["date"].split("-")
        desc = " ".join(r["desc"])
        if r["chan"]:
            desc += f" ({' '.join(r['chan'])})"
        if r["detail"]:
            desc += " " + " ".join(r["detail"])
        out.append({"Date": f"20{yy}-{mm}-{dd} {r['time']}".strip(), "Description": desc,
                    "Category": categorize(desc, amount), "Amount": f"{amount:.2f}",
                    "Balance": f"{bal:.2f}", "Bank": "KBANK"})
    return out, problems


def parse_ktb(pdf_path: str, password: str | None = None):
    """Krungthai statement -> ledger rows; anything that doesn't reconcile is reported (see report)."""
    records, totals = parse(pdf_path, password)
    rows, stats = build_rows(records)
    report(os.path.basename(pdf_path), stats["warnings"] + check_totals(stats, totals))
    return rows


# --- Bank registry ---------------------------------------------------------------------------
# Adding a bank = one Bank(...) entry here (plus a parser); every other script, the setup wizard and
# the password lookup read this list. Order matters: the first bank whose name pattern / page-1 text
# matches wins, and the last entry is the fallback for a statement nothing else claims.
@dataclass(frozen=True)
class Bank:
    id: str                       # the ledger's Bank column value
    name: str                     # shown to people
    passwords: tuple[str, ...]    # settings holding its PDF password; the setup wizard saves to the first
    file: re.Pattern              # its statement file name (Gmail's 8-hex-char prefix is stripped first)
    markers: tuple[str, ...]      # text on page 1 that only its statements have
    parse: Callable[[str, str | None], list]


BANKS: tuple[Bank, ...] = (
    Bank("KBANK", "KBank", ("KBANK_PW",), re.compile(r"^STM"), ("K Contact Center", "ถอนเงิน / ฝากเงิน"), parse_kbank),
    Bank("KTB", "Krungthai", ("KTB_PW", "STATEMENT_PW"), re.compile(r"Statement"), ("ธนาคารกรุงไทย",), parse_ktb),
)
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
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def selfcheck():
    """python extract_ledger.py --selfcheck: the interest rule on the 30/06/69 layout seen in real statements."""
    rec = lambda t, d, wd, dep, bal: {"date": "30/06/69", "time": t, "desc": d.split(), "wd": wd, "dep": dep, "bal": bal}
    day = [rec("21:00", "จ่ายค่าสินค้า/บริการ x", 90.0, None, 94.51),
           rec("01:47", "ดอกเบี้ยและภาษี (IIPS)", 0.0, 1.53, 555.04),      # printed first, closing balance
           rec("08:44", "จ่ายค่าสินค้า/บริการ y", 15.0, None, 79.51),
           rec("14:24", "เงินโอนเข้า-พร้อมเพย์ z", None, 474.0, 553.51)]
    rows, st = build_rows(day)
    assert [r["Date"][-5:] for r in rows] == ["21:00", "08:44", "14:24", "23:59"], rows
    assert not st["warnings"], st["warnings"]
    ok = [rec("01:47", "ดอกเบี้ยและภาษี (IIPS)", 0.0, 1.53, 96.04)]          # already chains: left in place
    assert [r["Date"][-5:] for r in build_rows(day[:1] + ok)[0]] == ["21:00", "01:47"]

    # KBank: direction follows the bank's balance even when the amount sits in the "money in" position; a row
    # that doesn't reconcile is kept (sign from position) and reported, never dropped.
    kb = lambda d, money: {"date": d, "time": "10:00", "desc": ["x"], "chan": [], "detail": [], "money": money}
    out, problems = kbank_amounts([kb("01-05-26", [(329, 100.0)]),                # opening balance
                                   kb("02-05-26", [(267, 30.0), (329, 70.0)]),    # "in" position, balance fell
                                   kb("03-05-26", [(252, 20.0), (329, 40.0)])])   # balance moved 30, amount 20
    assert [r["Amount"] for r in out] == ["-30.00", "-20.00"], out
    assert len(problems) == 1 and "03-05-26" in problems[0], problems
    print("selfcheck ok")


def main() -> int:
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
        return 0
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
        named = bank_from_name(src)
        pw = getpass.getpass(f"{named.name if named else 'PDF'} password for {os.path.basename(src)}: ")
    bank = bank_of(src, pw)
    if bank.id != "KTB":
        rows = bank.parse(src, pw)     # prints a CHECK line for anything that doesn't reconcile
        stamp_ids(rows)
        write_csv(rows, dst)
        print(f"Wrote {len(rows)} {bank.name} transactions to {dst}")
        return 0
    records, totals = parse(src, pw)
    rows, stats = build_rows(records)
    report(os.path.basename(src), check_totals(stats, totals))
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

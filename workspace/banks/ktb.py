"""Krungthai (KTB) statements: withdrawal vs deposit is decided by the amount's x-position under the
statement's own column headers, not by guessing; counts/sums are checked against its printed totals."""
import os
import re

import pdfplumber

from .common import MONEY, TIME, Bank, categorize, group_lines, report

DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")   # DD/MM/YY, Buddhist era

# Column x-centre boundaries (from statement layout):
#   withdrawal ~369 | deposit ~429 | balance ~503 | branch(514) ~550
WD_MAX, DEP_MAX = 400, 470

# Thai transaction-type prefix -> English label (the category when no reference number matches).
TYPES = {
    "จ่ายค่าสินค้า/บริการ": "Bill / purchase",
    "โอนเงินออก-พร้อมเพย์": "PromptPay out",
    "โอนเงินออก": "Transfer out",
    "เงินโอนเข้า-พร้อมเพย์": "PromptPay in",
    "เงินโอนเข้า": "Transfer in",
    "ดอกเบี้ยและภาษี": "Interest & tax",
    "ฝากเงินผ่าน ADM": "ADM cash deposit",
    "หักบัญชีอัตโนมัติ": "Auto debit",
}

# Statement footer boilerplate that can bleed into a last-of-page row's detail.
FOOTER = re.compile(r"\s*บริษัท ธนาคารกรุงไทย.*$")

# The statement's closing summary: "จำนวนหน้าทั้งหมด N C/F", then "รายการถอนทั้งหมด <count> <total>" and
# "รายการฝากทั้งหมด <count> <total>". It ends the last row (else its words were glued onto that row's description)
# and its counts/totals are what the parsed rows must reproduce.
SUMMARY = "จำนวนหน้าทั้งหมด"
TOTALS = {"รายการถอนทั้งหมด": "wd", "รายการฝากทั้งหมด": "dep"}

INTEREST = "ดอกเบี้ยและภาษี"


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


def read(pdf_path: str, password: str | None = None):
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
            "Category": categorize(desc, amount, TYPES),
            "Amount": f"{amount:.2f}",
            "Balance": f"{r['bal']:.2f}" if r["bal"] is not None else "",
            "Bank": "KTB",
        })
    stats = {"wd_n": wd_n, "wd_sum": wd_sum, "dep_n": dep_n,
             "dep_sum": dep_sum, "warnings": warnings}
    return rows, stats


def parse(pdf_path: str, password: str | None = None):
    """Krungthai statement -> ledger rows; anything that doesn't reconcile is reported (see report)."""
    records, totals = read(pdf_path, password)
    rows, stats = build_rows(records)
    report(os.path.basename(pdf_path), stats["warnings"] + check_totals(stats, totals))
    return rows


def selfcheck():
    """The interest rule on the 30/06/69 layout seen in real statements."""
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


def parse_notice(text):
    """Krungthai NEXT "payment done" email (no PDF, outgoing only, no balance) -> manual_entries row dict, or None
    if it is not a completed payment."""
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
            "Category": kind, "Amount": f"{-total:.2f}", "Balance": "", "Bank": "KTB"}


def notice_window(stmt_row):
    """Statements can post bills minutes to hours after the email's payment time: 4h. "Future Amount" rows are payments
    made after KTB's nightly cut-off (~23:00), posted ~01:30-02:30 the next day: 6h, and the email's paid time wins."""
    return (6, True) if "Future Amount" in stmt_row["Description"] else (4, False)


BANK = Bank("KTB", "Krungthai", ("KTB_PW", "STATEMENT_PW"), re.compile(r"Statement"), ("ธนาคารกรุงไทย",),
            parse, selfcheck,
            statement_mail='from:noreply@krungthai.com "ส่งรายการเดินบัญชีเงินฝาก" has:attachment',
            notice_mail='from:noreply@krungthai.com "แจ้งผลการ"',
            parse_notice=parse_notice, notice_window=notice_window)

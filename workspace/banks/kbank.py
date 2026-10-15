"""Kasikorn (KBank) statements: one amount column for both directions, then the balance; the channel and
detail columns follow. Amount and balance are read as the row's first two figures (layout-independent);
direction comes from the balance, cross-checked against the x-position and the statement's own totals.
Positions measured on one statement, used only for text columns and as a direction fallback: money out's
right edge ~252 vs money in ~267; channel starts ~333; detail starts ~404."""

import os
import re

import pdfplumber

from .common import MONEY, TIME, Bank, categorize, group_lines, num, report

DATE = re.compile(r"^\d{2}-\d{2}-\d{2}$")  # DD-MM-YY, Christian era
OUT_MAX = 260  # amount right edge (x1) left of this = money out (fallback only)
CHAN_MIN, DETAIL_MIN = 330, 400  # left edge (x0) boundaries

# Thai transaction-type prefix -> English label (the category when no reference number matches).
TYPES = {
    "ชำระเงิน": "Bill / purchase",
    "โอนเงิน": "Transfer out",
    "รับโอนเงิน": "Transfer in",
    "รับดอกเบี้ยเงินฝาก": "Interest & tax",
}


def parse(pdf_path: str, password: str | None = None):
    """KBank statement -> ledger rows. Problems (rows that don't reconcile with the bank's balances or totals)
    are reported by name and the rows kept; nothing is dropped."""
    rows, cur = [], None
    with pdfplumber.open(pdf_path, password=password) as pdf:
        head = pdf.pages[0].extract_text() or ""
        for pg in pdf.pages:
            last_top = None
            for line in group_lines(pg.extract_words()):
                if DATE.match(line[0]["text"]):
                    cur = {"date": line[0]["text"], "time": "", "desc": [], "chan": [], "detail": [], "money": []}
                    rows.append(cur)
                    cols, first = line[1:], True
                elif cur is not None and last_top is not None and line[0]["top"] - last_top <= 14:
                    cols, first = line, False  # wrapped text belonging to the row above
                else:
                    continue  # header, totals, footer
                last_top = line[0]["top"]
                for w in cols:
                    t, x0 = w["text"], w["x0"]
                    if TIME.match(t) and x0 < 120 and not cur["time"]:
                        cur["time"] = t
                    elif first and MONEY.match(t) and len(cur["money"]) < 2 and not cur["chan"] and not cur["detail"]:
                        # Amount and balance are the first two figures on the row, left to right, whatever the
                        # exact column positions (they move between layouts); figures inside the detail don't count.
                        cur["money"].append((w["x1"], num(t)))
                    elif x0 >= DETAIL_MIN:
                        cur["detail"].append(t)
                    elif x0 >= CHAN_MIN:
                        cur["chan"].append(t)
                    else:
                        cur["desc"].append(t)
            cur = None  # never continue a row across a page break
    out, problems = amounts(rows)

    # The statement prints its own totals; the parsed rows should reproduce them exactly.
    # A total the statement doesn't print (other layout/language) is skipped, never compared against 0.
    def total(label):
        # (?:...) keeps the label's "Thai|English" alternation from splitting the whole pattern
        m = re.search(rf"(?:{label})\s+\d+\s+(?:รายการ|Items?|Transactions?)\s+([\d,]+\.\d{{2}})", head, re.I)
        return num(m.group(1)) if m else None

    end = re.search(r"(?:ยอดยกไป|Ending Balance)\s+([\d,]+\.\d{2})", head, re.I)
    wd = sum(-float(r["Amount"]) for r in out if float(r["Amount"]) < 0)
    dep = sum(float(r["Amount"]) for r in out if float(r["Amount"]) > 0)
    last = float(out[-1]["Balance"]) if out else None
    for what, got, want in (
        ("withdrawals", wd, total("รวมถอนเงิน|Total Withdrawal")),
        ("deposits", dep, total("รวมฝากเงิน|Total Deposit")),
        ("closing balance", last, num(end.group(1)) if end else None),
    ):
        if want is not None and got is not None and abs(got - want) > 0.011:
            problems.append(f"{what}: parsed {got:,.2f} but the statement says {want:,.2f}")
    report(os.path.basename(pdf_path), problems)
    return out


def amounts(rows):
    """Raw KBank rows -> (ledger rows, problems). Signed amounts come from the bank's own running balance:
    balance down = money out. The amount column's position is only a fallback (first row, or a row whose balance
    doesn't move by its amount, which is then reported and kept)."""
    out, problems, prev = [], [], None
    for r in rows:
        money = r["money"]
        if len(money) < 2:  # ยอดยกมา (opening / brought-forward): balance only, not a transaction
            if money:
                prev = money[-1][1]
            continue
        (ax1, amt), (_, bal) = money[0], money[1]
        if prev is not None and abs(abs(bal - prev) - amt) < 0.011:
            sign = -1 if bal < prev else 1
        else:
            sign = -1 if ax1 < OUT_MAX else 1
            if prev is not None:
                problems.append(
                    f"{r['date']} {r['time']}: balance {prev:,.2f} -> {bal:,.2f} does not move by the amount {amt:,.2f}"
                )
        prev = bal
        amount = sign * amt
        dd, mm, yy = r["date"].split("-")
        desc = " ".join(r["desc"])
        if r["chan"]:
            desc += f" ({' '.join(r['chan'])})"
        if r["detail"]:
            desc += " " + " ".join(r["detail"])
        out.append(
            {
                "Date": f"20{yy}-{mm}-{dd} {r['time']}".strip(),
                "Description": desc,
                "Category": categorize(desc, amount, TYPES),
                "Amount": f"{amount:.2f}",
                "Balance": f"{bal:.2f}",
                "Bank": "KBANK",
            }
        )
    return out, problems


def parse_notice(text):
    """K PLUS "Result of Bill Payment / Funds Transfer / PromptPay Funds Transfer (Success)" email -> manual_entries
    row dict, or None if it is not a completed payment. Reads the English half (Western-calendar date, with seconds).
    Its Available Balance is left out, as KTB notices have none: it can differ from the statement's balance."""

    def field(name):
        m = re.search(rf"^\s*{name}\s*:\s*(.+)$", text, re.M)
        return m.group(1).strip() if m else None

    subject = field("Subject") or ""
    when = re.search(r"Transaction Date\s*:\s*(\d\d)/(\d\d)/(\d{4})\s+(\d\d:\d\d)", text)
    amt = re.search(r"Amount \(THB\)\s*:\s*([\d,.]+)", text)
    if not (when and amt and "(Success)" in subject):
        return None
    fee = re.search(r"Fee \(THB\)\s*:\s*([\d,.]+)", text)
    dd, mm, yyyy, hm = when.groups()
    total = float(amt.group(1).replace(",", "")) + (float(fee.group(1).replace(",", "")) if fee else 0)
    if "PromptPay" in subject:
        kind, to = "PromptPay out", field("Received Name") or field("To PromptPay ID")
    elif "Transfer" in subject:
        kind, to = "Transfer out", field("Account Name") or field("To Account")
    else:  # "Result of Payment": bills and shop QR payments
        kind, to = "Bill / purchase", field("Company Name")
    return {
        "Date": f"{yyyy}-{mm}-{dd} {hm}",
        "Description": f"K PLUS {kind} (email) {to or ''}".strip(),
        "Category": kind,
        "Amount": f"{-total:.2f}",
        "Balance": "",
        "Bank": "KBANK",
    }


BANK = Bank(
    "KBANK",
    "KBank",
    ("KBANK_PW",),
    re.compile(r"^STM"),
    ("K Contact Center", "ถอนเงิน / ฝากเงิน"),
    parse,
    statement_mail='from:K-ElectronicDocument@kasikornbank.com subject:"E-statement for saving account" has:attachment',
    notice_mail='from:KPLUS@kasikornbank.com subject:"Result of" subject:Success',
    parse_notice=parse_notice,
)

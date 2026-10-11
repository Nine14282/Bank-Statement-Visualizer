"""What every bank parser shares: the Bank record, PDF-word helpers, categories and CHECK reporting."""
import os
import re

from collections.abc import Callable
from dataclasses import dataclass

import config  # loads the project's env settings into os.environ (the LEDGER_*_REF below)

MONEY = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")
TIME = re.compile(r"^\d{2}:\d{2}$")


@dataclass(frozen=True)
class Bank:
    id: str                       # the ledger's Bank column value
    name: str                     # shown to people
    passwords: tuple[str, ...]    # settings holding its PDF password; the setup wizard saves to the first
    file: re.Pattern              # its statement file name (Gmail's 8-hex-char prefix is stripped first)
    markers: tuple[str, ...]      # text on page 1 that only its statements have
    parse: Callable[[str, str | None], list]   # (pdf path, password) -> ledger rows (HEADER keys, no ID)
    selfcheck: Callable[[], None]               # asserts on synthetic rows; run by extract_ledger.py --selfcheck
    # Gmail (fetch_gmail.py). Fixed on purpose: only these exact senders/subjects are imported, so a stranger can't
    # mail a fake statement into the ledger. Blank = this bank isn't fetched from Gmail.
    statement_mail: str = ""                    # Gmail search for its statement-PDF emails
    notice_mail: str = ""                       # Gmail search for its per-payment "done" emails
    parse_notice: Callable[[str], dict | None] | None = None   # email text -> manual_entries row, or None
    # How update_statement matches a payment email to this bank's statement row: (hours apart at most, whether the
    # statement's time is only when the bank posted it, so the email's paid time replaces it).
    notice_window: Callable[[dict], tuple[int, bool]] = lambda stmt_row: (4, False)


# --- Semantic categories keyed off the reference in the detail column ---
# Direction (money out vs in) flips the meaning of the same counterparty.
# Optional, personal: account numbers that appear in the transaction detail. Set them in the
# env settings (see .env.example); a blank value turns that category off.
REF_CASH = os.environ.get("LEDGER_CASH_REF", "")    # your own cash channel
REF_PEER = os.environ.get("LEDGER_PEER_REF", "")    # a person you lend to
REF_STOCK = os.environ.get("LEDGER_STOCK_REF", "")  # your stock/investment account


def categorize(desc: str, amount: float, types: dict[str, str]) -> str:
    """Meaning of a row, from its reference number and money direction, else its bank's type label
    (`types`: Thai transaction-type prefix -> English)."""
    out = amount < 0
    if REF_CASH and REF_CASH in desc:
        return "Cash withdrawal" if out else "Cash deposit"
    if REF_PEER and REF_PEER in desc:
        return "Lent out" if out else "Loan repaid to me"
    if REF_STOCK and REF_STOCK in desc:
        return "Stock investment" if out else "Stock return"
    ttype = desc.split(" (")[0].strip()
    return types.get(ttype, ttype)


def num(t: str) -> float:
    return float(t.replace(",", ""))


def group_lines(words):
    """Cluster words into visual lines by their vertical position."""
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 2), []).append(w)
    return [sorted(lines[k], key=lambda w: w["x0"]) for k in sorted(lines)]


def report(name, problems):
    """Print parser self-check problems (the data is imported anyway) so a misread row is seen, not hidden."""
    for p in problems:
        print(f"  CHECK {name}: {p}  <- the statement is right; this row was read wrong, please report it")

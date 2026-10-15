"""Bank registry: one module per bank (its parser, layout constants, type labels and a
BANK = Bank(...) record), listed in BANKS below. Every other script, the setup wizard and the password
lookup read BANKS. Order matters: the first bank whose name pattern / page-1 text matches wins, and the
last entry is the fallback for a statement nothing else claims.

Adding a bank: copy the closest module (ktb.py or kbank.py), adapt it, add its BANK here, and a display
entry in web/src/lib/banks.ts."""

from . import kbank, ktb
from .common import Bank

BANKS: tuple[Bank, ...] = (kbank.BANK, ktb.BANK)


def manual_bank(row: dict) -> str:
    """Bank of a manual_entries.csv row: its Bank column (payment emails are written with it), else "Manual".
    ponytail: files written before the Bank column tell email rows by their text; drop once none are left."""
    if row.get("Bank"):
        return row["Bank"]
    desc = row.get("Description") or ""
    if "(email)" not in desc:
        return "Manual"
    return "KBANK" if desc.startswith("K PLUS ") else "KTB"

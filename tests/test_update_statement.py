"""update_statement: manual_bank, sort order, the per-PDF parse cache, own transfers and the main() merge."""

import csv
import os
import sys

import pytest

import build_dashboard
import update_statement as us
from txid import stamp_ids


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch, tmp_path):
    """Module state that outlives a test: USED, the passwords(cache=[]) default, CACHE, HERE (all into tmp_path)."""
    us.USED.clear()
    us.passwords.__defaults__[0].clear()
    monkeypatch.setattr(us, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(us, "HERE", str(tmp_path))
    monkeypatch.delenv(us.CACHE_SETTINGS[0], raising=False)
    yield
    us.USED.clear()
    us.passwords.__defaults__[0].clear()


# manual_bank / sort order


def test_manual_bank_from_email_wording():  # pre-Bank-column rows
    descs = ("Bill / purchase (email) SHOP", "K PLUS Transfer out (email) X", "K PLUS lunch")
    assert [us.manual_bank({"Description": d}) for d in descs] == ["KTB", "KBANK", "Manual"]


def test_manual_bank_keeps_an_explicit_bank():
    assert us.manual_bank({"Description": "Transfer out (email) X", "Bank": "KBANK"}) == "KBANK"


def test_same_minute_rows_keep_statement_order():
    same_minute = [{"Date": "2026-01-01 10:00", "Balance": b} for b in ("150.00", "140.00", "130.00")]
    assert [r["Balance"] for r in sorted(same_minute, key=us.by_minute)] == ["150.00", "140.00", "130.00"]


# parse cache


@pytest.fixture
def reads(monkeypatch):
    """read_pdf stand-in: records each call and prints a CHECK line (cached with the rows, shown on every run)."""
    calls = []

    def fake_read(path):
        calls.append(path)
        print("CHECK a.pdf: one row doesn't reconcile")
        return [
            {"Date": "2026-01-01 10:00", "Description": "x", "Category": "Food", "Amount": "-1.00", "Balance": "9.00"}
        ]

    monkeypatch.setattr(us, "read_pdf", fake_read)
    return calls


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1 first")
    return str(p)


def test_second_load_comes_from_the_cache(reads, pdf):
    first, second = us.load(pdf), us.load(pdf)
    assert first == second and len(reads) == 1, reads  # second load: the cache, no read


def test_cache_replays_the_check_warning_every_run(reads, pdf, capsys):
    us.load(pdf)
    log = capsys.readouterr().out
    us.load(pdf)
    log2 = capsys.readouterr().out
    assert "CHECK" in log and log2 == log, (log, log2)  # the warning shows on every run


def test_changed_setting_reads_again(reads, pdf, monkeypatch):
    us.load(pdf)
    monkeypatch.setenv(us.CACHE_SETTINGS[0], "changed")
    us.load(pdf)
    assert len(reads) == 2, reads


def test_changed_file_reads_again(reads, pdf):
    us.load(pdf)
    with open(pdf, "wb") as f:
        f.write(b"%PDF-1 second")
    us.load(pdf)
    assert len(reads) == 2, reads


def test_prune_keeps_only_what_the_run_used(reads, pdf, monkeypatch):
    us.load(pdf)
    monkeypatch.setenv(us.CACHE_SETTINGS[0], "changed")
    us.load(pdf)
    with open(pdf, "wb") as f:
        f.write(b"%PDF-1 second")
    us.load(pdf)
    assert len(os.listdir(us.CACHE)) == 3
    us.USED.clear()
    us.load(pdf)
    us.prune_cache()
    assert len(os.listdir(us.CACHE)) == 1, os.listdir(us.CACHE)  # older entries pruned


@pytest.mark.skipif(os.name == "nt", reason="Windows keeps files private by folder permissions, not mode bits")
def test_cache_entry_is_private(reads, pdf):
    old = os.umask(0)  # config sets 0o077, which would hide a wrong mode: the entry must be 0600 by itself
    try:
        us.load(pdf)
    finally:
        os.umask(old)
    entry = os.path.join(us.CACHE, os.listdir(us.CACHE)[0])
    assert oct(os.stat(entry).st_mode & 0o777) == "0o600"


# own transfers


def test_own_transfer_pairs_across_banks_only():
    # money out pairs with the same amount in at ANOTHER bank within 2 minutes; same bank never
    pair = stamp_ids(
        [
            {"Date": "2026-01-01 10:00", "Amount": "-100.00", "Category": "a", "Bank": "KTB"},
            {"Date": "2026-01-01 10:00", "Amount": "100.00", "Category": "b", "Bank": "KTB"},
            {"Date": "2026-01-01 10:01", "Amount": "100.00", "Category": "c", "Bank": "KBANK"},
        ]
    )
    us.own_transfers(pair)
    assert [r["Category"] for r in pair] == ["Own transfer", "b", "Own transfer"], pair


# main() with payment emails, all in tmp_path (never the real ledger or dashboard)


def row(date, desc, amt, bal, bank):
    return {"Date": date, "Description": desc, "Category": "c", "Amount": amt, "Balance": bal, "Bank": bank}


@pytest.fixture
def merged(monkeypatch, tmp_path):
    """Run main() over two fake statements plus manual_entries.csv; returns the written ledger as (Date, Amount, Bank)."""
    stmts = {
        "Statement_a.pdf": [
            row("2026-01-05 08:00", "x", "-1.00", "99.00", "KTB"),
            row("2026-01-10 10:00", "y", "-50.00", "49.00", "KTB"),
            row("2026-01-11 01:48", "z Future Amount", "-80.00", "-31.00", "KTB"),
        ],
        "STM_b.pdf": [row("2026-01-10 12:00", "k", "-50.00", "0.00", "KBANK")],
    }
    src, dst = tmp_path / "Statement", tmp_path / "ledger.csv"
    src.mkdir()
    for name in stmts:
        (src / name).write_bytes(name.encode())
    monkeypatch.setattr(us, "read_pdf", lambda path: [dict(r) for r in stmts[os.path.basename(path)]])
    monkeypatch.setattr(build_dashboard, "build", lambda csv_path=None: None)
    (tmp_path / "manual_entries.csv").write_text(
        "Date,Description,Category,Amount,Balance,Bank\n"
        "2026-01-01 09:00,Transfer out (email) e,Transfer out,-20.00,,KTB\n"  # before KTB's rows
        "2026-01-10 09:30,Transfer out (email) a,Transfer out,-50.00,,KTB\n"  # the 10:00 row
        "2026-01-10 11:00,Transfer out (email) b,Transfer out,-50.00,,KTB\n"  # 10:00 taken: kept
        "2026-01-10 23:30,Bill / purchase (email) c,Bill / purchase,-80.00,,KTB\n",  # Future Amount
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(sys, "argv", ["update_statement.py", str(src), str(dst)])
    assert us.main() == 0
    with open(dst, encoding="utf-8-sig") as f:
        return [(r["Date"], r["Amount"], r["Bank"]) for r in csv.DictReader(f)]


def test_main_merges_payment_emails(merged):
    # an email older than the bank's first row is left out; each statement row takes one email of its own bank;
    # a "Future Amount" row keeps the email's paid time
    assert merged == [
        ("2026-01-05 08:00", "-1.00", "KTB"),
        ("2026-01-10 10:00", "-50.00", "KTB"),
        ("2026-01-10 11:00", "-50.00", "KTB"),
        ("2026-01-10 12:00", "-50.00", "KBANK"),
        ("2026-01-10 23:30", "-80.00", "KTB"),
    ], merged


def test_main_drops_email_older_than_first_statement_row(merged):
    assert not any(d == "2026-01-01 09:00" for d, _, _ in merged)


def test_main_matches_each_statement_row_once(merged):
    assert [d for d, a, b in merged if a == "-50.00" and b == "KTB"] == ["2026-01-10 10:00", "2026-01-10 11:00"]


def test_main_future_amount_keeps_paid_time(merged):
    assert ("2026-01-10 23:30", "-80.00", "KTB") in merged and not any(d == "2026-01-11 01:48" for d, _, _ in merged)


def test_main_keeps_the_kbank_row(merged):
    assert ("2026-01-10 12:00", "-50.00", "KBANK") in merged


def test_main_raises_on_duplicate_ids_after_merge(monkeypatch, tmp_path):
    """The final guard is a real raise (an assert would vanish under python -O). It is unreachable through the by_id
    dedupe, so the IDs compare unequal during the merge loop and equal once the progress callback says "merge"."""

    class Twin(str):
        armed = False
        __hash__ = str.__hash__

        def __eq__(self, other):
            return Twin.armed and str.__eq__(self, other)

    monkeypatch.setattr(Twin, "armed", False)
    src = tmp_path / "Statement"
    src.mkdir()
    (src / "a.pdf").write_bytes(b"a")
    monkeypatch.setattr(us, "read_pdf", lambda path: [row("2026-01-05 08:00", "x", "-1.00", "99.00", "KTB")] * 2)
    monkeypatch.setattr(us, "stamp_ids", lambda rows: [{**r, "ID": Twin("same")} for r in rows])
    monkeypatch.setattr(sys, "argv", ["update_statement.py", str(src), str(tmp_path / "ledger.csv")])
    with pytest.raises(AssertionError, match="duplicate transaction IDs after merge"):
        us.main(progress=lambda stage, *a: setattr(Twin, "armed", stage == "merge"))

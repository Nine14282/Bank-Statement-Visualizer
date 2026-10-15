"""extract_ledger: the bank registry, picking a bank from a file name / page text, the CLI usage line, write_csv."""

import csv

import extract_ledger as ex


def test_registry_has_ktb_and_kbank():
    assert {b.id for b in ex.BANKS} == {"KTB", "KBANK"}
    assert ex.BY_ID["KTB"].name == "Krungthai" and ex.BY_ID["KBANK"].name == "KBank"


def test_bank_from_name_strips_gmail_prefix():
    assert ex.bank_from_name("/x/STM_123.pdf").id == "KBANK"
    assert ex.bank_from_name("/x/0123abcd_STM_123.pdf").id == "KBANK"
    assert ex.bank_from_name("/x/Statement_2026.pdf").id == "KTB"
    assert ex.bank_from_name("/x/other.pdf") is None


def test_bank_from_text_uses_page1_markers():
    assert ex.bank_from_text("... ธนาคารกรุงไทย ...").id == "KTB"
    assert ex.bank_from_text("K Contact Center 02-8888888").id == "KBANK"
    assert ex.bank_from_text("nothing here") is None


def test_main_usage_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["extract_ledger.py"])
    assert ex.main() == 2
    assert "Usage" in capsys.readouterr().err


def test_write_csv_is_utf8_sig_with_header(tmp_path):
    dst = tmp_path / "out.csv"
    ex.write_csv(
        [
            {
                "Date": "2026-01-01 10:00",
                "Description": "ก",
                "Category": "c",
                "Amount": "-1.00",
                "Balance": "9.00",
                "ID": "i",
                "Bank": "KTB",
            }
        ],
        str(dst),
    )
    assert dst.read_bytes().startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(dst.open(encoding="utf-8-sig")))
    assert rows[0]["Description"] == "ก" and list(rows[0]) == ex.HEADER
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]  # no leftover temp file

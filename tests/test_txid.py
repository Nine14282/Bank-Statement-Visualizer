"""Transaction IDs: the documented key examples, distinct/equal IDs, and conflict reporting."""

import pytest

import txid
from txid import base_key, differences, stamp_ids, tx_id


@pytest.mark.parametrize(
    ("amount", "key"),
    [
        (1000, "20241011 1100 100000"),
        (-1000, "20241011 1100 0100000"),
        (1, "20241011 1100 100"),
        (-1, "20241011 1100 0100"),
        (101.11, "20241011 1100 10111"),  # satang, no float drift
        (-0.05, "20241011 1100 05"),
        (0.29, "20241011 1100 29"),  # 0.29 * 100 == 28.999999999999996: int() would drop a satang
    ],
)
def test_base_key_examples(amount, key):
    assert base_key("2024-10-11 11:00", amount) == key


def test_in_and_out_of_the_same_size_never_share_an_id():
    assert tx_id(base_key("2024-10-11 11:00", 1)) != tx_id(base_key("2024-10-11 11:00", -1))


def test_repeated_real_transactions_in_one_statement_stay_distinct():
    a = stamp_ids(
        [
            {"Date": "2025-10-12 19:05", "Amount": -20.0},
            {"Date": "2025-10-12 19:05", "Amount": -20.0},
            {"Date": "2025-10-12 19:06", "Amount": -20.0},
        ]
    )
    assert len({r["ID"] for r in a}) == 3


def test_overlapping_statement_numbers_the_same_rows_the_same_way():
    a = stamp_ids(
        [
            {"Date": "2025-10-12 19:05", "Amount": -20.0},
            {"Date": "2025-10-12 19:05", "Amount": -20.0},
            {"Date": "2025-10-12 19:06", "Amount": -20.0},
        ]
    )
    b = stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0}, {"Date": "2025-10-12 19:05", "Amount": -20.0}])
    assert [r["ID"] for r in b] == [r["ID"] for r in a[:2]]


def test_other_banks_differ_but_ktb_and_manual_rows_share_keys():
    ktb = stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0}])[0]["ID"]
    assert stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0, "Bank": "KBANK"}])[0]["ID"] != ktb
    assert stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0, "Bank": "KTB"}])[0]["ID"] == ktb
    assert stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0, "Bank": "Manual"}])[0]["ID"] == ktb


def test_hash_collision_raises(monkeypatch):
    digest = tx_id("20241011 1100 100")
    monkeypatch.setitem(txid._KEYS, digest, "some other key")
    with pytest.raises(RuntimeError, match="ID collision"):
        tx_id("20241011 1100 100")


def test_differences_ignores_whitespace_and_float_formatting():
    assert differences({"Balance": 10, "Description": "x  y"}, {"Balance": "10.00", "Description": "x y"}) == []


def test_differences_reports_balance_and_description():
    assert differences({"Balance": 10, "Description": "x"}, {"Balance": 11, "Description": "z"}) == [
        "balance 10.00 vs 11.00",
        "description differs",
    ]


def test_differences_skips_a_blank_balance():
    assert differences({"Balance": "", "Description": "x"}, {"Balance": 5, "Description": "x"}) == []

"""KTB parser: the interest rule, Buddhist-era dates, the printed-totals check, the NEXT payment email."""

import pytest

from banks.ktb import build_rows, check_totals, parse_notice


def rec(t, d, wd, dep, bal, date="30/06/69"):
    return {"date": date, "time": t, "desc": d.split(), "wd": wd, "dep": dep, "bal": bal}


@pytest.fixture
def day():
    """The 30/06/69 layout seen in real statements: the interest row is printed first with the day's closing balance."""
    return [
        rec("21:00", "จ่ายค่าสินค้า/บริการ x", 90.0, None, 94.51),
        rec("01:47", "ดอกเบี้ยและภาษี (IIPS)", 0.0, 1.53, 555.04),  # printed first, closing balance
        rec("08:44", "จ่ายค่าสินค้า/บริการ y", 15.0, None, 79.51),
        rec("14:24", "เงินโอนเข้า-พร้อมเพย์ z", None, 474.0, 553.51),
    ]


def test_interest_row_moves_to_end_of_day_at_2359(day):
    rows, st = build_rows(day)
    assert [r["Date"][-5:] for r in rows] == ["21:00", "08:44", "14:24", "23:59"], rows
    assert not st["warnings"], st["warnings"]


def test_interest_row_that_already_chains_stays_put(day):
    ok = [rec("01:47", "ดอกเบี้ยและภาษี (IIPS)", 0.0, 1.53, 96.04)]  # already chains: left in place
    assert [r["Date"][-5:] for r in build_rows(day[:1] + ok)[0]] == ["21:00", "01:47"]


def test_held_interest_row_released_on_date_change_and_year_is_be_minus_543(day):
    rows, st = build_rows([*day, rec("09:00", "จ่ายค่าสินค้า/บริการ w", 5.0, None, 550.04, "01/07/69")])
    assert [r["Date"] for r in rows] == [
        "2026-06-30 21:00",
        "2026-06-30 08:44",
        "2026-06-30 14:24",
        "2026-06-30 23:59",
        "2026-07-01 09:00",
    ], rows
    assert not st["warnings"], st["warnings"]


def test_totals_match_ignores_interest_zero_withdrawal(day):
    # The interest row's 0.00 withdrawal isn't counted.
    _, st = build_rows(day)
    assert check_totals(st, {"wd": (2, 105.0), "dep": (2, 475.53)}) == [], st


def test_misread_amount_shows_as_check(day):
    _, st = build_rows(day)
    assert len(check_totals(st, {"wd": (2, 106.0), "dep": (2, 475.53)})) == 1


def test_payment_email_promptpay_adds_fee():
    got = parse_notice(
        "โอนเงินพร้อมเพย์\nวันที่ทำรายการ : 05/07/2569 13:07\nจำนวนเงิน : 1,214.00\nค่าธรรมเนียม : 5.00\n"
        "ไปยังบัญชีพร้อมเพย์ : PERSON\n"
    )
    assert got == {
        "Date": "2026-07-05 13:07",
        "Description": "PromptPay out (email) PERSON",
        "Category": "PromptPay out",
        "Amount": "-1219.00",
        "Balance": "",
        "Bank": "KTB",
    }, got

"""KBank parser: direction from the running balance, CHECK reporting, K PLUS payment emails."""

import pytest

from banks.kbank import amounts, parse_notice


def kb(d, money):
    return {"date": d, "time": "10:00", "desc": ["x"], "chan": [], "detail": [], "money": money}


@pytest.fixture
def parsed():
    return amounts(
        [
            kb("01-05-26", [(329, 100.0)]),  # opening balance
            kb("02-05-26", [(267, 30.0), (329, 70.0)]),  # "in" position, balance fell
            kb("03-05-26", [(252, 20.0), (329, 40.0)]),
        ]
    )  # balance moved 30, amount 20


def test_direction_follows_balance_even_in_money_in_position(parsed):
    out, _ = parsed
    assert [r["Amount"] for r in out] == ["-30.00", "-20.00"], out


def test_date_is_dd_mm_yy_christian_era(parsed):
    out, _ = parsed
    assert out[0]["Date"] == "2026-05-02 10:00", out


def test_row_that_does_not_reconcile_is_kept_and_reported(parsed):
    out, problems = parsed
    assert len(out) == 2  # kept (sign from position), never dropped
    assert len(problems) == 1 and "03-05-26" in problems[0], problems


# K PLUS emails, layout as received (redacted): Thai half first, the English half is what we read.
KPLUS = (
    "เรื่อง แจ้งผลการทำรายการ{th} (สำเร็จ)\n\tวันที่ทำรายการ: 06/07/2026  13:07:08\n\tจำนวนเงิน (บาท): 10.00\n"
    "Dear Customer\nSubject: Result of {en}\nWith reference to your request via K PLUS Service as follows:\n"
    "\tTransaction Date: 06/07/2026  13:07:08\n\tFrom Account: xxx-x-x1234-x\n{to}"
    "\tAmount (THB): 1,214.00\n\tFee (THB): 5.00\n\tAvailable Balance (THB): 0.67\n"
)


def test_notice_bill_payment():
    bill = parse_notice(KPLUS.format(th="ชำระค่าสินค้า", en="Payment (Success)", to="\tCompany Name: SHOP A\n"))
    assert bill == {
        "Date": "2026-07-06 13:07",
        "Description": "K PLUS Bill / purchase (email) SHOP A",
        "Category": "Bill / purchase",
        "Amount": "-1219.00",
        "Balance": "",
        "Bank": "KBANK",
    }, bill


def test_notice_promptpay():
    pp = parse_notice(
        KPLUS.format(
            th="โอนเงินพร้อมเพย์",
            en="PromptPay Funds Transfer (Success)",
            to="\tTo PromptPay ID: xxx-xxx-1234\n\tReceived Name: PERSON B\n",
        )
    )
    assert pp["Description"] == "K PLUS PromptPay out (email) PERSON B", pp


def test_notice_transfer():
    tr = parse_notice(
        KPLUS.format(
            th="โอนเงิน",
            en="Funds Transfer (Success)",
            to="\tTo Bank: KRUNG THAI BANK\n\tTo Account: 123-4-56789-0\n\tAccount Name: PERSON C\n",
        )
    )
    assert tr["Description"] == "K PLUS Transfer out (email) PERSON C" and tr["Category"] == "Transfer out", tr


def test_notice_unsuccessful_is_ignored():
    assert parse_notice(KPLUS.format(th="โอนเงิน", en="Funds Transfer (Unsuccessful)", to="")) is None

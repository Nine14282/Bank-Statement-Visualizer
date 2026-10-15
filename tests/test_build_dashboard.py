"""build_dashboard: data injection (hostile text stays inside the data tag) and find_gaps."""

import json

import pytest

import build_dashboard as bd


def test_inject_keeps_hostile_text_inside_the_data_tag():
    evil = {"tx": [{"desc": "</script><script>alert(1)</script> <!-- ฿"}]}
    page = bd.inject(f"<html><body>{bd.MARK}<script type=module>app()</script></body></html>", evil)
    body = page.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert "<" not in body, body
    assert json.loads(body) == evil
    assert page.count("<script") == 2, page


def test_inject_exits_when_the_placeholder_is_missing():
    with pytest.raises(SystemExit):
        bd.inject("<html></html>", {"tx": []})


def test_data_js_has_no_literal_tag_and_parses_back():
    evil = {"tx": [{"desc": "</script><script>alert(1)</script> <!-- ฿"}]}
    js = bd.data_js(evil, 7)
    body, _, tail = js.removeprefix("window.__LEDGER=").rpartition(";window.__LEDGER_BUILD=")
    assert "<" not in js and json.loads(body) == evil and tail == "7;", js


def t(date, amt, bal, bank="KTB"):
    return {"date": date, "amt": amt, "bal": bal, "bank": bank}


def test_find_gaps_empty_month_and_balance_jump_per_bank():
    # an empty month; a balance jump per bank (same-minute rows chained by balance, a row without a balance
    # skipped, another bank's rows apart)
    tx = [
        t("2026-01-01 10:00", 100, 100),
        t("2026-01-01 10:05", -10, 80),
        t("2026-01-01 10:05", -10, 90),
        t("2026-01-02 09:00", 5, 5, "KBANK"),
        t("2026-01-03 09:00", -7, None),
        t("2026-03-01 10:00", -10, 30),
    ]
    assert bd.find_gaps(tx) == {
        "months": ["2026-02"],
        "breaks": [{"after": "2026-01-01 10:05", "before": "2026-03-01 10:00", "bank": "KTB", "missing": -40}],
    }


def test_find_gaps_drops_offsetting_jumps_posted_out_of_order():
    swapped = [
        t("2026-01-01 10:00", 100, 100),
        t("2026-01-01 23:59", -20, 70),
        t("2026-01-02 00:01", -10, 90),
        t("2026-01-02 08:00", -5, 65),
    ]
    assert bd.find_gaps(swapped)["breaks"] == []

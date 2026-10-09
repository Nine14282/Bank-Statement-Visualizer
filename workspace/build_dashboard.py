#!/usr/bin/env python3
"""Build the dashboard: ledger.csv -> web/dist/index.html, with Python only (no Node needed).

The dashboard is the React app in web/, built once by its developers into one self-contained page with no data,
web/prebuilt/index.html (committed). This script checks ledger.csv, prints the summary and any coverage warnings,
and writes that page with the ledger filled into its <script id="ledger-data"> tag. It also writes
web/src/data/ledger.json, which only the `npm run dev` server reads.

Usage: python build_dashboard.py      (python build_dashboard.py --selfcheck: the data-injection check)
"""
import csv
import datetime
import json
import os
import sys
import time

import config  # loads the project's env settings into os.environ

# Anchor paths to this script's folder so it runs from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root

CSV = os.path.join(HERE, "ledger.csv")
WEB = os.path.join(ROOT, "web")
SHELL = os.path.join(WEB, "prebuilt", "index.html")   # the app without data: `npm run build` in web/ makes it
JSON_OUT = os.path.join(WEB, "src", "data", "ledger.json")   # for the dev server only
OUT = os.path.join(WEB, "dist", "index.html")      # the dashboard
# The placeholder in web/index.html (and so in the prebuilt page) that the data replaces; same text in vite.config.ts.
MARK = '<script id="ledger-data" type="application/json">null</script>'

# Optional labels shown in the dashboard top bar: the avatar tooltip and the greeting (env settings, see .env.example).
ACCOUNT = os.environ.get("ACCOUNT_LABEL", "")
NAME = os.environ.get("ACCOUNT_HOLDER", "")
# Picked in the setup wizard: the dashboard's default theme (an id from web/src/lib/themes.ts), and the
# expected-spending list that seeds the Expected Spending tab (the dashboard keeps later edits itself).
EXPECTED = os.path.join(HERE, "expected.json")


def expected():
    try:
        return json.load(open(EXPECTED, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def find_gaps(tx):
    """Spot missing statement data: empty months, and balance jumps.

    A balance jump = a row whose balance isn't previous balance + its amount,
    so something between the two rows isn't in the ledger (a missing statement,
    even one that covers only part of a month). Rows in the same minute can be
    in any order, so each minute is chained by balance rather than by position.
    """
    seen = {t["date"][:7] for t in tx}
    months, y, m = [], int(tx[0]["date"][:4]), int(tx[0]["date"][5:7])
    while f"{y}-{m:02d}" <= tx[-1]["date"][:7]:
        k = f"{y}-{m:02d}"
        if k not in seen:
            months.append(k)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    breaks = []
    for bank in sorted({t["bank"] for t in tx}):   # each account has its own balance chain
        cur, cur_date = None, None
        bal_rows = [t for t in tx if t["bal"] is not None and t["bank"] == bank]   # manual rows carry no balance
        for minute in sorted({t["date"] for t in bal_rows}):
            rem = [t for t in bal_rows if t["date"] == minute]
            while rem:
                nxt = next((t for t in rem
                            if cur is None or abs(cur + t["amt"] - t["bal"]) < 0.011), None)
                if nxt is None:                      # nothing chains: record the jump, resync
                    nxt = rem[0]
                    breaks.append({"after": cur_date, "before": minute, "bank": bank,
                                   "missing": round(nxt["bal"] - nxt["amt"] - cur, 2)})
                rem.remove(nxt)
                cur, cur_date = nxt["bal"], minute
    breaks.sort(key=lambda b: b["before"])
    # Rows posted out of order around midnight/month-end show up as a jump and an
    # equal and opposite jump a few rows later. A run of nearby jumps that nets to
    # zero moved no money, so drop it; what survives is genuinely missing.
    day = lambda d: datetime.date.fromisoformat(d[:10])
    real, run = [], []
    for b in breaks:
        if run and (day(b["after"]) - day(run[-1]["before"])).days > 2:
            real += run; run = []
        run.append(b)
        if abs(sum(r["missing"] for r in run)) < 0.011:
            run = []
    return {"months": months, "breaks": real + run}


def build(csv_path: str = CSV) -> None:
    # No ledger yet (fresh clone, nothing imported): build the blank "No data yet" dashboard.
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig"))) if os.path.exists(csv_path) else []

    ids = [r["ID"] for r in rows if r.get("ID")]
    if len(ids) != len(set(ids)):
        print(f"  WARNING: {len(ids) - len(set(ids))} duplicate transaction ID(s) in ledger.csv; re-run ./run.sh")

    tx = [{"date": r["Date"], "desc": r["Description"], "cat": r["Category"],
           "amt": round(float(r["Amount"]), 2), "bal": round(float(r["Balance"]), 2) if r["Balance"] else None,
           "bank": r.get("Bank") or "KTB"}   # ledgers written before the Bank column were KTB-only
          for r in rows]
    gaps = find_gaps(tx) if tx else {"months": [], "breaks": []}

    payload = {"meta": {"account": ACCOUNT, "name": NAME, "from": tx[0]["date"] if tx else "",
                        "to": tx[-1]["date"] if tx else "", "n": len(tx), "gaps": gaps,
                        "theme": os.environ.get("THEME", ""), "plan": expected()},
               "tx": tx}
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    if not tx:
        print("ledger.csv has no transactions yet: building the blank dashboard.")
    else:
        inc = sum(t["amt"] for t in tx if t["amt"] > 0)
        exp = -sum(t["amt"] for t in tx if t["amt"] < 0)
        years = sorted({t["date"][:4] for t in tx})
        print(f"ledger.csv: {len(tx)} transactions")
        print(f"  Income {inc:,.2f}  ·  Expense {exp:,.2f}  ·  Net {inc - exp:,.2f}")
        print(f"  Years: {', '.join(years)}")
        for m in gaps["months"]:
            print(f"  WARNING missing month: {m}")
        for b in gaps["breaks"]:
            print(f"  WARNING {b['bank']} balance jump {b['after']} -> {b['before']}: "
                  f"{b['missing']:+,.2f} not in ledger")
        if not gaps["months"] and not gaps["breaks"]:
            print("  Coverage OK: no empty months, balance continuous")

    try:
        shell = open(SHELL, encoding="utf-8").read()
    except OSError:
        sys.exit(f"Missing {SHELL}: it ships with the project. Restore it (git checkout web/prebuilt) or, if you "
                 "changed the web app, run `npm install && npm run build` in web/ (needs Node.js 20+).")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(inject(shell, payload))
    os.replace(tmp, OUT)    # an open dashboard tab never reloads into a half-written file
    # An open dashboard polls this file (a <script>, which works from file:// where fetch doesn't) and reloads
    # when the number changes.
    with open(os.path.join(os.path.dirname(OUT), "version.js"), "w", encoding="utf-8") as f:
        f.write(f"window.__BUILD={int(time.time() * 1000)}")
    print(f"Wrote {OUT}  ({os.path.getsize(OUT):,} bytes)")


def inject(shell: str, payload) -> str:
    """The prebuilt page with the ledger in its data tag. Every '<' in the JSON becomes \\u003c (still valid JSON),
    so no description (bank PDFs, payment emails) can close the script tag or start markup."""
    if shell.count(MARK) != 1:
        sys.exit(f"{SHELL} doesn't hold the ledger-data placeholder exactly once; rebuild it with `npm run build` in web/.")
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return shell.replace(MARK, f'<script id="ledger-data" type="application/json">{data}</script>')


def selfcheck():
    """python build_dashboard.py --selfcheck: hostile text stays inside the data tag and parses back unchanged."""
    evil = {"tx": [{"desc": "</script><script>alert(1)</script> <!-- ฿"}]}
    page = inject(f"<html><body>{MARK}<script type=module>app()</script></body></html>", evil)
    body = page.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert "<" not in body, body
    assert json.loads(body) == evil
    assert page.count("<script") == 2, page
    print("selfcheck ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    else:
        build()

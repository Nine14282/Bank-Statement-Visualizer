#!/usr/bin/env python3
"""Build the dashboard: ledger.csv -> web/src/data/ledger.json -> web/dist/index.html.

The dashboard is the React app in web/ (Vite single-file build, opens offline from
disk). This script checks ledger.csv, prints the summary and any coverage warnings,
writes the JSON the app imports, then runs `npm run build` in web/.

Usage: python build_dashboard.py
"""
import csv
import datetime
import json
import os
import shutil
import subprocess
import sys

import config  # loads the project's env settings into os.environ

# Anchor paths to this script's folder so it runs from any working directory.
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root

CSV = os.path.join(HERE, "ledger.csv")
WEB = os.path.join(ROOT, "web")
JSON_OUT = os.path.join(WEB, "src", "data", "ledger.json")
OUT = os.path.join(WEB, "dist", "index.html")      # the dashboard

# Secrets loaded from the settings file are NOT passed to npm: its install scripts and build plugins
# (hundreds of third-party packages) would otherwise inherit them through the environment.
SECRET_ENV = ("STATEMENT_PW", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_PROJECT_ID")

# Optional labels shown in the dashboard sidebar (set in the env settings, see .env.example).
ACCOUNT = os.environ.get("ACCOUNT_LABEL", "")
NAME = os.environ.get("ACCOUNT_HOLDER", "")


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

    breaks, cur, cur_date = [], None, None
    bal_rows = [t for t in tx if t["bal"] is not None]   # manual rows carry no balance
    for minute in sorted({t["date"] for t in bal_rows}):
        rem = [t for t in bal_rows if t["date"] == minute]
        while rem:
            nxt = next((t for t in rem
                        if cur is None or abs(cur + t["amt"] - t["bal"]) < 0.011), None)
            if nxt is None:                      # nothing chains: record the jump, resync
                nxt = rem[0]
                breaks.append({"after": cur_date, "before": minute,
                               "missing": round(nxt["bal"] - nxt["amt"] - cur, 2)})
            rem.remove(nxt)
            cur, cur_date = nxt["bal"], minute
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
           "amt": round(float(r["Amount"]), 2), "bal": round(float(r["Balance"]), 2) if r["Balance"] else None}
          for r in rows]
    gaps = find_gaps(tx) if tx else {"months": [], "breaks": []}

    payload = {"meta": {"account": ACCOUNT, "name": NAME, "from": tx[0]["date"] if tx else "",
                        "to": tx[-1]["date"] if tx else "", "n": len(tx), "gaps": gaps},
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
        print(f"ledger.csv: {len(tx)} transactions -> {JSON_OUT}")
        print(f"  Income {inc:,.2f}  ·  Expense {exp:,.2f}  ·  Net {inc - exp:,.2f}")
        print(f"  Years: {', '.join(years)}")
        for m in gaps["months"]:
            print(f"  WARNING missing month: {m}")
        for b in gaps["breaks"]:
            print(f"  WARNING balance jump {b['after']} -> {b['before']}: "
                  f"{b['missing']:+,.2f} not in ledger")
        if not gaps["months"] and not gaps["breaks"]:
            print("  Coverage OK: no empty months, balance continuous")

    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    npm = shutil.which("npm")
    if not npm:
        sys.exit("npm not found: install Node.js, then run `npm install` in web/ and re-run.")
    if not os.path.isdir(os.path.join(WEB, "node_modules")):
        subprocess.run([npm, "install"], cwd=WEB, check=True, env=env)
    subprocess.run([npm, "run", "build"], cwd=WEB, check=True, stdout=subprocess.DEVNULL, env=env)
    print(f"Wrote {OUT}  ({os.path.getsize(OUT):,} bytes)")


if __name__ == "__main__":
    build()

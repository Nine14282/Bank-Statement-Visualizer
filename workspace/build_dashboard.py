#!/usr/bin/env python3
"""Build the dashboard: ledger.csv -> web/dist/index.html, with Python only (no Node needed).

The dashboard is the React app in web/, built once by its developers into one self-contained page with no data,
web/prebuilt/index.html (committed). This script checks ledger.csv, prints the summary and any coverage warnings,
and writes that page with the ledger filled into its <script id="ledger-data"> tag. It also writes
web/src/data/ledger.json, which only the `npm run dev` server reads.

Usage: python build_dashboard.py
"""

import csv
import datetime
import hashlib
import itertools
import json
import os
import re
import sys
import time

import config  # loads the project's env settings into os.environ

# Absolute paths (config.py), so it runs from any working directory.
HERE = config.WORK  # workspace/
ROOT = config.ROOT  # project root

CSV = os.path.join(HERE, "ledger.csv")
WEB = os.path.join(ROOT, "web")
SHELL = os.path.join(config.APP, "web", "prebuilt", "index.html")  # the app without data: `npm run build` in web/
# For the dev server only; the PyInstaller build has none, so it doesn't write this extra copy of your ledger there.
JSON_OUT = None if config.FROZEN else os.path.join(WEB, "src", "data", "ledger.json")
OUT = os.path.join(WEB, "dist", "index.html")  # the dashboard
LINK = os.path.join(ROOT, "Dashboard.html")  # one double-click from the project folder; forwards to OUT
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
    for bank in sorted({t["bank"] for t in tx}):  # each account has its own balance chain
        cur, cur_date = None, None
        bal_rows = [t for t in tx if t["bal"] is not None and t["bank"] == bank]  # manual rows carry no balance
        for minute, grp in itertools.groupby(sorted(bal_rows, key=lambda t: t["date"]), key=lambda t: t["date"]):
            rem = list(grp)
            while rem:
                nxt = next((t for t in rem if cur is None or abs(cur + t["amt"] - t["bal"]) < 0.011), None)
                if nxt is None:  # nothing chains: record the jump, resync
                    nxt = rem[0]
                    breaks.append(
                        {
                            "after": cur_date,
                            "before": minute,
                            "bank": bank,
                            "missing": round(nxt["bal"] - nxt["amt"] - cur, 2),
                        }
                    )
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
            real += run
            run = []
        run.append(b)
        if abs(sum(r["missing"] for r in run)) < 0.011:
            run = []
    return {"months": months, "breaks": real + run}


def build(csv_path: str = CSV) -> None:
    # No ledger yet (fresh clone, nothing imported): build the blank "No data yet" dashboard.
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig"))) if os.path.exists(csv_path) else []

    ids = [r["ID"] for r in rows if r.get("ID")]
    if len(ids) != len(set(ids)):
        print(
            f"  WARNING: {len(ids) - len(set(ids))} duplicate transaction ID(s) in ledger.csv; re-run {config.command('run')}"
        )

    tx = [
        {
            "date": r["Date"],
            "desc": r["Description"],
            "cat": r["Category"],
            "amt": round(float(r["Amount"]), 2),
            "bal": round(float(r["Balance"]), 2) if r["Balance"] else None,
            "bank": r.get("Bank") or "KTB",
        }  # ledgers written before the Bank column were KTB-only
        for r in rows
    ]
    gaps = find_gaps(tx) if tx else {"months": [], "breaks": []}

    payload = {
        "meta": {
            "account": ACCOUNT,
            "name": NAME,
            "from": tx[0]["date"] if tx else "",
            "to": tx[-1]["date"] if tx else "",
            "n": len(tx),
            "gaps": gaps,
            "theme": os.environ.get("THEME", ""),
            "plan": expected(),
        },
        "tx": tx,
    }
    if JSON_OUT:
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
            print(
                f"  WARNING {b['bank']} balance jump {b['after']} -> {b['before']}: {b['missing']:+,.2f} not in ledger"
            )
        if not gaps["months"] and not gaps["breaks"]:
            print("  Coverage OK: no empty months, balance continuous")

    try:
        shell = open(SHELL, encoding="utf-8").read()
    except OSError:
        if config.FROZEN:
            sys.exit(f"Missing {SHELL}: this copy of the program is incomplete. Download or build it again.")
        sys.exit(
            f"Missing {SHELL}: it ships with the project. Restore it (git checkout web/prebuilt) or, if you "
            "changed the web app, run `npm install && npm run build` in web/ (needs Node.js 20+)."
        )
    # Which build of the app's own code this is: an open page swaps in new data, but reloads when this differs from
    # the one it was loaded with (an update of the app itself). stamp: this build, also in version.js and data.js.
    page = hashlib.sha256(shell.encode()).hexdigest()[:12]
    stamp = int(time.time() * 1000)
    payload["meta"]["page"], payload["meta"]["build"] = page, stamp
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(inject(shell, payload))
    os.replace(tmp, OUT)  # an open dashboard tab never reloads into a half-written file
    # An open app window is told to update (app.py, from the Gmail listener's output) and then reads version.js and
    # data.js (by <script>, which works from file:// where fetch doesn't), swapping the new data in without a reload.
    # data.js goes first, whole, so a changed version.js always finds it complete. Both carry the same stamp: a
    # data.js left behind by an older builder doesn't match, and the page reloads instead.
    tmp = os.path.join(os.path.dirname(OUT), "data.js.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data_js(payload, stamp))
    os.replace(tmp, os.path.join(os.path.dirname(OUT), "data.js"))
    with open(os.path.join(os.path.dirname(OUT), "version.js"), "w", encoding="utf-8") as f:
        f.write(f'window.__BUILD={stamp};window.__PAGE="{page}"')
    # A forwarder, not a copy: the page stays at OUT, so its live updates and saved browser
    # settings (localStorage) keep working. No data in it.
    with open(LINK, "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html><meta charset="utf-8"><title>Statement Visualizer</title>'
            '<script>location.replace("web/dist/index.html")</script>\n'
        )
    print(f"Wrote {OUT}  ({os.path.getsize(OUT):,} bytes); open it with {LINK}")


def data_js(payload, stamp=0) -> str:
    """dist/data.js: the ledger as a script (JSON is valid JavaScript). Loaded by <script src>, so no HTML parsing:
    the '<' escaping inject() needs isn't required, but it's kept so the file never holds a literal tag either."""
    return (
        "window.__LEDGER="
        + json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
        + f";window.__LEDGER_BUILD={int(stamp)};"
    )


def inject(shell: str, payload) -> str:
    """The prebuilt page with the ledger in its data tag. Every '<' in the JSON becomes \\u003c (still valid JSON),
    so no description (bank PDFs, payment emails) can close the script tag or start markup."""
    if shell.count(MARK) != 1:
        sys.exit(
            f"{SHELL} doesn't hold the ledger-data placeholder exactly once; rebuild it with `npm run build` in web/."
        )
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    theme = payload.get("meta", {}).get("theme") or ""
    if re.fullmatch(r"[a-z0-9-]{1,30}", theme):  # the first frame's background (index.html) follows the theme
        shell = shell.replace('<html lang="en">', f'<html lang="en" data-theme="{theme}">', 1)
    return shell.replace(MARK, f'<script id="ledger-data" type="application/json">{data}</script>')


if __name__ == "__main__":
    build()

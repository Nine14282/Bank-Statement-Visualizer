#!/usr/bin/env python3
"""Watch Statement/ and auto-update the ledger whenever a PDF is added.

Leave this running (e.g. at login). Drop a new statement PDF into Statement/
and, a few seconds later, ledger.csv and web/dist/index.html rebuild on their
own — no command to type. Everything stays local.

The bank password is needed to unlock encrypted PDFs. Set it once so the watcher
can run unattended:
    STATEMENT_PW=xxxx python watch_statements.py
Otherwise it prompts once at startup.

Usage:
    python watch_statements.py [STATEMENT_DIR]   (default: Statement)
Stop with Ctrl-C.
"""
import getpass
import os
import sys
import time

import update_statement

# Anchor default watch folder to the project root (outside workspace/).
HERE = os.path.dirname(os.path.abspath(__file__))   # workspace/
ROOT = os.path.dirname(HERE)                         # project root

POLL_SECONDS = 5


def snapshot(folder):
    """Map of pdf path -> (size, mtime) for change detection."""
    snap = {}
    for e in os.scandir(folder):
        if e.is_file() and e.name.lower().endswith(".pdf"):
            st = e.stat()
            snap[e.path] = (st.st_size, int(st.st_mtime))
    return snap


def run_update():
    try:
        update_statement.main()
    except SystemExit:
        pass
    except Exception as e:  # keep the watcher alive on a bad file
        print(f"  update failed: {type(e).__name__}: {e}")


def main():
    # Stay line-buffered even when output is piped to a log file.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Statement")
    if not os.path.isdir(folder):
        print(f"No such folder: {folder}", file=sys.stderr)
        return 1

    # Resolve the password up front so unattended runs never block on a prompt.
    if "STATEMENT_PW" not in os.environ:
        os.environ["STATEMENT_PW"] = getpass.getpass(
            "Statement password (leave blank if PDFs are already unlocked): ")

    print(f"Watching {folder}/ for new statements — Ctrl-C to stop.")
    prev = snapshot(folder)
    if prev:
        print(f"  ({len(prev)} PDF(s) already present; building once now)")
        run_update()

    while True:
        time.sleep(POLL_SECONDS)
        try:
            cur = snapshot(folder)
        except FileNotFoundError:
            continue
        added = {p for p in cur if prev.get(p) != cur[p]}
        if added:
            for p in sorted(added):
                print(f"\nDetected: {os.path.basename(p)}")
            run_update()
        prev = cur


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Remove the password from a bank-statement PDF.

Usage:
    python unlock_pdf.py [INPUT_PDF] [OUTPUT_PDF]

Defaults: statement_1.pdf -> statement_clean.pdf
Prompts for the password (input stays hidden).
"""
import getpass
import sys

import pikepdf


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "statement_1.pdf"
    dst = sys.argv[2] if len(sys.argv) > 2 else "statement_clean.pdf"

    password = getpass.getpass(f"Password for {src}: ")
    try:
        with pikepdf.open(src, password=password) as pdf:
            pdf.save(dst)
    except pikepdf.PasswordError:
        print("Wrong password — nothing written.", file=sys.stderr)
        return 1

    print(f"DONE - unlocked: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

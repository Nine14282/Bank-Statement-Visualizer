"""Shared settings: reads <project root>/.env into os.environ when this module is imported.

Real environment variables win over the file, and empty values are ignored, so a blank
line like `STATEMENT_PW=` in .env.example means "not set". Format: KEY=value, one per line,
`#` comment lines, optional `export ` prefix, optional quotes. No inline comments.

Every script imports this first; see .env.example for the settings.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENVFILE = os.path.join(ROOT, ".env")


def load_env() -> None:
    if not os.path.exists(ENVFILE):
        return
    for line in open(ENVFILE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.removeprefix("export ").partition("=")
        value = value.strip().strip("\"'")
        if sep and value:
            os.environ.setdefault(key.strip(), value)


load_env()

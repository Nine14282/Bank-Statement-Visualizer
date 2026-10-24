"""Shared settings: reads <project root>/.env into os.environ when this module is imported.

Real environment variables win over the file, and empty values are ignored, so a blank
line like `STATEMENT_PW=` in .env.example means "not set". Format: KEY=value, one per line,
`#` comment lines, optional `export ` prefix, optional quotes. No inline comments.

Every script imports this first; see .env.example for the settings.

Where things live. From source: everything in the project folder. In the PyInstaller build (statement-visualizer.spec):
your data next to the .exe (ROOT, the same layout: Statement/, workspace/, web/dist/, .env), and the program's own
files inside the bundle (APP: web/prebuilt/index.html, .env.example), read-only.
"""

import os
import sys

os.umask(0o077)  # ledger, dashboard and cache are private even when a script is run by hand

FROZEN = bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))
HERE = os.path.dirname(os.path.abspath(__file__))  # the scripts (from source)
# your data; SV_ROOT redirects it (the tests point it at a temp folder so they never touch the real data)
ROOT = os.environ.get("SV_ROOT") or (os.path.dirname(sys.executable) if FROZEN else os.path.dirname(HERE))
WORK = os.path.join(ROOT, "workspace")  # ledger, caches, Gmail login
APP = sys._MEIPASS if FROZEN else os.path.dirname(HERE)  # shipped files
ENVFILE = os.path.join(ROOT, ".env")
# The scripts the build can run as its own subprocesses (launcher.py's --script); nothing else is accepted.
SCRIPTS = ("app", "build_dashboard", "extract_ledger", "fetch_gmail", "update_statement", "welcome")

if FROZEN and sys.platform.startswith("linux"):
    # The bootloader points LD_LIBRARY_PATH at the bundle; a system program started from here (xdg-open, the browser)
    # must get the system's libraries back. This process already loaded its own, and a copy of the build started from
    # here sets it again itself. Windows and macOS don't use it (PyInstaller docs, "Launching External Programs").
    if "LD_LIBRARY_PATH_ORIG" in os.environ:
        os.environ["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH_ORIG"]
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)


def script(name: str, *args: str) -> list[str]:
    """The command line that runs one of SCRIPTS in its own process: python name.py from source; in the build, the
    .exe again, which runs it (launcher.py)."""
    if name not in SCRIPTS:
        raise ValueError(f"not a script: {name}")
    if FROZEN:
        return [sys.executable, "--script", name, *args]
    return [sys.executable, os.path.join(HERE, name + ".py"), *args]


def load_env() -> None:
    if not os.path.exists(ENVFILE):
        return
    for line in open(ENVFILE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":  # one matching pair, so a quoted
            value = value[1:-1]  # value keeps its inner quotes
        if sep and value:
            os.environ.setdefault(key.strip(), value)


load_env()


def lock(f, wait: bool = True) -> bool:
    """Lock an open file for this process; it's released when the file closes, also if the process dies. True once
    held; with wait=False, False at once when another process holds it. fcntl on Linux and macOS, msvcrt on Windows
    (which locks a byte range, not the file: byte 0, the same one for every process)."""
    if os.name == "nt":
        import msvcrt
        import time

        f.seek(0)
        while True:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                if not wait:
                    return False
                time.sleep(0.5)
    import fcntl

    try:
        fcntl.flock(f, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        return True
    except BlockingIOError:
        return False


def save(key: str, value: str) -> None:
    """Set KEY=value in the settings file (replace the KEY= line, else append) and in os.environ.
    Used by the setup wizard; the file stays readable by you only."""
    if not key.replace("_", "").isalnum() or "\n" in value or "\r" in value:
        raise ValueError("bad setting")
    lines = open(ENVFILE, encoding="utf-8").read().splitlines() if os.path.exists(ENVFILE) else []
    out, done = [], False
    for line in lines:
        if line.strip().removeprefix("export ").partition("=")[0].strip() == key:
            if not done:
                out.append(f"{key}={value}")
                done = True
            continue
        out.append(line)
    if not done:
        out.append(f"{key}={value}")
    fd = os.open(ENVFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(ENVFILE, 0o600)
    os.environ[key] = value

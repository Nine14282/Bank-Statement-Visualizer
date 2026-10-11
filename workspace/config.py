"""Shared settings: reads <project root>/.env into os.environ when this module is imported.

Real environment variables win over the file, and empty values are ignored, so a blank
line like `STATEMENT_PW=` in .env.example means "not set". Format: KEY=value, one per line,
`#` comment lines, optional `export ` prefix, optional quotes. No inline comments.

Every script imports this first; see .env.example for the settings.
"""
import os

os.umask(0o077)   # ledger, dashboard and cache are private even when a script is run by hand

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
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":   # one matching pair, so a quoted
            value = value[1:-1]                                              # value keeps its inner quotes
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

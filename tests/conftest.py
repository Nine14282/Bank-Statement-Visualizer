"""Test isolation: every data path points into a temp folder, never at the real ledger, settings or Statement/.

The SV_ROOT setup runs at import, before any test module imports a workspace script (config reads it once).
"""

import atexit
import os
import shutil
import tempfile

import pytest

_ROOT = tempfile.mkdtemp(prefix="sv-test-")
for _d in ("workspace", "Statement"):
    os.mkdir(os.path.join(_ROOT, _d))
os.environ["SV_ROOT"] = _ROOT
for _k in (
    "LEDGER_CASH_REF",
    "LEDGER_PEER_REF",
    "LEDGER_STOCK_REF",
    "KTB_PW",
    "STATEMENT_PW",
    "KBANK_PW",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_PROJECT_ID",
    "GMAIL_TOPIC",
    "GMAIL_SUBSCRIPTION",
    "ACCOUNT_LABEL",
    "ACCOUNT_HOLDER",
    "THEME",
):
    os.environ.pop(_k, None)
atexit.register(shutil.rmtree, _ROOT, ignore_errors=True)  # also runs when pytest is interrupted


@pytest.fixture(scope="session")
def sv_root() -> str:
    return _ROOT

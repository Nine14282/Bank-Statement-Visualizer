"""Transaction IDs: the duplicate / conflict check used when merging overlapping statements.

ID = first 16 hex chars of sha256 over "<yyyymmdd> <hhmm> <money>#<n>"

  yyyymmdd hhmm  date and time to the minute, exactly as the statement prints them
  money          the amount in satang (integer, so no float rounding), with the direction
                 in the leading digit: money IN has none, money OUT gets a leading 0
                     in  1000.00 baht -> "100000"      out 1000.00 baht -> "0100000"
                     in     1.00 baht -> "100"         out    1.00 baht -> "0100"
  n              1-based occurrence of the same (minute, signed amount) inside ONE statement.
                 Two real payments of 20 baht in the same minute are two transactions, so they
                 get n=1 and n=2. The same statement rows always number the same way, so the
                 copy of a transaction in an overlapping statement gets the same ID.

Rows of another bank (Bank column other than KTB/Manual, e.g. KBANK) get the bank name in front of
the key, so a KTB and a KBank payment in the same minute with the same amount never share an ID.
KTB and manual rows keep the plain key: payment emails must match their KTB statement rows.

Rows with equal IDs are the same transaction. `differences()` reports when two copies disagree
(balance or description), and a hash collision between two different keys raises an error.

Run `python txid.py` for the self-check.
"""
import hashlib

_KEYS: dict[str, str] = {}   # id -> key text, to detect hash collisions


def base_key(date: str, amount) -> str:
    """'2024-10-11 11:00', 1000 -> '20241011 1100 100000' (out: '20241011 1100 0100000')."""
    amount = float(amount)
    ymd, hm = date[:10].replace("-", ""), date[11:16].replace(":", "")
    return f"{ymd} {hm} {'0' if amount < 0 else ''}{round(abs(amount) * 100)}"


def tx_id(base: str, nth: int = 1) -> str:
    text = f"{base}#{nth}"
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    if _KEYS.setdefault(digest, text) != text:
        raise RuntimeError(f"ID collision: {text!r} and {_KEYS[digest]!r} hash to {digest}")
    return digest


def stamp_ids(rows):
    """Set row['ID'] on every row of ONE source (one statement PDF, or the manual file)."""
    seen: dict[str, int] = {}
    for r in rows:
        base = base_key(r["Date"], r["Amount"])
        if r.get("Bank") not in (None, "", "KTB", "Manual"):
            base = f"{r['Bank']} {base}"
        seen[base] = seen.get(base, 0) + 1
        r["ID"] = tx_id(base, seen[base])
    return rows


def _num(v):
    return None if v in (None, "") else float(v)


def differences(old: dict, new: dict) -> list[str]:
    """How two rows with the same ID disagree (empty list = true duplicates)."""
    out = []
    ob, nb = _num(old.get("Balance")), _num(new.get("Balance"))
    if ob is not None and nb is not None and abs(ob - nb) > 0.011:
        out.append(f"balance {ob:,.2f} vs {nb:,.2f}")
    if " ".join(str(old["Description"]).split()) != " ".join(str(new["Description"]).split()):
        out.append("description differs")
    return out


if __name__ == "__main__":
    # the documented examples
    assert base_key("2024-10-11 11:00", 1000) == "20241011 1100 100000"
    assert base_key("2024-10-11 11:00", -1000) == "20241011 1100 0100000"
    assert base_key("2024-10-11 11:00", 1) == "20241011 1100 100"
    assert base_key("2024-10-11 11:00", -1) == "20241011 1100 0100"
    assert base_key("2024-10-11 11:00", 101.11) == "20241011 1100 10111"      # satang, no float drift
    assert base_key("2024-10-11 11:00", -0.05) == "20241011 1100 05"
    # in and out of the same size never share an ID
    assert tx_id(base_key("2024-10-11 11:00", 1)) != tx_id(base_key("2024-10-11 11:00", -1))
    # repeated real transactions in one statement stay distinct
    a = stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0}, {"Date": "2025-10-12 19:05", "Amount": -20.0},
                   {"Date": "2025-10-12 19:06", "Amount": -20.0}])
    assert len({r["ID"] for r in a}) == 3
    # an overlapping statement numbers the same rows the same way -> same IDs -> duplicates found
    b = stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0}, {"Date": "2025-10-12 19:05", "Amount": -20.0}])
    assert [r["ID"] for r in b] == [r["ID"] for r in a[:2]]
    # another bank's identical-looking row is a different transaction; KTB/manual rows share keys
    k = stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0, "Bank": "KBANK"}])
    assert k[0]["ID"] != a[0]["ID"]
    assert stamp_ids([{"Date": "2025-10-12 19:05", "Amount": -20.0, "Bank": "KTB"}])[0]["ID"] == a[0]["ID"]
    # conflict reporting
    assert differences({"Balance": 10, "Description": "x  y"}, {"Balance": "10.00", "Description": "x y"}) == []
    assert differences({"Balance": 10, "Description": "x"}, {"Balance": 11, "Description": "z"}) == \
        ["balance 10.00 vs 11.00", "description differs"]
    assert differences({"Balance": "", "Description": "x"}, {"Balance": 5, "Description": "x"}) == []
    print("txid self-check passed")

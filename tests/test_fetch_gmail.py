"""fetch_gmail against a fake Gmail / Pub/Sub session: paging, attachment download, seen list, notices, locking."""

import base64
import csv
import os
import threading
import time

import pytest
import requests

import fetch_gmail as fg


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


PDF = base64.urlsafe_b64encode(b"%PDF-1 x").decode()


class FakeGmail:
    """Two pages of message ids, one PDF attachment per message; every GET is recorded in .calls."""

    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        path = url.removeprefix(fg.API)
        self.calls.append((path, dict(params or {})))
        if path == "":
            if params.get("pageToken") is None:
                return Resp({"messages": [{"id": "aaaaaaaa11"}], "nextPageToken": "p2"})
            return Resp({"messages": [{"id": "bbbbbbbb22"}]})
        if path.endswith("/attachments/att1"):
            return Resp({"data": PDF})
        return Resp(
            {
                "payload": {
                    "headers": [{"name": "From", "value": "bank"}],
                    "parts": [{"filename": "s.pdf", "body": {"attachmentId": "att1"}}],
                }
            }
        )


@pytest.fixture
def outdir(tmp_path, monkeypatch):
    monkeypatch.setattr(fg, "OUTDIR", str(tmp_path / "Statement"))
    monkeypatch.setattr(fg, "RECENT", "")
    return tmp_path / "Statement"


def test_fetch_pages_and_skips_the_seen_one(outdir):
    seen = {"bbbbbbbb22"}
    got = fg.fetch(FakeGmail(), seen)
    assert [os.path.basename(g) for g in got] == ["aaaaaaaa_s.pdf"], got  # paged, and the seen one skipped
    assert open(got[0], "rb").read() == b"%PDF-1 x"
    assert "aaaaaaaa11" in seen


def test_message_ids_follows_pagination():
    assert fg.message_ids(FakeGmail(), "from:bank") == ["aaaaaaaa11", "bbbbbbbb22"]


def test_plain_run_searches_all_mail(outdir):
    fake = FakeGmail()
    fg.fetch(fake, set())
    assert not fake.calls[0][1]["q"].endswith(fg.LISTEN_WINDOW)


def test_listener_searches_only_recent_mail(outdir, monkeypatch):
    monkeypatch.setattr(fg, "RECENT", fg.LISTEN_WINDOW)
    fake = FakeGmail()
    fg.message_ids(fake, "from:bank")
    assert fake.calls[-1][1]["q"] == f"from:bank {fg.LISTEN_WINDOW}", fake.calls[-1]


class Sub:
    """Pub/Sub: one pull with two notifications, then an empty one, then a timeout."""

    def __init__(self):
        self.replies = [{"receivedMessages": [{"ackId": "k1"}, {"ackId": "k2"}]}, {}]
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url.rsplit(":", 1)[1], json))
        if url.endswith(":acknowledge"):
            return Resp({})
        if not self.replies:
            raise requests.exceptions.ReadTimeout()
        return Resp(self.replies.pop(0))


def test_notified_acknowledges_what_it_pulled():
    sub = Sub()
    assert fg.notified(sub, "S")
    assert sub.posts[-1] == ("acknowledge", {"ackIds": ["k1", "k2"]}), sub.posts


def test_notified_false_on_empty_pull_and_on_timeout():
    sub = Sub()
    fg.notified(sub, "S")
    assert not fg.notified(sub, "S")  # the empty reply
    assert not fg.notified(sub, "S")  # the long poll timing out
    assert sub.posts[-1][0] == "pull", sub.posts


KB = {
    "Date": "2026-01-02 10:00",
    "Description": "K PLUS Transfer out (email) A",
    "Category": "Transfer out",
    "Amount": "-20.00",
    "Balance": "",
    "Bank": "KBANK",
}


@pytest.fixture
def old_manual(tmp_path):
    """A manual_entries.csv from before the Bank column."""
    path = tmp_path / "manual_entries.csv"
    path.write_text(
        "Date,Description,Category,Amount,Balance\n2026-01-01,lunch,Food,-50,\n"
        "2026-01-02 10:00,K PLUS Transfer out (email) A,Transfer out,-20.00,\n",
        encoding="utf-8-sig",
    )
    return str(path)


def test_append_manual_adds_bank_column_and_skips_known_rows(old_manual):
    # hand rows "Manual", email rows their bank; a row already in the file is not added twice
    assert fg.append_manual(old_manual, [KB, {**KB, "Description": "Transfer out (email) B", "Bank": "KTB"}]) == 1
    assert fg.append_manual(old_manual, [KB]) == 0
    with open(old_manual, encoding="utf-8-sig") as f:
        assert [r["Bank"] for r in csv.DictReader(f)] == ["Manual", "KBANK", "KTB"]


def test_pull_runs_one_fetch_at_a_time_and_the_second_sees_the_first_seen_list(tmp_path, monkeypatch):
    # flock is per open file, so two threads of one process contend like two processes
    monkeypatch.setattr(fg, "SEEN", str(tmp_path / "seen.json"))
    monkeypatch.setattr(fg, "LOCK", str(tmp_path / "lock"))
    spans, saw = [], []

    def slow_fetch(svc, seen):
        start = time.monotonic()
        saw.append(set(seen))
        time.sleep(0.1)
        seen.add(f"m{len(saw)}")
        spans.append((start, time.monotonic()))
        return []

    monkeypatch.setattr(fg, "service", lambda interactive=False: None)
    monkeypatch.setattr(fg, "fetch", slow_fetch)
    monkeypatch.setattr(fg, "fetch_notices", lambda svc, seen: 0)
    both = [threading.Thread(target=fg.pull) for _ in range(2)]
    for t in both:
        t.start()
    for t in both:
        t.join()
    (_, a1), (b0, _) = sorted(spans)
    assert a1 <= b0, spans  # never at the same time
    assert saw == [set(), {"m1"}], saw  # the second saw the first's seen list

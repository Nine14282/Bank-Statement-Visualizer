"""welcome.py: names and the spending list are cleaned before use; the gates in front of handle(); uploads never
overwrite and only this setup's files can be removed; a password is saved only after it opened every locked file,
replacing the old line; Gmail settings are checked before saving; deleting everything needs DELETE typed."""

import http.client
import os
import sys
import threading
import types
from urllib.parse import urlparse

import pytest

import config
import welcome


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch, tmp_path):
    """Module state that would leak between tests: files, folder, one-time token, saved banks, settings file."""
    statements = tmp_path / "Statement"
    statements.mkdir()
    monkeypatch.setattr(welcome, "STATEMENTS", str(statements))
    monkeypatch.setattr(welcome, "FILES", {})
    monkeypatch.setattr(welcome, "SAVED", set(welcome.SAVED))
    monkeypatch.setattr(welcome, "TOKEN_USED", threading.Event())
    monkeypatch.setattr(config, "ENVFILE", str(tmp_path / "settings.env"))
    monkeypatch.setenv("KTB_PW", "x")  # config.save() writes os.environ: this puts it back after the test
    return statements


# --- names and the spending list ---


def test_safe_name_strips_the_path():
    assert welcome.safe_name("../../etc/passwd") == "passwd.pdf"


def test_safe_name_keeps_spaces_brackets_and_case():
    assert welcome.safe_name("My Statement (1).PDF") == "My Statement (1).PDF"


def test_safe_name_replaces_odd_characters():
    assert welcome.safe_name("a;b|c.pdf") == "a_b_c.pdf"


def test_clean_plan_drops_bad_items_and_keeps_key():
    plan = welcome.clean_plan(
        [
            {"name": " Lunch ", "amount": 120, "every": "day"},
            {"name": "", "amount": 5, "every": "day"},
            {"name": "Rent", "amount": -1, "every": "month"},
            {"name": "X", "amount": 1, "every": "week"},
            {"name": "Phone", "amount": "299.5", "every": "month", "key": "k"},
        ]
    )
    assert [(p["name"], p["amount"], p["every"]) for p in plan] == [("Lunch", 120, "day"), ("Phone", 299.5, "month")], (
        plan
    )
    assert plan[1]["key"] == "k"
    assert "key" not in plan[0]


# --- over HTTP: the link's token works once and becomes the cookie; every API call needs the cookie, the X-Setup
# header and our own Host name ---


@pytest.fixture
def web():
    server = welcome.Server(("127.0.0.1", 0), welcome.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    def call(method, path, cookie="", setup=True, host=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        headers = {
            "Host": host or f"127.0.0.1:{port}",
            **({"Cookie": cookie} if cookie else {}),
            **({"X-Setup": "1"} if setup else {}),
        }
        c.request(method, path, body=b"{}" if method == "POST" else None, headers=headers)
        r = c.getresponse()
        r.read()
        c.close()
        return r

    try:
        yield call
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def cookie(web):
    first = web("GET", f"/?setup={welcome.TOKEN}")
    assert first.status == 303
    assert "HttpOnly" in first.getheader("Set-Cookie")
    return (first.getheader("Set-Cookie") or "").split(";")[0]


def test_token_visit_sets_an_httponly_cookie(cookie):
    assert cookie


def test_the_link_works_once(web, cookie):
    assert web("GET", f"/?setup={welcome.TOKEN}").status == 403


def test_api_needs_the_x_setup_header(web, cookie):
    assert web("POST", "/api/state", cookie, setup=False).status == 403  # another site's form


def test_api_needs_the_cookie(web, cookie):
    assert web("POST", "/api/state").status == 403


def test_api_needs_our_own_host(web, cookie):
    assert web("POST", "/api/state", cookie, host="evil.example").status == 403  # DNS rebinding


def test_api_answers_with_cookie_header_and_host(web, cookie):
    assert web("POST", "/api/state", cookie).status == 200


# --- in the app window, Api answers only while the window shows our own page (app.our_page) ---


@pytest.fixture
def shows(monkeypatch):
    import app

    def show(url):
        window = types.SimpleNamespace(get_current_url=lambda: url)
        monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(windows=[window]))
        return app.our_page()

    show.app = app
    return show


def test_our_page_is_the_dashboard_file(shows):
    assert shows(shows.app.PAGE.as_uri() + "?app")


def test_our_page_rejects_same_file_name_in_another_folder(shows):
    assert not shows("file:///tmp/index.html")


def test_our_page_rejects_a_web_address(shows):
    assert not shows("http://x" + urlparse(shows.app.PAGE.as_uri()).path)


# --- uploads: a different file with the same name is kept as "name (2).pdf"; a file that was there before this
# setup can't be removed from the page, even after the same file is uploaded again ---


@pytest.fixture
def uploaded(fresh_state, capsys):
    welcome.upload("a.pdf", b"%PDF-1 a")
    assert welcome.upload("a.pdf", b"%PDF-1 b")["name"] == "a (2).pdf"
    welcome.FILES["a.pdf"]["uploaded"] = False
    welcome.upload("a.pdf", b"%PDF-1 a")
    return fresh_state


def test_same_name_other_content_is_kept_both(uploaded):
    assert (uploaded / "a (2).pdf").read_bytes() == b"%PDF-1 b"


def test_identical_reupload_keeps_the_file(uploaded):
    assert (uploaded / "a.pdf").read_bytes() == b"%PDF-1 a"


def test_upload_rejects_a_non_pdf():
    with pytest.raises(ValueError):
        welcome.upload("a.pdf", b"not a pdf")


def test_remove_asks_before_deleting_a_file_this_setup_did_not_add(uploaded):
    with pytest.raises(ValueError):
        welcome.handle("/api/remove", "", b'{"name": "a.pdf"}')
    assert (uploaded / "a.pdf").exists()
    welcome.handle("/api/remove", "", b'{"name": "a.pdf", "confirm": true}')
    assert not (uploaded / "a.pdf").exists()
    assert "a.pdf" not in welcome.FILES


def test_remove_refuses_a_name_not_in_the_folder(uploaded):
    with pytest.raises(ValueError):
        welcome.handle("/api/remove", "", b'{"name": "../workspace/ledger.csv", "confirm": true}')


# --- passwords: save replaces the KEY= line (export and duplicate lines too) and refuses a newline; a password that
# doesn't open the bank's files is never saved over the good one ---


def test_save_replaces_every_line_of_the_key():
    with open(config.ENVFILE, "w", encoding="utf-8") as f:
        f.write("export KTB_PW=old\nKTB_PW=dup\nOTHER=1\n")
    config.save("KTB_PW", "new")
    with open(config.ENVFILE, encoding="utf-8") as f:
        assert f.read() == "KTB_PW=new\nOTHER=1\n"


def test_save_refuses_a_newline():
    with pytest.raises(ValueError):
        config.save("X", "a\nB=c")


def test_failed_password_is_not_saved(monkeypatch, capsys):
    with open(config.ENVFILE, "w", encoding="utf-8") as f:
        f.write("KTB_PW=new\nOTHER=1\n")

    def wrong_password(path, password):
        raise ValueError("wrong password")

    monkeypatch.setattr(welcome, "extract", wrong_password)
    welcome.FILES["a.pdf"] = {"bank": "KTB", "ok": False}
    assert welcome.unlock("KTB", "bad", True)["ok"] is False
    with open(config.ENVFILE, encoding="utf-8") as f:
        assert "KTB_PW=new\n" in f.read()
    assert os.environ["KTB_PW"] == "x"


# --- the browser app: its link lands on ?web, and the page's ping is answered (it keeps the server from stopping) ---


def test_link_opens_the_browser_app(web):
    assert web("GET", f"/?setup={welcome.TOKEN}").getheader("Location") == "/?web"


def test_ping_needs_the_cookie(web, cookie):
    assert web("GET", "/api/ping").status == 404
    assert web("GET", "/api/ping", cookie).status == 204


# --- Gmail settings (Settings, last step): checked before saving; a blank secret keeps the saved one; real time needs
# all three of its fields ---

ID = "123-abc.apps.googleusercontent.com"


@pytest.fixture
def google_env(monkeypatch):
    for k in welcome.GOOGLE.values():
        monkeypatch.setenv(k, "")  # config.save() writes os.environ: this puts it back after the test


def env_file() -> str:
    with open(config.ENVFILE, encoding="utf-8") as f:
        return f.read()


def test_google_saves_the_keys(google_env, capsys):
    welcome.google({"id": ID, "secret": "GOCSPX-secret_1"})
    assert f"GOOGLE_CLIENT_ID={ID}\n" in env_file()
    assert "GOOGLE_CLIENT_SECRET=GOCSPX-secret_1\n" in env_file()
    assert welcome.state()["google"]["secret"] is True  # the page learns only that it is saved


def test_google_blank_secret_keeps_the_saved_one(google_env, capsys):
    welcome.google({"id": ID, "secret": "GOCSPX-secret_1"})
    welcome.google({"id": ID, "secret": ""})
    assert "GOOGLE_CLIENT_SECRET=GOCSPX-secret_1\n" in env_file()


def test_google_needs_a_secret_the_first_time(google_env):
    with pytest.raises(ValueError):
        welcome.google({"id": ID})


def test_google_rejects_a_malformed_id(google_env):
    with pytest.raises(ValueError):
        welcome.google({"id": "not an id", "secret": "GOCSPX-secret_1"})
    assert not os.path.exists(config.ENVFILE)


def test_google_real_time_needs_all_three(google_env):
    with pytest.raises(ValueError):
        welcome.google({"id": ID, "secret": "GOCSPX-secret_1", "topic": "gmail-push"})


def test_google_accepts_the_consoles_full_topic_path(google_env, capsys):
    welcome.google(
        {
            "id": ID,
            "secret": "GOCSPX-secret_1",
            "project": "my-project",
            "topic": "projects/my-project/topics/gmail-push",
            "subscription": "gmail-sub",
        }
    )
    assert "GMAIL_TOPIC=projects/my-project/topics/gmail-push\n" in env_file()


# --- Delete all my data: only with the typed confirmation ---


def test_clear_needs_delete_typed():
    with pytest.raises(ValueError):  # refused before anything runs
        welcome.handle("/api/clear", "", b'{"confirm": "delete"}')

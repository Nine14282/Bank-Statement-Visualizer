"""launcher.py: setup() per build kind, the --smoke import list, and SV_ROOT (importing it chdirs to ROOT)."""

import os
import subprocess
import sys

import pytest

import config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    """The module, imported under a temp cwd (the import chdirs to ROOT and sets PYTHONUTF8; both undone after)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONUTF8", "1")
    import launcher

    monkeypatch.chdir(tmp_path)  # the import moved us to ROOT
    return launcher


@pytest.fixture
def calls(launcher, monkeypatch):
    """Stubs for everything setup() does outside itself; the names called, in order, with install_packages' mode."""
    log = []
    monkeypatch.setattr(launcher, "installed_mode", lambda: None)
    monkeypatch.setattr(launcher, "TTY_IN", False)
    monkeypatch.setattr(launcher, "install_packages", lambda mode: log.append(("install_packages", mode)))
    monkeypatch.setattr(launcher, "prepare", lambda: log.append("prepare"))
    monkeypatch.setattr(launcher, "py", lambda name, *a, **k: log.append(("py", name)) or 0)
    monkeypatch.setattr(launcher, "make_launcher", lambda: log.append("make_launcher"))
    monkeypatch.setattr(launcher, "detach", lambda argv: log.append("detach"))
    return log


# --- setup() -------------------------------------------------------------------------------------------------------


def test_setup_from_source_installs_app_packages(launcher, calls, monkeypatch):
    monkeypatch.setattr(launcher, "FROZEN", False)
    monkeypatch.setattr(launcher, "WIN", False)
    assert launcher.setup([], open_after=False) == 0
    assert calls == [("install_packages", "app"), "prepare", ("py", "build_dashboard"), "make_launcher"]


def test_setup_from_source_on_windows_defaults_to_web(launcher, calls, monkeypatch):
    monkeypatch.setattr(launcher, "FROZEN", False)
    monkeypatch.setattr(launcher, "WIN", True)
    launcher.setup([], open_after=False)
    assert ("install_packages", "web") in calls
    assert "make_launcher" not in calls


def test_setup_frozen_windows_app_installs_no_packages(launcher, calls, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "FROZEN", True)
    monkeypatch.setattr(launcher, "WIN", True)
    launcher.setup(["--app"], open_after=False)
    assert not [c for c in calls if isinstance(c, tuple) and c[0] == "install_packages"]
    assert calls == ["prepare", ("py", "build_dashboard"), "make_launcher"]
    assert "everything happens in the app" in capsys.readouterr().out


def test_setup_frozen_windows_web(launcher, calls, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "FROZEN", True)
    monkeypatch.setattr(launcher, "WIN", True)
    launcher.setup(["--web"], open_after=False)
    assert calls == ["prepare", ("py", "build_dashboard")]
    out = capsys.readouterr().out
    assert "browser mode" in out
    assert "Want the app window instead?" not in out  # the build has no --app to add


def test_setup_frozen_linux_forces_web_with_its_message(launcher, calls, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "FROZEN", True)
    monkeypatch.setattr(launcher, "WIN", False)
    launcher.setup(["--app"], open_after=False)
    assert calls == ["prepare", ("py", "build_dashboard")]
    out = capsys.readouterr().out
    assert "This build has no app window here" in out
    assert "browser mode" in out


def test_setup_rejects_unknown_option(launcher, calls):
    with pytest.raises(SystemExit):
        launcher.setup(["--bogus"])
    assert calls == []


def test_setup_stops_when_the_dashboard_build_fails(launcher, calls, monkeypatch):
    monkeypatch.setattr(launcher, "py", lambda *a, **k: 1)
    with pytest.raises(SystemExit):
        launcher.setup([], open_after=False)
    assert "make_launcher" not in calls


# --- --smoke -------------------------------------------------------------------------------------------------------


def test_smoke_list_names_every_script(launcher):
    assert set(config.SCRIPTS) <= set(launcher.smoke_modules())


def test_smoke_list_names_the_lazily_imported_packages(launcher, monkeypatch):
    # app.py and fetch_gmail.py import these only when they run, so importing the scripts doesn't prove them
    monkeypatch.setattr(launcher, "WIN", False)
    mods = launcher.smoke_modules()
    assert {"pdfplumber", "google.auth.transport.requests", "google_auth_oauthlib"} <= set(mods)
    assert "webview" not in mods


def test_smoke_list_has_the_app_window_on_windows(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "WIN", True)
    assert "webview" in launcher.smoke_modules()


def test_smoke_ok(launcher, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "WIN", False)
    assert launcher.smoke() == 0
    assert "smoke ok" in capsys.readouterr().out


def test_smoke_names_the_failed_import(launcher, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "smoke_modules", lambda: ["os", "no_such_module_for_smoke"])
    assert launcher.smoke() == 1
    cap = capsys.readouterr()
    assert "no_such_module_for_smoke" in cap.err
    assert "smoke ok" not in cap.out


def test_smoke_option_is_frozen_only(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "smoke", lambda: 7)
    monkeypatch.setattr(launcher, "FROZEN", True)
    assert launcher.main(["--smoke"]) == 7
    monkeypatch.setattr(launcher, "FROZEN", False)
    with pytest.raises(SystemExit):  # from source it is not a command
        launcher.main(["--smoke"])


# --- SV_ROOT -------------------------------------------------------------------------------------------------------


def test_root_is_the_temp_root(launcher, sv_root):
    assert sv_root == launcher.ROOT


def _root_and_cwd(tmp_path, **env):
    """ROOT and the cwd after importing launcher in a fresh Python (it chdirs at import)."""
    full = {k: v for k, v in os.environ.items() if k != "SV_ROOT"} | env
    out = subprocess.run(
        [sys.executable, "-c", "import os, launcher; print(launcher.ROOT); print(os.getcwd())"],
        cwd=tmp_path,
        env=full | {"PYTHONPATH": os.path.join(REPO, "workspace")},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    return os.path.realpath(out[0]), os.path.realpath(out[1])


def test_sv_root_redirects_root_and_cwd(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    assert _root_and_cwd(tmp_path, SV_ROOT=str(data)) == (os.path.realpath(data),) * 2


def test_root_is_the_repo_without_sv_root(tmp_path):
    assert _root_and_cwd(tmp_path) == (os.path.realpath(REPO),) * 2

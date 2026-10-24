"""app.py: one app at a time; a second launch asks the open one to come to the front instead of opening another."""

import os
import time

import pytest

import app


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "STORE", str(tmp_path))
    monkeypatch.setattr(app, "RAISE", str(tmp_path / "raise"))
    return tmp_path


def test_second_launch_raises_the_first(store):
    raised = []
    first = app.only_window(lambda: raised.append(1))
    try:
        assert first
        assert app.only_window(lambda: None) is None  # the second one gets no lock...
        deadline = time.monotonic() + 5
        while not raised and time.monotonic() < deadline:
            time.sleep(0.1)
        assert raised  # ...and the first one heard about it
        assert not os.path.exists(store / "raise")
    finally:
        first.close()


def test_bring_forward_restores_only_a_minimized_window():
    calls = []
    w = type("W", (), {"restore": lambda self: calls.append("restore"), "show": lambda self: calls.append("show")})()
    app.bring_forward(w, {"minimized": False})
    app.bring_forward(w, {"minimized": True})
    assert calls == ["show", "restore", "show"]

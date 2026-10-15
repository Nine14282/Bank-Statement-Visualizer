"""The isolation itself: nothing a test does can reach the real data."""

import os

import config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_root_is_the_temp_root(sv_root):
    assert sv_root == config.ROOT
    assert os.path.join(sv_root, "workspace") == config.WORK


def test_root_is_not_the_real_repo(sv_root):
    assert os.path.realpath(config.ROOT) != os.path.realpath(REPO)
    assert not os.path.realpath(config.ROOT).startswith(os.path.realpath(REPO) + os.sep)


def test_envfile_is_inside_the_temp_root(sv_root):
    assert os.path.dirname(config.ENVFILE) == sv_root


def test_app_is_the_repo_with_the_prebuilt_page():
    assert os.path.realpath(config.APP) == os.path.realpath(REPO)
    assert os.path.isfile(os.path.join(config.APP, "web", "prebuilt", "index.html"))

"""The API's build, for the sidebar's version line: Vercel's commit when it's
given, and on every page's frame."""

from app import build

from .test_tax_api import app, ana, client  # noqa: F401 (fixtures)


def test_vercels_commit_is_used_when_given(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "c6705e1d2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c")
    assert build._commit() == "c6705e1"


def test_the_frame_carries_the_apis_build(client, ana, monkeypatch):
    monkeypatch.setattr(build, "COMMIT", "c6705e1")
    assert client.get("/finance/frame", headers=ana).json()["build"] == "c6705e1"
    monkeypatch.setattr(build, "COMMIT", None)
    assert client.get("/finance/frame", headers=ana).json()["build"] is None


def test_the_frame_says_where_the_build_came_from(client, ana, monkeypatch):
    # Only two deployed builds are compared by the screens (fixed 2026-10-22: false warning on dev machines).
    assert client.get("/finance/frame", headers=ana).json()["buildSource"] == "local"
    monkeypatch.setattr(build, "SOURCE", "vercel")
    assert client.get("/finance/frame", headers=ana).json()["buildSource"] == "vercel"

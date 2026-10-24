"""Tests for locating the trained model's artifact.

The default has to hold wherever the process happens to be started from: App
Service extracts the application into a directory it generates at container
start, so a path relative to the working directory does not point at the app.
"""

from pathlib import Path

import pytest

pytest.importorskip("lightgbm")

from app.forecast.service import DEFAULT_MODEL_PATH, MODEL_PATH_ENV, resolve_model_path


def test_default_path_is_absolute():
    assert DEFAULT_MODEL_PATH.is_absolute()


def test_default_path_sits_beside_the_application_package():
    assert DEFAULT_MODEL_PATH.name == "revenue_model.joblib"
    assert DEFAULT_MODEL_PATH.parent.name == "models"
    assert (DEFAULT_MODEL_PATH.parent.parent / "app" / "forecast").is_dir()


def test_default_path_does_not_follow_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv(MODEL_PATH_ENV, raising=False)
    resolved_before = resolve_model_path()

    monkeypatch.chdir(tmp_path)

    assert resolve_model_path() == resolved_before
    assert Path(resolve_model_path()).is_absolute()


def test_configured_path_overrides_the_default(monkeypatch):
    monkeypatch.setenv(MODEL_PATH_ENV, "/srv/models/revenue_model.joblib")

    assert resolve_model_path() == "/srv/models/revenue_model.joblib"


def test_explicit_path_overrides_the_configured_one(monkeypatch):
    monkeypatch.setenv(MODEL_PATH_ENV, "/srv/models/revenue_model.joblib")

    assert resolve_model_path("/var/models/other.joblib") == "/var/models/other.joblib"


def test_an_empty_configured_path_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(MODEL_PATH_ENV, "")

    assert resolve_model_path() == str(DEFAULT_MODEL_PATH)

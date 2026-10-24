"""Shared setup that keeps the forecast tests off two live services.

``service.forecast_from_dataframe`` prefers the endpoint whenever
``AZURE_FORECAST_ENDPOINT`` and ``AZURE_FORECAST_KEY`` are set. A developer who has
sourced ``.env`` would otherwise have the whole suite calling a paid remote service,
which is slow, costs money, and makes the assertions depend on whether that service
happens to be deployed today.

Clearing both variables for every test in this package makes the local artifact the
answer by default. Tests that want the endpoint set the variables themselves.

The second is Azure Blob storage. ``prepare_upload`` and ``load_cleaned`` read and
write through it, so without a stand-in these tests would need real credentials for
a real container.
"""

import os

import pytest

import app.data_pipeline.preparation as preparation
from app.forecast import automl_endpoint


@pytest.fixture(autouse=True)
def local_model_only(monkeypatch):
    monkeypatch.delenv(automl_endpoint.ENDPOINT_URL, raising=False)
    monkeypatch.delenv(automl_endpoint.ENDPOINT_KEY, raising=False)


def _safe_name(filename: str) -> str:
    """Mirrors AzureStorage's own check so the fake rejects a path the way a
    real Blob-backed call would, rather than storing it as an odd key."""
    safe = os.path.basename(filename)
    if safe != filename or not safe:
        raise ValueError(f"Invalid filename: {filename!r}")
    return safe


class _FakeAzureStorage:
    """In-memory stand-in for AzureStorage, keyed by (user_id, filename).

    Same shape as the fake in tests/data_pipeline/test_data_preparation.py, and
    for the same reason: prepare_upload and load_cleaned need somewhere to write
    and read that is not a real Blob container, since neither the CI agent nor a
    developer's machine is guaranteed to have credentials for one.
    """

    _store: dict = {}

    def __init__(self, user_id):
        self.user_id = user_id

    async def save(self, filename, contents):
        safe = _safe_name(filename)
        self._store[(self.user_id, safe)] = contents
        return f"user-{self.user_id}/{safe}"

    def exists(self, filename):
        return (self.user_id, _safe_name(filename)) in self._store

    def load(self, filename):
        safe = _safe_name(filename)
        try:
            return self._store[(self.user_id, safe)]
        except KeyError as exc:
            raise FileNotFoundError(filename) from exc

    def delete(self, filename):
        self._store.pop((self.user_id, _safe_name(filename)), None)

    def list_files(self):
        return [f for (uid, f) in self._store if uid == self.user_id]


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    """Keep these tests off real Azure Blob storage.

    Patched on the preparation module because prepare_upload and load_cleaned
    resolve AzureStorage from their own module globals at call time.
    """
    _FakeAzureStorage._store.clear()
    monkeypatch.setattr(preparation, "AzureStorage", _FakeAzureStorage)
    return _FakeAzureStorage

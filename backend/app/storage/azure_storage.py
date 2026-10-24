from __future__ import annotations

import os
import threading

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContainerClient

from app.core.config import AZURE_STORAGE_ACCOUNT_URL, credential
from app.storage.base import StorageBase

# Single container shared by every user - each user's files live under their
# own "folder" inside it (a blob-name prefix; Blob Storage has no real
# directories, so "folder" here just means every blob name starts with
# "user-<id>/"). Rename this if the team picks a different container name -
# nothing else in this file needs to change.
DATASETS_CONTAINER_NAME = "datasets"

_blob_service_client: BlobServiceClient | None = None

# The container itself only needs to be created once per process, not once
# per user (there's only one container now, not one per user) - this flag
# plus the lock avoid a network call to check/create it on every AzureStorage
# instantiation.
_container_ensured = False
_container_ensure_lock = threading.Lock()


def _get_blob_service_client() -> BlobServiceClient:
    global _blob_service_client
    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient(
            account_url=AZURE_STORAGE_ACCOUNT_URL,
            credential=credential,
        )
    return _blob_service_client


def _ensure_container(container_client: ContainerClient) -> None:
    global _container_ensured
    if _container_ensured:
        return
    with _container_ensure_lock:
        if _container_ensured:
            return
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass
        _container_ensured = True


def _prefix_for_user(user_id: int) -> str:
    return f"user-{user_id}/"


def _safe_blob_name(filename: str) -> str:
    """Validates the filename portion only - the user prefix is added
    separately by the caller, never taken from `filename` itself, so a
    filename can't be crafted to write outside the user's own folder.
    """
    safe = os.path.basename(filename)
    if safe != filename or not safe:
        raise ValueError(f"Invalid filename: {filename!r}")
    return safe


class AzureStorage(StorageBase):
    """Storage backend scoped to a single user's folder inside the one
    shared datasets container (blob names are prefixed "user-<id>/...").
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.container_name = DATASETS_CONTAINER_NAME
        self._prefix = _prefix_for_user(user_id)
        self._service_client = _get_blob_service_client()
        self._container_client: ContainerClient = self._service_client.get_container_client(self.container_name)
        _ensure_container(self._container_client)

    def _blob_client(self, filename: str):
        safe_name = _safe_blob_name(filename)
        return self._container_client.get_blob_client(f"{self._prefix}{safe_name}")

    async def save(self, filename: str, contents: bytes) -> str:
        blob_client = self._blob_client(filename)
        blob_client.upload_blob(contents, overwrite=True)
        return f"{self.container_name}/{self._prefix}{_safe_blob_name(filename)}"

    def exists(self, filename: str) -> bool:
        return self._blob_client(filename).exists()

    def load(self, filename: str) -> bytes:
        blob_client = self._blob_client(filename)
        try:
            return blob_client.download_blob().readall()
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(f"No such file for this user: {filename!r}") from exc

    def delete(self, filename: str) -> None:
        blob_client = self._blob_client(filename)
        try:
            blob_client.delete_blob()
        except ResourceNotFoundError:
            pass

    def list_files(self) -> list[str]:
        # list_blobs(name_starts_with=...) scopes the listing server-side to
        # this user's folder only - other users' blobs are never returned
        # even though they live in the same container.
        prefix_len = len(self._prefix)
        return [blob.name[prefix_len:] for blob in self._container_client.list_blobs(name_starts_with=self._prefix)]

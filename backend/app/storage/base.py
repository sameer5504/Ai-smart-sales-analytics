from abc import ABC, abstractmethod


class StorageBase(ABC):
    @abstractmethod
    async def save(self, filename: str, contents: bytes) -> str: ...

    @abstractmethod
    def exists(self, filename: str) -> bool: ...

    @abstractmethod
    def load(self, filename: str) -> bytes:
        """Raises FileNotFoundError if filename is not stored."""
        ...

    @abstractmethod
    def delete(self, filename: str) -> None: ...

    @abstractmethod
    def list_files(self) -> list[str]: ...

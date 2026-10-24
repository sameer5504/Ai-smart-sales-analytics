import os

from app.storage.base import StorageBase


class LocalStorage(StorageBase):
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir

    def get_path(self, filename: str) -> str:
        safe_filename = os.path.basename(filename)

        if safe_filename != filename:
            raise ValueError("Invalid filename")

        return os.path.join(self.base_dir, safe_filename)

    def exists(self, filename: str) -> bool:
        return os.path.isfile(self.get_path(filename))

    async def save(self, filename: str, contents: bytes) -> str:
        os.makedirs(self.base_dir, exist_ok=True)
        save_path = self.get_path(filename)

        with open(save_path, "wb") as f:
            f.write(contents)

        return save_path

    def load(self, filename: str) -> bytes:
        path = self.get_path(filename)

        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {filename!r}")

        with open(path, "rb") as f:
            return f.read()

    def delete(self, filename: str) -> None:
        path = self.get_path(filename)

        if os.path.isfile(path):
            os.remove(path)

    def list_files(self) -> list[str]:
        if not os.path.isdir(self.base_dir):
            return []

        return [name for name in os.listdir(self.base_dir) if os.path.isfile(os.path.join(self.base_dir, name))]

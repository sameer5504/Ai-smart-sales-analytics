import os


def get_extension(file_path: str) -> str:
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path must be a non-empty string")

    return os.path.splitext(file_path)[1].lower()

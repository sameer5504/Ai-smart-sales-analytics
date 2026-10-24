import json
from pathlib import Path

from .normalise import normalise

_PATH = Path(__file__).resolve().parents[2] / "config" / "column_aliases.json"


def standard_fields(path=_PATH) -> dict:
    """Return the full schema: field -> {required, label, aliases}."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_aliases(path=_PATH) -> dict:
    """Return a flat lookup: normalised alias -> standard field name."""
    schema = standard_fields(path)
    lookup, seen = {}, {}
    for field, meta in schema.items():
        for alias in meta["aliases"]:
            key = normalise(alias)
            if key in seen:
                raise ValueError(
                    f"Alias '{alias}' claimed by both '{seen[key]}' and '{field}'"
                )
            seen[key] = field
            lookup[key] = field
    return lookup
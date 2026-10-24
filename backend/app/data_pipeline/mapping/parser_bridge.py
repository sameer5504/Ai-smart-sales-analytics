"""Bridge between parser output and column mapping.

The parser returns a dictionary containing the parsed DataFrame metadata,
including a ``columns`` list. This module extracts those column names and
builds the mapping contract.
"""

from .contract import build_mapping_result


def extract_headers(parsed):
    """Extract column names from supported parser output shapes."""

    if hasattr(parsed, "columns"):  # pandas DataFrame
        return [str(c) for c in parsed.columns]

    if isinstance(parsed, dict) and "columns" in parsed:
        return [str(c) for c in parsed["columns"]]

    if isinstance(parsed, dict) and "headers" in parsed:
        return [str(h) for h in parsed["headers"]]

    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return [str(k) for k in parsed[0].keys()]

    raise ValueError(f"Unrecognised parser output type: {type(parsed).__name__}")


def map_parsed_file(parsed):
    """Convert parser output into the mapping contract."""
    headers = extract_headers(parsed)
    result = build_mapping_result(headers)
    result["column_count"] = len(headers)
    return result

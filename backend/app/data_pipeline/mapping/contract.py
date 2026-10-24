"""Mapping result contract for US-1.4.1 / US-1.4.2.

Groups scored columns into recognised / ambiguous / unrecognised and
reports which required standard fields remain unmapped.
"""

from .aliases import standard_fields
from .matcher import AUTO_ACCEPT, match_columns


def build_mapping_result(headers, schema=None):
    """Return the mapping contract consumed by the manual-mapping step."""
    schema = schema or standard_fields()
    scored = match_columns(headers, schema=schema)

    recognised, ambiguous, unrecognised = [], [], []

    for item in scored:
        entry = {
            "column": item["column"],
            "suggested_field": item["field"],
            "confidence": item["confidence"],
        }
        if "conflict_with" in item:
            entry["conflict_with"] = item["conflict_with"]

        if item["field"] and item["confidence"] >= AUTO_ACCEPT:
            recognised.append(entry)
        elif item["field"] or "conflict_with" in item:
            ambiguous.append(entry)
        else:
            unrecognised.append(entry)

    mapped = {i["suggested_field"] for i in recognised}
    unmapped_required = [f for f, meta in schema.items() if meta["required"] and f not in mapped]

    return {
        "recognised": recognised,
        "ambiguous": ambiguous,
        "unrecognised": unrecognised,
        "unmapped_required_fields": unmapped_required,
        "ready_for_analysis": len(unmapped_required) == 0,
    }

"""
Tiers: exact (1.0) -> normalised (0.95) -> alias (0.90) -> fuzzy (ratio).
AUTO_ACCEPT 0.85 is trusted; SUGGEST_FLOOR 0.80 is the minimum to offer
a suggestion. Below that the column is left unassigned.
"""

from difflib import SequenceMatcher

from .aliases import load_aliases, standard_fields
from .normalise import normalise

AUTO_ACCEPT = 0.85
SUGGEST_FLOOR = 0.80


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _score_column(header: str, schema: dict, lookup: dict):
    """Return (best_field, confidence) for one raw header."""
    norm = normalise(header)
    if not norm:
        return None, 0.0

    if header in schema:                       # tier 1
        return header, 1.0

    for field in schema:                       # tier 2
        if norm == normalise(field):
            return field, 0.95

    if norm in lookup:                         # tier 3
        return lookup[norm], 0.90

    best_field, best_score = None, 0.0         # tier 4
    for field, meta in schema.items():
        candidates = [normalise(field)] + [normalise(a) for a in meta["aliases"]]
        for cand in candidates:
            score = _similarity(norm, cand)
            if score > best_score:
                best_field, best_score = field, score

    if best_score >= SUGGEST_FLOOR:
        return best_field, best_score
    return None, best_score


def match_columns(headers, schema=None, lookup=None):
    """Map raw file headers to standard fields with confidence scores."""
    schema = schema or standard_fields()
    lookup = lookup or load_aliases()

    scored = []
    for header in headers:
        field, conf = _score_column(header, schema, lookup)
        scored.append({
            "column": header,
            "field": field,
            "confidence": round(conf, 3),
        })

    claimed = {}
    for item in sorted(scored, key=lambda x: -x["confidence"]):
        field = item["field"]
        if field is None:
            continue
        if field in claimed:
            item["field"] = None
            item["conflict_with"] = claimed[field]
        else:
            claimed[field] = item["column"]

    return scored
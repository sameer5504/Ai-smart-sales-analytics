import pytest

from app.data_pipeline.mapping.aliases import load_aliases, standard_fields
from app.data_pipeline.mapping.normalise import normalise


@pytest.mark.parametrize(
    "raw",
    [
        "Order_Date ",
        "ORDER DATE",
        "order-date",
        "Order  Date",
    ],
)
def test_normalise_variants(raw):
    assert normalise(raw) == "order date"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Price ($)", "price"),
        ("Qty.", "qty"),
        ("Unit-Price!", "unit price"),
    ],
)
def test_normalise_punctuation(raw, expected):
    assert normalise(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_normalise_empty(raw):
    assert normalise(raw) == ""


def test_aliases_load_without_conflicts():
    lookup = load_aliases()
    assert lookup["qty"] == "quantity"
    assert lookup["item"] == "product_name"
    assert lookup["order date"] == "transaction_date"


def test_six_required_one_optional():
    schema = standard_fields()
    required = [f for f, m in schema.items() if m["required"]]
    assert len(required) == 6
    assert schema["category"]["required"] is False

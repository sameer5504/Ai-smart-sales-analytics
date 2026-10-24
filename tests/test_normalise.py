from src.mapping.aliases import load_aliases, standard_fields
from src.mapping.normalise import normalise


def test_normalise_variants():
    for raw in ["Order_Date ", "ORDER DATE", "order-date", "Order  Date"]:
        assert normalise(raw) == "order date"


def test_normalise_punctuation():
    assert normalise("Price ($)") == "price"


def test_normalise_empty():
    assert normalise("") == ""
    assert normalise(None) == ""


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
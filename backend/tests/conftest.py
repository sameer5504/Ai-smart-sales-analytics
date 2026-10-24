import sys
from pathlib import Path

import pytest

# Mirror the sys.path bootstrap in app/main.py so tests can import both the
# `app` package (backend/) and the shared `src.mapping` package (repo root)
# regardless of the directory pytest is invoked from.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (_BACKEND_DIR, _REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


@pytest.fixture
def valid_sales_mapping() -> dict:
    return {
        "data_type": "sales",
        "file_name": "sample_sales.xlsx",
        "source_columns": [
            "Order Date",
            "Order Number",
            "Item Code",
            "Item",
            "Qty",
            "Price",
            "Category",
            "Notes",
        ],
        "mapped_fields": {
            "Order Date": "transaction_date",
            "Order Number": "order_id",
            "Item Code": "product_id",
            "Item": "product_name",
            "Qty": "quantity",
            "Price": "unit_price",
            "Category": "category",
        },
        "unmapped_columns": [
            "Notes",
        ],
    }


@pytest.fixture
def missing_fields_sales_mapping() -> dict:
    return {
        "data_type": "sales",
        "file_name": "sample_sales_missing_fields.csv",
        "source_columns": [
            "Order Date",
            "Item",
            "Qty",
            "Price",
            "Notes",
        ],
        "mapped_fields": {
            "Order Date": "transaction_date",
            "Item": "product_name",
            "Qty": "quantity",
            "Price": "unit_price",
        },
        "unmapped_columns": [
            "Notes",
        ],
    }


@pytest.fixture
def alternative_names_sales_mapping() -> dict:
    return {
        "data_type": "sales",
        "file_name": "alternative_sales_columns.csv",
        "source_columns": [
            "Sales Date",
            "Invoice ID",
            "SKU",
            "Product",
            "Units Sold",
            "Selling Price",
            "Product Category",
        ],
        "mapped_fields": {
            "Sales Date": "transaction_date",
            "Invoice ID": "order_id",
            "SKU": "product_id",
            "Product": "product_name",
            "Units Sold": "quantity",
            "Selling Price": "unit_price",
            "Product Category": "category",
        },
        "unmapped_columns": [],
    }


@pytest.fixture
def authenticated_user():
    from app.auth.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    try:
        yield {"user_id": 1}
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

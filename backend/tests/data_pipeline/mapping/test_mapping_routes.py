import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

pytestmark = pytest.mark.usefixtures("authenticated_user")


# --- In-memory fakes for Azure Blob Storage and the datasets DB table -----
# Same rationale as tests/data_pipeline/upload/test_upload_route.py: this
# file drives real uploads/mapping through the API, which needs Azure Blob +
# Postgres underneath - not available on the CI agent. See that file's
# comment for the full explanation.


class _FakeAzureStorage:
    _store: dict = {}

    def __init__(self, user_id):
        self.user_id = user_id

    async def save(self, filename, contents):
        self._store[(self.user_id, filename)] = contents
        return f"user-{self.user_id}/{filename}"

    def exists(self, filename):
        return (self.user_id, filename) in self._store

    def load(self, filename):
        try:
            return self._store[(self.user_id, filename)]
        except KeyError as exc:
            raise FileNotFoundError(filename) from exc

    def delete(self, filename):
        self._store.pop((self.user_id, filename), None)

    def list_files(self):
        return [f for (uid, f) in self._store if uid == self.user_id]


# A plain list, not keyed by (user_id, filename) - re-uploading/re-applying
# under the same display filename now creates a separate row (see
# insert_dataset), so the same filename can legitimately appear more than
# once here.
_fake_datasets: list = []
_next_id = [1]


def _fake_insert_dataset(user_id, filename, blob_path, row_count, stored, currency=None, content_hash=None):
    entry = {
        "id": _next_id[0],
        "user_id": user_id,
        "filename": filename,
        "blob_path": blob_path,
        "row_count": row_count,
        "stored": stored,
        "currency": currency,
        "content_hash": content_hash,
        "created_at": "2026-01-01T00:00:00Z",
    }
    _next_id[0] += 1
    _fake_datasets.append(entry)
    return entry


def _fake_list_datasets_for_user(user_id):
    return [d for d in _fake_datasets if d["user_id"] == user_id]


def _fake_get_dataset_for_user(dataset_id, user_id):
    for d in _fake_datasets:
        if d["id"] == dataset_id and d["user_id"] == user_id:
            return d
    return None


def _fake_delete_dataset(dataset_id, user_id):
    for i, d in enumerate(_fake_datasets):
        if d["id"] == dataset_id and d["user_id"] == user_id:
            del _fake_datasets[i]
            return True
    return False


def _fake_find_matching_dataset(user_id, content_hash, currency):
    for d in _fake_datasets:
        if (
            d["user_id"] == user_id
            and d.get("content_hash") == content_hash
            and d.get("currency") == currency
            and d.get("stored")
        ):
            return d
    return None


@pytest.fixture(autouse=True)
def _mock_external_storage(monkeypatch):
    _FakeAzureStorage._store.clear()
    _fake_datasets.clear()
    _next_id[0] = 1

    monkeypatch.setattr("app.data_pipeline.preparation.AzureStorage", _FakeAzureStorage)
    monkeypatch.setattr("app.data_pipeline.mapping.router.insert_dataset", _fake_insert_dataset)
    monkeypatch.setattr("app.data_pipeline.mapping.router.find_matching_dataset", _fake_find_matching_dataset)
    monkeypatch.setattr("app.db.datasets_router.list_datasets_for_user", _fake_list_datasets_for_user)
    monkeypatch.setattr("app.db.datasets_router.AzureStorage", _FakeAzureStorage)
    monkeypatch.setattr("app.db.datasets_router.delete_dataset", _fake_delete_dataset)
    monkeypatch.setattr("app.dashboard.router.get_dataset_for_user", _fake_get_dataset_for_user)


VALID_COLUMNS = [
    "Order Date",
    "Order No",
    "SKU",
    "Item",
    "Qty",
    "Unit Price",
    "Notes",
]
VALID_MAPPING = {
    "Order Date": "transaction_date",
    "Order No": "order_id",
    "SKU": "product_id",
    "Item": "product_name",
    "Qty": "quantity",
    "Unit Price": "unit_price",
}


def test_schema_lists_seven_standard_fields_with_required_flags():
    res = client.get("/api/mapping/schema")
    assert res.status_code == 200
    fields = res.json()
    assert len(fields) == 7
    by_key = {f["key"]: f for f in fields}
    assert by_key["category"]["required"] is False
    required = [f for f in fields if f["required"]]
    assert len(required) == 6


def test_suggest_reuses_automatic_matcher():
    res = client.post("/api/mapping/suggest", json={"columns": ["Qty", "Notes"]})
    assert res.status_code == 200
    suggestions = {s["column"]: s for s in res.json()["suggestions"]}
    assert suggestions["Qty"]["field"] == "quantity"
    assert suggestions["Notes"]["field"] is None


def test_valid_manual_mapping_is_accepted():
    res = client.post(
        "/api/mapping/submit",
        json={"columns": VALID_COLUMNS, "mapping": VALID_MAPPING},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["mapping"]["order_id"] == "Order No"
    assert "category" not in body["mapping"]  # optional field, left unmapped


def test_optional_field_can_be_left_unmapped_but_required_cannot():
    mapping = dict(VALID_MAPPING)
    del mapping["Order No"]  # order_id is required
    res = client.post(
        "/api/mapping/submit",
        json={"columns": VALID_COLUMNS, "mapping": mapping},
    )
    assert res.status_code == 422
    errors = res.json()["detail"]["errors"]
    assert errors["missing_required_fields"] == ["order_id"]


def test_missing_required_fields_lists_every_missing_field():
    res = client.post(
        "/api/mapping/submit",
        json={"columns": VALID_COLUMNS, "mapping": {"Order Date": "transaction_date"}},
    )
    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["success"] is False
    missing = body["detail"]["errors"]["missing_required_fields"]
    assert set(missing) == {"order_id", "product_id", "product_name", "quantity", "unit_price"}


def test_invalid_mapping_reports_unknown_field_and_unknown_column():
    res = client.post(
        "/api/mapping/submit",
        json={
            "columns": ["A", "B"],
            "mapping": {"A": "not_a_real_field", "C": "order_id"},
        },
    )
    assert res.status_code == 422
    errors = res.json()["detail"]["errors"]
    assert errors["unknown_fields"] == ["not_a_real_field"]
    assert errors["unknown_columns"] == ["C"]


def test_duplicate_field_mapping_is_rejected():
    res = client.post(
        "/api/mapping/submit",
        json={
            "columns": ["A", "B"],
            "mapping": {"A": "order_id", "B": "order_id"},
        },
    )
    assert res.status_code == 422
    errors = res.json()["detail"]["errors"]
    assert errors["duplicate_field_mapping"] == {"order_id": ["A", "B"]}


@pytest.mark.parametrize(
    "payload",
    [
        {"mapping": {"A": "order_id"}},  # missing "columns"
        {"columns": "not-a-list", "mapping": {}},  # wrong type for "columns"
        {"columns": ["A"], "mapping": {"A": 123}},  # wrong type for mapping value
        {},  # empty body
    ],
)
def test_malformed_requests_are_rejected_before_business_validation(payload):
    res = client.post("/api/mapping/submit", json=payload)
    assert res.status_code == 422
    # FastAPI's own request-validation shape, not our business-error shape.
    assert isinstance(res.json()["detail"], list)


def test_unmapped_columns_are_allowed_when_all_required_fields_present():
    mapping = dict(VALID_MAPPING)
    mapping["Notes"] = None
    res = client.post(
        "/api/mapping/submit",
        json={"columns": VALID_COLUMNS, "mapping": mapping},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


UNMAPPABLE_CSV = b"Date of Sale,Reference,Stock Ref,Description,Units,Value\n2026-01-15,ORD-1,P-100,Widget,2,9.99\n"

UNMAPPABLE_MAPPING = {
    "Date of Sale": "transaction_date",
    "Reference": "order_id",
    "Stock Ref": "product_id",
    "Description": "product_name",
    "Units": "quantity",
    "Value": "unit_price",
}


def test_apply_finishes_an_upload_the_automatic_matcher_could_not(tmp_path, monkeypatch):
    """/api/mapping/apply is how a manual mapping actually rescues a failed
    upload: /api/upload rejects this file because none of its headers match
    automatically, then /api/mapping/apply re-processes the same saved file
    using the mapping the user just confirmed, without re-uploading it.
    """
    monkeypatch.chdir(tmp_path)

    filename = "odd_mapped_successfully.csv"

    upload_res = client.post(
        "/api/upload",
        files={"file": (filename, UNMAPPABLE_CSV, "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )
    assert upload_res.status_code == 200
    upload_body = upload_res.json()
    assert upload_body["stored"] is False
    assert upload_body["columns"] == [
        "Date of Sale",
        "Reference",
        "Stock Ref",
        "Description",
        "Units",
        "Value",
    ]

    apply_res = client.post(
        "/api/mapping/apply",
        json={
            "filename": filename,
            "data_type": "sales",
            "currency": "SAR",
            "columns": upload_body["columns"],
            "mapping": UNMAPPABLE_MAPPING,
        },
    )
    assert apply_res.status_code == 200
    apply_body = apply_res.json()
    assert apply_body["stored"] is True
    assert apply_body["status"] == "success"
    assert apply_body["row_count"] == 1

    # The cleaned file now lives in Azure, not on local disk - confirm it
    # round-trips through the real API surface instead.
    datasets = client.get("/api/datasets").json()["datasets"]
    dataset = next(d for d in datasets if d["filename"] == filename)

    detail = client.get("/api/dashboard/detailed", params={"dataset_id": dataset["id"]})
    assert detail.status_code == 200
    assert detail.json()["data_quality"]["total_rows"] == 1


def test_apply_rejects_a_structurally_invalid_mapping_without_touching_the_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    filename = "odd_invalid_manual_mapping.csv"

    client.post(
        "/api/upload",
        files={"file": (filename, UNMAPPABLE_CSV, "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    apply_res = client.post(
        "/api/mapping/apply",
        json={
            "filename": filename,
            "data_type": "sales",
            "currency": "SAR",
            "columns": ["Date of Sale", "Reference"],
            "mapping": {"Date of Sale": "transaction_date"},  # missing 5 required fields
        },
    )
    assert apply_res.status_code == 422
    errors = apply_res.json()["detail"]["errors"]
    assert "order_id" in errors["missing_required_fields"]

    datasets = client.get("/api/datasets").json()["datasets"]
    assert not any(d["filename"] == filename for d in datasets)


def test_apply_reports_a_missing_file_instead_of_a_server_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    apply_res = client.post(
        "/api/mapping/apply",
        json={
            "filename": "never-uploaded.csv",
            "data_type": "sales",
            "currency": "SAR",
            "columns": VALID_COLUMNS,
            "mapping": VALID_MAPPING,
        },
    )
    assert apply_res.status_code == 404

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

pytestmark = pytest.mark.usefixtures("authenticated_user")


# --- In-memory fakes for Azure Blob Storage and the datasets DB table -----
#
# These tests exercise the real upload pipeline (parsing, cleaning, column
# mapping, validation) end to end through the actual API, which is the
# point of them - but the *storage* layer underneath (Azure Blob + Postgres)
# isn't available on the CI agent (no service connection is configured
# there yet - see the pipeline's own comment: "No deployment yet"). Locally
# these pass because the developer's machine has real `az login` + DB
# access; on CI they fail with DefaultAzureCredential/psycopg connection
# errors. Swapping both for in-memory fakes keeps the tests meaningful
# (still real business logic) while removing the only part that needs a
# live cloud connection.


class _FakeAzureStorage:
    """Stand-in for AzureStorage - one shared in-memory dict instead of a
    real Blob container, keyed by (user_id, filename) so a value saved by
    one call is readable by a later one within the same test.
    """

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


# A plain list, not keyed by (user_id, filename) - re-uploading the same
# display filename now creates a separate row (see insert_dataset), so the
# same filename can legitimately appear more than once here.
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

    # Used by prepare_upload/load_cleaned for the cleaned file itself.
    monkeypatch.setattr("app.data_pipeline.preparation.AzureStorage", _FakeAzureStorage)

    # Used by /api/mapping/apply to register the dataset row - /api/upload
    # itself never persists (preview only), see upload/router.py.
    monkeypatch.setattr("app.data_pipeline.mapping.router.insert_dataset", _fake_insert_dataset)
    monkeypatch.setattr("app.data_pipeline.mapping.router.find_matching_dataset", _fake_find_matching_dataset)

    # Used by GET /api/datasets, including its self-healing existence check.
    monkeypatch.setattr("app.db.datasets_router.list_datasets_for_user", _fake_list_datasets_for_user)
    monkeypatch.setattr("app.db.datasets_router.AzureStorage", _FakeAzureStorage)
    monkeypatch.setattr("app.db.datasets_router.delete_dataset", _fake_delete_dataset)

    # Used by GET /api/dashboard/detailed for the ownership check.
    monkeypatch.setattr("app.dashboard.router.get_dataset_for_user", _fake_get_dataset_for_user)


def test_upload_valid_csv_returns_200(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("data.csv", b"a,b,c\n1,2,3", "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["filename"] == "data.csv"
    assert body["data_type"] == "sales"
    assert body["extension"] == ".csv"


def test_upload_invalid_extension_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


SALES_CSV = (
    b"Order Date,Order No,SKU,Item,Qty,Unit Price,Product Category\n"
    b"2026-01-15,ORD-1,P-100,Widget,2,9.99,Tools\n"
    b"2026-01-15,ORD-1,P-100,Widget,2,9.99,Tools\n"
    b"2026-01-16,ORD-2,P-200,Gadget,1,19.99,\n"
    b",ORD-3,P-300,Doohickey,5,4.50,Tools\n"
)

UNMAPPABLE_CSV = b"Date of Sale,Reference,Stock Ref,Description,Units,Value\n2026-01-15,ORD-1,P-100,Widget,2,9.99\n"


def test_upload_returns_the_data_quality_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 200

    body = response.json()
    summary = body["data_quality"]

    assert summary["rows_read"] == 4
    assert summary["rows_excluded"] == 1
    assert summary["duplicates_removed"] == 1
    assert summary["values_filled"] == 1
    assert body["row_count"] == summary["rows_kept"] == 2
    assert body["stored"] is True
    assert body["validation"]["is_valid"] is True
    assert body["validation"]["missing_required_fields"] == []


def test_upload_stores_the_prepared_dataset(tmp_path, monkeypatch):
    """/api/upload is preview-only now - it never registers a dataset by
    itself, even when the automatic column match succeeds completely. The
    dataset only gets created once the frontend's review step confirms via
    /api/mapping/apply, so this test drives that same two-step flow before
    checking the cleaned file round-trips through the real API surface.
    """
    monkeypatch.chdir(tmp_path)

    upload_res = client.post(
        "/api/upload",
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )
    assert upload_res.status_code == 200
    upload_body = upload_res.json()
    assert upload_body["stored"] is True

    # No dataset exists yet - /api/upload alone never persists.
    assert client.get("/api/datasets").json()["datasets"] == []

    apply_res = client.post(
        "/api/mapping/apply",
        json={
            "filename": "sales.csv",
            "data_type": "sales",
            "currency": "SAR",
            "columns": upload_body["columns"],
            "mapping": {
                "Order Date": "transaction_date",
                "Order No": "order_id",
                "SKU": "product_id",
                "Item": "product_name",
                "Qty": "quantity",
                "Unit Price": "unit_price",
            },
        },
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["stored"] is True

    datasets = client.get("/api/datasets").json()["datasets"]
    dataset = next(d for d in datasets if d["filename"] == "sales.csv")

    detail = client.get("/api/dashboard/detailed", params={"dataset_id": dataset["id"]})

    assert detail.status_code == 200
    assert detail.json()["data_quality"]["total_rows"] == 2


def test_upload_reports_columns_it_could_not_identify(tmp_path, monkeypatch):
    """The file parses and cleans, but four required fields never mapped.

    Without this the summary would claim one of one rows is ready to use, while
    what was stored had no date, no price and no product id.
    """
    monkeypatch.chdir(tmp_path)

    filename = "odd_unmappable_upload.csv"

    response = client.post(
        "/api/upload",
        files={"file": (filename, UNMAPPABLE_CSV, "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["stored"] is False
    assert body["status"] == "incomplete"
    assert body["row_count"] == 0
    assert body["validation"]["is_valid"] is False
    assert "transaction_date" in body["validation"]["missing_required_fields"]

    datasets = client.get("/api/datasets").json()["datasets"]
    assert not any(d["filename"] == filename for d in datasets)


def test_upload_of_an_unreadable_file_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("broken.xlsx", b"not really a spreadsheet", "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 400
    assert "Could not read" in response.json()["detail"]


def test_upload_of_an_empty_file_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("nothing.csv", b"", "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_of_a_file_with_no_data_rows_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("headings.csv", b"Order Date,Qty,Unit Price\n", "text/csv")},
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 400
    assert "no data rows" in response.json()["detail"]


def test_successful_sales_upload_runs_anomaly_detection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    captured = {}

    def fake_detect_anomalies(dataframe):
        captured["dataframe"] = dataframe.copy()
        return []

    monkeypatch.setattr(
        "app.data_pipeline.upload.router.detect_anomalies",
        fake_detect_anomalies,
    )

    response = client.post(
        "/api/upload",
        files={
            "file": (
                "sales.csv",
                SALES_CSV,
                "text/csv",
            )
        },
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 200
    assert response.json()["stored"] is True

    assert "dataframe" in captured

    prepared_dataframe = captured["dataframe"]

    assert len(prepared_dataframe) == 2

    assert {
        "transaction_date",
        "quantity",
        "unit_price",
        "revenue",
    }.issubset(prepared_dataframe.columns)


def test_incomplete_sales_upload_skips_anomaly_detection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    def fail_if_called(_dataframe):
        pytest.fail("Anomaly detection should not run for an incomplete upload.")

    monkeypatch.setattr(
        "app.data_pipeline.upload.router.detect_anomalies",
        fail_if_called,
    )

    response = client.post(
        "/api/upload",
        files={
            "file": (
                "odd.csv",
                UNMAPPABLE_CSV,
                "text/csv",
            )
        },
        data={"data_type": "sales", "currency": "SAR"},
    )

    assert response.status_code == 200
    assert response.json()["stored"] is False

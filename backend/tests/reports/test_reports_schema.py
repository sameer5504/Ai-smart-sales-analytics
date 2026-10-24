from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.reports.schemas import Report, ReportListResponse, ReportSummary


def test_report_summary_holds_its_core_fields():
    summary = ReportSummary(
        report_id="abc123",
        user_id=1,
        generated_at=datetime.now(timezone.utc),
    )

    assert summary.report_id == "abc123"
    assert summary.user_id == 1


def test_report_summary_rejects_missing_fields():
    with pytest.raises(ValidationError):
        ReportSummary(report_id="abc123")


def test_report_includes_a_data_payload():
    report = Report(
        report_id="abc123",
        user_id=1,
        generated_at=datetime.now(timezone.utc),
        data={"total": 100},
    )

    assert report.data == {"total": 100}


def test_report_round_trips_through_json():
    report = Report(
        report_id="abc123",
        user_id=1,
        generated_at=datetime.now(timezone.utc),
        data={"total": 100, "nested": {"a": [1, 2, 3]}},
    )

    restored = Report.model_validate_json(report.model_dump_json())

    assert restored == report


def test_report_list_response_wraps_summaries():
    summary = ReportSummary(
        report_id="abc123",
        user_id=1,
        generated_at=datetime.now(timezone.utc),
    )

    response = ReportListResponse(reports=[summary])

    assert response.reports == [summary]

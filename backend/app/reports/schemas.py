from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportSummary(BaseModel):
    """Metadata for one stored report, without its full data payload.

    Returned by the list endpoint so a user can see what reports they have
    without pulling every report's full content over the wire.
    """

    report_id: str
    user_id: int
    generated_at: datetime


class Report(ReportSummary):
    """A stored report, including its full data payload.

    ``data`` is intentionally an open payload rather than a fixed set of
    business fields: nothing in the codebase yet defines what a generated
    report contains (see app/reports/service.py), so the contract here is
    just "whatever the generator produced", as JSON.
    """

    data: dict[str, Any]


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]


class GenerateReportRequest(BaseModel):
    """Body for POST /api/reports: whatever the caller wants saved as a
    report's content. The Dashboard page is the current caller -- it sends
    its computed KPIs, chart series and top-products, exactly as shown on
    screen, since that computation lives client-side (see
    frontend/src/features/dashboard/utils/aggregateDashboardData.js) and
    the backend has no equivalent of its own to recompute from.
    """

    data: dict[str, Any]

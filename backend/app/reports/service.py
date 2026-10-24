import logging
import os
import uuid
from datetime import datetime, timezone

from app.reports.schemas import Report, ReportSummary
from app.storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)

REPORTS_BASE_DIR = "reports"


def _storage_for_user(user_id: int) -> LocalStorage:
    """Reports are isolated per user by directory, not just by a filter
    applied after loading -- a user's storage instance can only ever read
    or write inside their own subdirectory.
    """

    return LocalStorage(base_dir=os.path.join(REPORTS_BASE_DIR, str(user_id)))


async def save_report(user_id: int, data: dict) -> Report:
    """Persist a generated report as JSON, scoped to its owning user.

    Called from POST /api/reports (see app.reports.router.generate_report),
    which just passes through whatever the caller sends. The Dashboard page
    is the current caller: it has no server-side equivalent to recompute
    its KPIs/charts from, since that aggregation lives client-side in
    frontend/src/features/dashboard/utils/aggregateDashboardData.js, so it
    sends its already-computed view as-is rather than the backend
    reproducing the same numbers a second way.
    """

    report = Report(
        report_id=uuid.uuid4().hex,
        user_id=user_id,
        generated_at=datetime.now(timezone.utc),
        data=data,
    )

    storage = _storage_for_user(user_id)
    contents = report.model_dump_json().encode("utf-8")
    await storage.save(f"{report.report_id}.json", contents)

    return report


async def list_reports(user_id: int) -> list[ReportSummary]:
    """Return metadata for every report belonging to the given user, most
    recently generated first.
    """

    storage = _storage_for_user(user_id)
    # list_files() / load() are synchronous on LocalStorage (matching
    # AzureStorage's interface - see StorageBase) - only save() is async.
    filenames = storage.list_files()

    summaries = []

    for filename in filenames:
        if not filename.endswith(".json"):
            continue

        try:
            contents = storage.load(filename)
            report = Report.model_validate_json(contents)
        except (OSError, ValueError) as exc:
            # A single unreadable/corrupt report shouldn't break the whole
            # list -- skip it and let the rest come back.
            logger.warning("Skipping unreadable report %s: %s", filename, exc)
            continue

        summaries.append(
            ReportSummary(
                report_id=report.report_id,
                user_id=report.user_id,
                generated_at=report.generated_at,
            )
        )

    summaries.sort(key=lambda summary: summary.generated_at, reverse=True)

    return summaries


async def get_report(user_id: int, report_id: str) -> Report:
    """Return one report if it exists and belongs to the given user.

    Raises FileNotFoundError both when the report doesn't exist and when it
    belongs to a different user, so the two cases are indistinguishable to
    the caller -- a report id must never reveal whether it belongs to
    someone else.
    """

    storage = _storage_for_user(user_id)

    try:
        # load() is synchronous on LocalStorage - see the note in
        # list_reports() above.
        contents = storage.load(f"{report_id}.json")
    except ValueError as exc:
        # get_path() rejects a report_id containing path separators; treat
        # that the same as "not found" rather than surfacing the ValueError.
        raise FileNotFoundError(f"Report not found: {report_id}") from exc

    report = Report.model_validate_json(contents)

    if report.user_id != user_id:
        # Shouldn't happen given per-user storage directories, but kept as
        # defense in depth per the task requirement.
        raise FileNotFoundError(f"Report not found: {report_id}")

    return report
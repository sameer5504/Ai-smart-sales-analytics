from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.reports.schemas import GenerateReportRequest, Report, ReportListResponse
from app.reports.service import get_report, list_reports, save_report

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ReportListResponse)
async def list_my_reports(
    current_user: dict = Depends(get_current_user),
):
    """Return metadata for the current user's saved reports."""

    reports = await list_reports(current_user["user_id"])
    return ReportListResponse(reports=reports)


@router.post("", response_model=Report)
async def generate_report(
    payload: GenerateReportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Save a new report from whatever the caller sends as its content.

    See GenerateReportRequest -- today that's the Dashboard page's current
    KPIs/chart series/top products, sent as-is.
    """

    return await save_report(current_user["user_id"], payload.data)


@router.get("/download/{report_id}", response_model=Report)
async def download_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return one report by id, if it belongs to the current user."""

    try:
        return await get_report(current_user["user_id"], report_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

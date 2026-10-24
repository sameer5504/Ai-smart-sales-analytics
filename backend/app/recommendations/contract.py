"""Output contract for recommendation generation (US-4.3.x).

Recommendations are built here, in Python, from the business's own rows. The
assistant that delivers them in chat phrases what it is given and does not
produce figures of its own, so any number shown to a user comes from one of
these objects.

Follows the available/unavailable result pattern used by
app/forecast/contract.py, so there is always a response to render.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.anomaly.schemas import Anomaly, AnomalyMetric, AnomalySeverity

# Result statuses.
STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

# Machine-readable reasons for an unavailable result.
REASON_NO_FINDINGS = "no_findings"
REASON_INSUFFICIENT_HISTORY = "insufficient_history"
REASON_DETECTION_UNAVAILABLE = "detection_unavailable"

# How many recommendations are returned at once (US-4.3.6).
DEFAULT_MAX_RECOMMENDATIONS = 5


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImpactConfidence(StrEnum):
    """Whether an impact figure is measured from the data or projected.

    The assistant states which one it is, so an estimate is not presented as
    a fact.
    """

    MEASURED = "measured"
    PROJECTED = "projected"


class DemandSource(StrEnum):
    """Where a restock quantity's demand estimate came from (US-4.3.5).

    PRODUCT_FORECAST is the product-level sales forecast (US-3.1.1).
    TRAILING_SALES is the fallback for a product that cannot be forecast.
    """

    PRODUCT_FORECAST = "product_forecast"
    TRAILING_SALES = "trailing_sales"


class Evidence(BaseModel):
    """The figures behind a recommendation, computed from the user's rows.

    Shown to the user when they ask what a suggestion is based on (US-5.4.2).

    Attributes:
        metric: units sold or revenue, carried over from the finding.
        current_value: the metric's value in the evaluated period.
        baseline_value: the normal value from the business's own history.
        change_percent: signed percentage change against the baseline.
        units_lost: units below baseline over the period. None when the
            finding is not about a shortfall.
        revenue_at_risk: the money attached to that gap, over the period.
        revenue_share_percent: the product's share of total revenue, which
            distinguishes a small product's decline from a large one's.
        period_start: first day of the window the figures cover.
        period_end: last day of the window the figures cover.
        currency: currency for the money fields. None when the upload did not
            establish one.
    """

    model_config = ConfigDict(frozen=True)

    metric: AnomalyMetric
    current_value: float
    baseline_value: float | None = None
    change_percent: float | None = None

    units_lost: float | None = None
    revenue_at_risk: float | None = None
    revenue_share_percent: float | None = None

    period_start: date
    period_end: date
    currency: str | None = None


class Impact(BaseModel):
    """What acting on a recommendation is expected to be worth (US-4.3.3).

    Attributes:
        value: the monthly amount, in currency. None when the data does not
            support an estimate, in which case unavailable_reason explains why.
        currency: currency of value.
        confidence: measured or projected.
        basis: one sentence naming the assumption, for example "if sales
            return to the four-week median". The assistant quotes this rather
            than writing its own justification.
        unavailable_reason: why no value could be produced.
    """

    model_config = ConfigDict(frozen=True)

    value: float | None = None
    currency: str | None = None
    confidence: ImpactConfidence = ImpactConfidence.PROJECTED
    basis: str = Field(min_length=1)
    unavailable_reason: str | None = None


class Recommendation(BaseModel):
    """A finding turned into an action the business owner can take.

    Attributes:
        id: stable identifier, so a follow-up question in chat can refer to
            one recommendation (US-5.4.1).
        finding: the anomaly this answers, carried whole so the assistant can
            explain the trigger without a second lookup.
        action: what to do, in one sentence.
        rationale: why the action follows from the finding. Quoted when the
            user asks why it was suggested (US-5.4.1).
        evidence: the figures behind it (US-4.3.2).
        expected_impact: what acting is worth (US-4.3.3).
        priority: 1 is most important. Set by ranking (US-4.3.6).
        restock_units: suggested restock quantity, when the rule produced one.
        demand_source: whether that quantity came from the forecast or from
            trailing sales (US-4.3.5).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    finding: Anomaly

    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    evidence: Evidence
    expected_impact: Impact

    priority: int = Field(default=0, ge=0)

    restock_units: float | None = None
    demand_source: DemandSource | None = None

    @property
    def severity(self) -> AnomalySeverity:
        """Severity comes from the finding and is not set independently."""
        return self.finding.severity

    @property
    def is_critical(self) -> bool:
        """Used to lead the assistant's answer with urgent findings (US-5.8.3)."""
        return self.finding.severity is AnomalySeverity.CRITICAL


class RecommendationsResult(BaseModel):
    """The API response, and the context the assistant is grounded in.

    Build these with the available and unavailable constructors so the fields
    each case needs are always set.

    Attributes:
        status: "available" or "unavailable".
        recommendations: ranked, most important first. Empty when unavailable.
        total_findings: how many anomalies detection produced, before capping.
        suppressed_count: how many the cap held back, so the assistant can
            offer the rest on request (US-4.3.6).
        reason: machine code, set when unavailable.
        message: human-readable explanation, safe to show the user.
        generated_at: ISO-8601 UTC timestamp.
    """

    status: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    total_findings: int = 0
    suppressed_count: int = 0
    reason: str | None = None
    message: str | None = None
    generated_at: str = Field(default_factory=_utc_now_iso)

    @classmethod
    def available(
        cls,
        *,
        recommendations: list[Recommendation],
        total_findings: int,
        suppressed_count: int = 0,
    ) -> RecommendationsResult:
        """Build a result carrying recommendations."""
        return cls(
            status=STATUS_AVAILABLE,
            recommendations=list(recommendations),
            total_findings=total_findings,
            suppressed_count=suppressed_count,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        reason: str,
        message: str,
        total_findings: int = 0,
    ) -> RecommendationsResult:
        """Build a result with nothing to recommend.

        Having nothing to report is a normal outcome, not an error, so this
        is returned with a 200 and an explanation rather than a 404.
        """
        return cls(
            status=STATUS_UNAVAILABLE,
            reason=reason,
            message=message,
            total_findings=total_findings,
        )

    @property
    def critical(self) -> list[Recommendation]:
        """The findings the assistant leads its answer with (US-5.8.3)."""
        return [r for r in self.recommendations if r.is_critical]

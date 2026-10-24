import pytest

from app.sales_forecasting.model import (
    classify_history,
    forecast_from_history,
    moving_average_3,
)
from app.sales_forecasting.schemas import (
    ForecastStatus,
)


def test_moving_average_uses_last_three_periods():
    result = moving_average_3(
        [2, 4, 10, 20]
    )

    assert result == pytest.approx(
        (4 + 10 + 20) / 3
    )


def test_moving_average_uses_available_periods_when_short():
    result = moving_average_3(
        [10, 20]
    )

    assert result == pytest.approx(
        15
    )


def test_moving_average_empty_history_returns_none():
    assert moving_average_3([]) is None


def test_moving_average_never_returns_negative():
    result = moving_average_3(
        [-10, -5, -1]
    )

    assert result == 0


@pytest.mark.parametrize(
    (
        "nonzero_periods",
        "expected",
    ),
    [
        (
            0,
            ForecastStatus.NO_SALES_HISTORY,
        ),
        (
            1,
            ForecastStatus.INSUFFICIENT_HISTORY,
        ),
        (
            2,
            ForecastStatus.INSUFFICIENT_HISTORY,
        ),
        (
            3,
            ForecastStatus.FORECASTABLE,
        ),
        (
            10,
            ForecastStatus.FORECASTABLE,
        ),
    ],
)
def test_history_classification(
    nonzero_periods,
    expected,
):
    assert (
        classify_history(
            nonzero_periods
        )
        == expected
    )


def test_negative_nonzero_period_count_is_rejected():
    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        classify_history(-1)


def test_forecastable_history_returns_prediction():
    status, prediction = (
        forecast_from_history(
            [0, 4, 8, 12]
        )
    )

    assert (
        status
        == ForecastStatus.FORECASTABLE
    )

    assert prediction == pytest.approx(
        (4 + 8 + 12) / 3
    )


def test_insufficient_history_returns_null_prediction():
    status, prediction = (
        forecast_from_history(
            [0, 0, 5, 0, 3]
        )
    )

    assert (
        status
        == ForecastStatus.INSUFFICIENT_HISTORY
    )

    assert prediction is None


def test_no_sales_history_returns_null_prediction():
    status, prediction = (
        forecast_from_history(
            [0, 0, 0]
        )
    )

    assert (
        status
        == ForecastStatus.NO_SALES_HISTORY
    )

    assert prediction is None
